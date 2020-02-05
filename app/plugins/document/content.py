import json
import re
import traceback
import html
import os
import shutil
import mongoengine
from corpus import Content, File, run_neo, get_corpus
from natsort import natsorted
from datetime import datetime
from django.utils.text import slugify


REGISTRY = [
    {
        "name": "Document",
        "plural_name": "Documents",
        "show_in_nav": True,
        "proxy_field": "",
        "inherited_from_module": "plugins.document.content",
        "inherited_from_class": "Document",
        "has_file_field": True,
        "label_template": "{{ Document.title }}",
        "fields": [
            {
                "name": "title",
                "label": "Title",
                "type": "text",
                "inherited": True,
            },
            {
                "name": "author",
                "label": "Author",
                "type": "text",
                "inherited": True,
            },
            {
                "name": "work",
                "label": "Work",
                "in_lists": False,
                "type": "text",
                "inherited": True,
            },
            {
                "name": "expression",
                "label": "Expression",
                "type": "text",
                "in_lists": False,
                "inherited": True
            },
            {
                "name": "manifestation",
                "label": "Manifestation",
                "type": "text",
                "in_lists": False,
                "inherited": True
            },
            {
                "name": "pub_date",
                "label": "Published",
                "type": "keyword",
                "inherited": True
            },
            {
                "name": "files",
                "label": "Files",
                "type": "embedded",
                "multiple": True,
                "inherited": True,
                "in_lists": False
            },
            {
                "name": "pages",
                "label": "Pages",
                "type": "embedded",
                "multiple": True,
                "inherited": True,
                "in_lists": False
            },
            {
                "name": "page_sets",
                "label": "Page Sets",
                "type": "embedded",
                "multiple": True,
                "inherited": True,
                "in_lists": False
            },
        ],
        "invalid_field_names": [
            "kvp",
            "page_file_collections",
            "has_primary_text",
            "ordered_pages",
            "get_page_file_collection",
            "save_file",
            "running_jobs",
            "save_page",
            "save_page_file"
        ],
        "base_mongo_indexes": [
            {
                'fields': ['id', 'pages.ref_no'],
                'unique': True,
                'sparse': True
            },
            {
                'fields': ['id', 'files.path'],
                'unique': True,
                'sparse': True
            },
            {
                'fields': ['id', 'pages.files.path'],
                'unique': True,
                'sparse': True
            }
        ],
        "templates": {
            "Label": {
                "template": "{{ Document.title }}{% if Document.author %} ({{ Document.author }}){% endif %}",
                "mime_type": "text/html"
            }
        }
    },
]

'''
    def get_document_index_mapping(self):
        corpora_analyzer = analyzer(
            'corpora_analyzer',
            tokenizer='classic',
            filter=['stop', 'lowercase', 'classic']
        )
        mapping = Mapping()

        page_field = Nested(
            properties={
                'ref_no': Integer(),
                'contents': Text(analyzer=corpora_analyzer)
            }
        )
        mapping.field('pages', page_field)

        for field_name, field_setting in self.field_settings.items():
            if field_setting['display']:
                field_type = field_setting.get('type', 'keyword')
                if field_type not in ['keyword', 'text', 'integer', 'date']:
                    field_type = 'keyword'

                if field_type == 'keyword' or (field_type == 'text' and not field_setting['search']):
                    mapping.field(field_setting['es_field_name'], 'keyword')
                elif field_type == 'text':
                    subfields = {}
                    if field_setting['sort']:
                        subfields = { 'raw': Keyword() }
                    mapping.field(field_setting['es_field_name'], 'text', analyzer=corpora_analyzer, fields=subfields)
                elif field_type == 'integer':
                    mapping.field(field_setting['es_field_name'], Integer())
                elif field_type == 'date':
                    mapping.field(field_setting['es_field_name'], Date())

        return mapping
'''

class Page(mongoengine.EmbeddedDocument):
    instance = mongoengine.StringField()
    label = mongoengine.StringField()
    ref_no = mongoengine.StringField()
    kvp = mongoengine.DictField()
    files = mongoengine.MapField(mongoengine.EmbeddedDocumentField(File))

    @property
    def tei_text(self):
        if not hasattr(self, '_text'):
            self._text = ""
            illegal_chars_pattern_matcher = re.compile(u'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]')

            for file_key, file in self.files.items():
                if file.extension == 'txt' and file.primary_witness:
                    try:
                        with open(file.path, 'r', encoding='utf-8') as file_in:
                            self._text = file_in.read()
                        self._text = html.escape(self._text)
                        self._text = re.sub(illegal_chars_pattern_matcher, '', self._text)
                        self._text = self._text.replace('\n\n', "</p><p>")
                        self._text = "<p>" + self._text + "</p>"
                    except:
                        print("Error reading primary text witness for page {0}".format(self.ref_no))
                        print(traceback.format_exc())
                        self._text = ""
        return self._text

    def _do_linking(self, content_type, content_uri):
        page_uri = "{0}/page/{1}".format(content_uri, self.ref_no)
        
        run_neo('''
                MATCH (d:{content_type} {{ uri: $doc_uri }})
                MERGE (p:Page {{ uri: $page_uri }})
                SET p.label = $page_label
                SET p.ref_no = $page_ref_no
                MERGE (d) -[rel:hasPage]-> (p) 
            '''.format(content_type=content_type),
            {
                'doc_uri': content_uri,
                'page_uri': page_uri,
                'page_label': self.label if self.label else self.ref_no,
                'page_ref_no': self.ref_no
            }
        )

        for file_key, file in self.files.items():
            file._do_linking(content_type='Page', content_uri=page_uri)

    def to_dict(self, parent_uri):
        return {
            'uri': "{0}/page/{1}".format(parent_uri, self.ref_no),
            'instance': self.instance,
            'label': self.label,
            'ref_no': self.ref_no,
            'files': [file.to_dict(parent_uri) for file_key, file in self.files.items()]
        }


class PageNavigator(object):
    def __init__(self, page_dict, page_set=None):
        self.page_dict = page_dict
        if not page_set:
            self.ordered_ref_nos = natsorted(list(page_dict.keys()))
        else:
            self.ordered_ref_nos = page_set.ref_nos
        self.bookmark = 0

    def __iter__(self):
        self.bookmark = 0
        return self

    def __next__(self):
        if self.bookmark < len(self.ordered_ref_nos):
            self.bookmark += 1
            return self.ordered_ref_nos[self.bookmark - 1], self.page_dict[self.ordered_ref_nos[self.bookmark - 1]]
        else:
            raise StopIteration


class PageSet(mongoengine.EmbeddedDocument):
    label = mongoengine.StringField()
    ref_nos = mongoengine.ListField(mongoengine.StringField())

    @property
    def starting_ref_no(self):
        if self.ref_nos:
            return self.ref_nos[0]
        return None

    @property
    def ending_ref_no(self):
        if self.ref_nos:
            return self.ref_nos[-1]
        return None

    def to_dict(self):
        return {
            'label': self.label,
            'ref_nos': [ref_no for ref_no in self.ref_nos],
            'starting_ref_no': self.starting_ref_no,
            'ending_ref_no': self.ending_ref_no
        }


class Document(Content):
    title = mongoengine.StringField()
    work = mongoengine.StringField()
    expression = mongoengine.StringField()
    manifestation = mongoengine.StringField()
    author = mongoengine.StringField()
    pub_date = mongoengine.StringField()
    kvp = mongoengine.DictField()
    files = mongoengine.MapField(mongoengine.EmbeddedDocumentField(File))
    pages = mongoengine.MapField(mongoengine.EmbeddedDocumentField(Page))
    page_sets = mongoengine.MapField(mongoengine.EmbeddedDocumentField(PageSet))

    @property
    def page_file_collections(self):
        if not hasattr(self, '_page_file_collections'):
            self._page_file_collections = {}
            cached_pfcs = run_neo(
                '''
                    MATCH (d:Document { uri: $doc_uri }) -[:hasPageFileCollection]-> (pfc:PageFileCollection)
                    RETURN pfc
                '''
                ,
                {
                    'doc_uri': "/corpus/{0}/Document/{1}".format(self.corpus_id, self.id)
                }
            )

            if cached_pfcs:
                for cached_pfc in cached_pfcs:
                    created = datetime.fromtimestamp(cached_pfc['pfc']['created'])
                    if created >= self.last_updated:
                        label = cached_pfc['pfc']['label']
                        slug = cached_pfc['pfc']['slug']
                        page_file_dict = json.loads(cached_pfc['pfc']['page_file_dict_json'])
                        self._page_file_collections[slug] = {
                            'label': label,
                            'page_files': PageNavigator(page_file_dict)
                        }

            if not self._page_file_collections:
                for ref_no, page in self.ordered_pages:
                    for file_key, file in self.pages[ref_no].files.items():
                        slug = slugify(file.collection_label)
                        if slug not in self._page_file_collections:
                            self._page_file_collections[slug] = {
                                'label': file.collection_label,
                                'page_files': {}
                            }
                        self._page_file_collections[slug]['page_files'][ref_no] = file.to_dict(self.uri)

                self._corpus.queue_local_job(
                    content_type="Document",
                    content_id=str(self.id),
                    task_name="Cache Page File Collections",
                    parameters={
                        'page_file_collections': self._page_file_collections
                    }
                )

                for slug in self._page_file_collections:
                    self._page_file_collections[slug]['page_files'] = PageNavigator(self._page_file_collections[slug]['page_files'])

        return self._page_file_collections

    @property
    def has_primary_text(self):
        for ref_no, page in self.pages.items():
            for file_key, file in page.files.items():
                if file.extension == 'txt' and file.primary_witness:
                    return True
        return False

    @property
    def ordered_pages(self, pageset=None):
        if not hasattr(self, '_page_navigator'):
            if pageset and pageset in self.page_sets:
                self._page_navigator = PageNavigator(self.pages, self.page_sets[pageset])
            elif '_default_pageset' in self.kvp and self.kvp['_default_pageset'] in self.page_sets:
                self._page_navigator = PageNavigator(self.pages, self.page_sets[self.kvp['_default_pageset']])
            else:
                self._page_navigator = PageNavigator(self.pages)
        return self._page_navigator

    @staticmethod
    def get_page_file_collection(corpus_id, document_id, slug):
        pfc = {}
        results = run_neo(
            '''
                MATCH (pfc:PageFileCollection { uri: $pfc_uri })
                RETURN pfc
            '''
            ,
            {
                'pfc_uri': "/corpus/{0}/Document/{1}/page-file-collection/{2}".format(corpus_id, document_id, slug)
            }
        )

        if results:
            pfc = {
                'label': results[0]['pfc']['label'],
                'page_files': PageNavigator(json.loads(results[0]['pfc']['page_file_dict_json']))
            }

        return pfc

    def save_file(self, file):
        self.files[file.key] = file
        self.save(do_indexing=False, do_linking=False)
        file._do_linking(content_type='Document', content_uri=self.uri)

    def save_page(self, page):
        self.pages[page.ref_no] = page
        self.save(do_indexing=False, do_linking=False)
        page._do_linking(content_type='Document', content_uri=self.uri)

    def save_page_file(self, page_ref_no, file):
        self.pages[page_ref_no].files[file.key] = file
        self.save(do_indexing=False, do_linking=False)
        file._do_linking(content_type='Page', content_uri="{0}/page/{1}".format(self.uri, page_ref_no))

    def to_dict(self, ref_only=False):
        doc_dict = {}

        if not ref_only:
            doc_dict['has_primary_text'] = self.has_primary_text
            doc_dict['page_file_collections'] = self.page_file_collections

            for slug in doc_dict['page_file_collections'].keys():
                doc_dict['page_file_collections'][slug]['page_files'] = doc_dict['page_file_collections'][slug]['page_files'].page_dict

        doc_dict.update(super().to_dict(ref_only))

        return doc_dict

    meta = {
        'abstract': True
    }


def reset_page_extraction(corpus_id, document_id):
    corpus = get_corpus(corpus_id)
    if corpus:
        document = corpus.get_content('Document', document_id)
        if document:
            print('found objects')

            dirs_to_delete = [
                "{0}/temporary_uploads".format(document.path),
                "{0}/files".format(document.path),
                "{0}/pages".format(document.path),
            ]

            for dir_to_delete in dirs_to_delete:
                if os.path.exists(dir_to_delete):
                    print('found {0}'.format(dir_to_delete))
                    shutil.rmtree(dir_to_delete)

            document.files = []
            document.pages = {}

            document.save(index_pages=True)
            corpus.save()
