import json
import re
import traceback
import html
import os
import shutil
import mongoengine
from corpus import Content, File, run_neo, get_corpus, FieldRenderer
from manager.utilities import _contains
from natsort import natsorted
from datetime import datetime
from django.utils.text import slugify
from django.template import Template, Context
from django.conf import settings


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
        "dependent_nodes": [
            "Page",
            "PageFileCollection"
        ],
        "templates": {
            "Label": {
                "template": "{{ Document.title }}{% if Document.author %} ({{ Document.author }}){% endif %}",
                "mime_type": "text/html"
            }
        }
    },
    {
        "name": "TranscriptionProject",
        "plural_name": "Transcription Projects",
        "fields": [
            {
                "name": "name",
                "label": "Name",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "document",
                "label": "Document",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Document",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "pageset",
                "label": "Page Set",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "image_pfc",
                "label": "Image Page File Collection",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "ocr_pfc",
                "label": "OCR Page File Collection",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "transcription_level",
                "label": "Transcription Level",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "transcription_text",
                "label": "Transcription Text",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": False,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "transcription_cursor",
                "label": "Transcription Cursor",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "number",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "allow_markup",
                "label": "Allow Markup?",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "boolean",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "markup_schema",
                "label": "Markup Schema",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "large_text",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "percent_complete",
                "label": "Percent Complete",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "number",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ TranscriptionProject.name }}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ],
        "view_widget_url": None,
        "edit_widget_url": None
    },
    {
        "name": "Transcription",
        "plural_name": "Transcriptions",
        "fields": [
            {
                "name": "project",
                "label": "Project",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "TranscriptionProject",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "page_refno",
                "label": "Page",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "scholar",
                "label": "Scholar",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "data",
                "label": "Data",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "large_text",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "complete",
                "label": "Complete?",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "boolean",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ Transcription.project.name }}, page {{ Transcription.page_refno }}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ],
        "view_widget_url": None,
        "edit_widget_url": None
    }
]


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
        uri_parts = [part for part in content_uri.split('/') if part]
        if uri_parts[0] == 'corpus' and len(uri_parts) > 1:
            corpus_id = uri_parts[1]
            page_uri = "{0}/page/{1}".format(content_uri, self.ref_no)
        
            run_neo('''
                    MATCH (d:{content_type} {{ uri: $doc_uri }})
                    MERGE (p:_Page {{ uri: $page_uri }})
                    SET p.label = $page_label
                    SET p.corpus_id = $corpus_id
                    SET p.ref_no = $page_ref_no
                    MERGE (d) -[rel:hasPage]-> (p) 
                '''.format(content_type=content_type),
                {
                    'doc_uri': content_uri,
                    'page_uri': page_uri,
                    'corpus_id': corpus_id,
                    'page_label': self.label if self.label else self.ref_no,
                    'page_ref_no': self.ref_no
                }
            )

            for file_key, file in self.files.items():
                file._do_linking(content_type='_Page', content_uri=page_uri)

    def _make_path(self, parent_path):
        page_path = "{0}/pages/{1}".format(parent_path, self.ref_no)
        os.makedirs(page_path, exist_ok=True)
        return page_path

    def to_dict(self, parent_uri):
        self_uri = "{0}/page/{1}".format(parent_uri, self.ref_no)
        self_dict = {
            'uri': self_uri,
            'instance': self.instance,
            'label': self.label,
            'ref_no': self.ref_no,
            'files': {}
        }
        for file_key, file in self.files.items():
            self_dict['files'][file_key] = file.to_dict(self_uri)
        return self_dict


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

    def to_dict(self, parent_uri=None):
        return {
            'label': self.label,
            'ref_nos': [ref_no for ref_no in self.ref_nos],
            'starting_ref_no': self.starting_ref_no,
            'ending_ref_no': self.ending_ref_no
        }


class PagesRenderer(object):

    def render(self, context):
        html_template = open(f"{settings.BASE_DIR}/plugins/document/field_templates/pages/view.html", 'r').read()
        django_template = Template(html_template)
        return django_template.render(context)


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

            if not self._page_file_collections:
                for ref_no, page in self.ordered_pages():
                    for file_key, file in self.pages[ref_no].files.items():
                        slug = slugify(file.collection_label)
                        if slug not in self._page_file_collections:
                            self._page_file_collections[slug] = {
                                'label': file.collection_label,
                                'page_files': {}
                            }
                        self._page_file_collections[slug]['page_files'][ref_no] = file.to_dict(self.uri + '/page/{0}'.format(ref_no))

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

    def ordered_pages(self, pageset=None):
        if pageset and pageset in self.page_sets:
            return PageNavigator(self.pages, self.page_sets[pageset])
        elif '_default_pageset' in self.kvp and self.kvp['_default_pageset'] in self.page_sets:
            return PageNavigator(self.pages, self.page_sets[self.kvp['_default_pageset']])
        else:
            return PageNavigator(self.pages)

    def get_page_file_collection(self, slug, pageset=None):
        pfc = {}
        for ref_no, page in self.ordered_pages(pageset):
            for file_key, file in self.pages[ref_no].files.items():
                collection_slug = slugify(file.collection_label)
                if collection_slug == slug:
                    if 'label' not in pfc:
                        pfc['label'] = file.collection_label
                        pfc['page_files'] = {}

                    pfc['page_files'][ref_no] = file.to_dict(self.uri + '/page/{0}'.format(ref_no))
        return pfc

    def save_file(self, file):
        self.modify(**{'set__files__{0}'.format(file.key): file})
        file._do_linking(content_type='Document', content_uri=self.uri)

    def save_page(self, page):
        self.modify(**{'set__pages__{0}'.format(page.ref_no): page})
        page._do_linking(content_type='Document', content_uri=self.uri)

    def save_page_file(self, page_ref_no, file):
        self.modify(**{'set__pages__{0}__files__{1}'.format(page_ref_no, file.key): file})
        file._do_linking(content_type='_Page', content_uri="{0}/page/{1}".format(self.uri, page_ref_no))

    def to_dict(self, ref_only=False):
        doc_dict = {}

        if not ref_only:
            doc_dict['has_primary_text'] = self.has_primary_text
            doc_dict['page_file_collections'] = self.page_file_collections

            for slug in doc_dict['page_file_collections'].keys():
                doc_dict['page_file_collections'][slug]['page_files'] = doc_dict['page_file_collections'][slug]['page_files'].page_dict

        doc_dict.update(super().to_dict(ref_only))

        return doc_dict

    def from_dict(self, dict):
        core_fields = ['title', 'work', 'expression', 'manifestation', 'author', 'pub_date']
        page_fields = ['instance', 'label', 'ref_no']
        file_fields = ['primary_witness', 'path', 'basename', 'extension', 'byte_size', 'description', 'provenance_type', 'provenance_id', 'height', 'width', 'iiif_info']

        if _contains(dict, core_fields):
            for core_field in core_fields:
                setattr(self, core_field, dict[core_field])

        for ref_no, page_dict in dict['pages'].items():
            p = Page()

            if _contains(page_dict, page_fields):
                for page_field in page_fields:
                    setattr(p, page_field, page_dict[page_field])

            for file_key, file_dict in page_dict['files'].items():
                f = File()
                if _contains(file_dict, file_fields):
                    for file_field in file_fields:
                        setattr(f, file_field, file_dict[file_field])

                p.files[file_key] = f

            self.pages[ref_no] = p

        for file_key, file_dict in dict['files'].items():
            f = File()
            if _contains(file_dict, file_fields):
                for file_field in file_fields:
                    setattr(f, file_field, file_dict[file_field])

            self.files[file_key] = f

        # Extra fields defined by corpus
        for ct_field in self._ct.fields:
            if not ct_field.inherited and ct_field.name in dict:
                setattr(self, ct_field.name, dict[ct_field.name])

    @classmethod
    def get_render_requirements(cls, mode):
        inclusions = {}
        javascript_functions = ""
        css_styles = ""

        if mode == 'view':
            inclusions = {
                'js': ['js/openseadragon.min.js', 'js/openseadragonselection.js'],
                 'directories': ['img/openseadragon', 'img/openseadragonselection']
            }

            javascript_functions = open(f"{settings.BASE_DIR}/plugins/document/field_templates/pages/view.js", 'r').read()
            css_styles = open(f"{settings.BASE_DIR}/plugins/document/field_templates/pages/view.css", 'r').read()

        return inclusions, javascript_functions, css_styles

    @classmethod
    def render_embedded_field(cls, field_name, field_value):
        template_path = f"{settings.BASE_DIR}/plugins/document/field_templates/{field_name}/view.html"
        if os.path.exists(template_path):
            html_template = open(template_path, 'r').read()
            django_template = Template(html_template)
            return django_template.render(Context({'value': field_value}))
        return ''

    meta = {
        'abstract': True
    }


def reset_page_extraction(corpus_id, document_id):
    corpus = get_corpus(corpus_id)
    if corpus:
        document = corpus.get_content('Document', document_id)
        if document:
            dirs_to_delete = [
                "{0}/temporary_uploads".format(document.path),
                "{0}/files".format(document.path),
                "{0}/pages".format(document.path),
            ]

            for dir_to_delete in dirs_to_delete:
                if os.path.exists(dir_to_delete):
                    shutil.rmtree(dir_to_delete)

            document.files = []
            document.pages = {}

            document.save(index_pages=True)
            corpus.save()
