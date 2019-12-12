import mongoengine
import os
import json
import secrets
import traceback
import html
import re
import zlib
from time import sleep
from copy import deepcopy
from natsort import natsorted
from dateutil import parser
from datetime import datetime
from bson.objectid import ObjectId
from PIL import Image
from django.conf import settings
from django.utils.text import slugify
from elasticsearch_dsl import Index, Mapping, analyzer, Keyword, Text, Integer, Date, \
    Nested, char_filter, Q, Search
from elasticsearch_dsl.query import SimpleQueryString
from elasticsearch_dsl.connections import get_connection
from .tasks import index_document_pages, cache_page_file_collections


class File(mongoengine.EmbeddedDocument):
    # TODO: when importing old corpora deal with primary_facsimile
    primary_witness = mongoengine.BooleanField()
    path = mongoengine.StringField()
    basename = mongoengine.StringField()
    extension = mongoengine.StringField()
    byte_size = mongoengine.IntField()
    description = mongoengine.StringField()
    provenance_type = mongoengine.StringField()
    provenance_id = mongoengine.StringField()
    height = mongoengine.IntField()
    width = mongoengine.IntField()
    iiif_info = mongoengine.DictField()

    @property
    def key(self):
        if not hasattr(self, '_key'):
            self._key = file_path_key(self.path)
        return self._key
    
    @property
    def collection_label(self):
        if not hasattr(self, '_collection_label'):
            self._collection_label = "{0}{1} from {2} ({3})".format(
                "Primary " if self.primary_witness else "",
                self.description,
                self.provenance_type,
                self.provenance_id
            ).strip()
        return self._collection_label

    def link(self, corpus_id, document_id=None, page_ref_no=None):
        node_type = "Corpus"
        node_uri = "/corpus/{0}".format(corpus_id)
        link_page_file_collection = False

        if document_id:
            node_type = "Document"
            node_uri += "/document/{0}".format(document_id)

        if page_ref_no:
            node_type = "Page"
            node_uri += "/page/{0}".format(page_ref_no)
            link_page_file_collection = True

        run_neo(
            '''
                MATCH (n:{node_type} {{ uri: $node_uri }})
                MERGE (f:File {{ uri: $file_uri }})
                SET f.key = $file_key
                MERGE (n) -[rel:hasFile]-> (f)
            '''.format(node_type=node_type),
            {
                'node_uri': node_uri,
                'file_uri': "{0}/file/{1}".format(node_uri, self.key),
                'file_key': self.key
            }
        )

    def to_dict(self):
        return {
            'primary_witness': self.primary_witness,
            'key': self.key,
            'path': self.path,
            'basename': self.basename,
            'extension': self.extension,
            'byte_size': self.byte_size,
            'description': self.description,
            'provenance_type': self.provenance_type,
            'provenance_id': self.provenance_id,
            'height': self.height,
            'width': self.width,
            'iiif_info': self.iiif_info
        }


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

            for file in self.files:
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

    def link(self, corpus_id, document_id):
        run_neo('''
                MATCH (d:Document { uri: $doc_uri })
                MERGE (p:Page { uri: $page_uri })
                SET p.label = $page_label
                SET p.ref_no = $page_ref_no
                MERGE (d) -[rel:hasPage]-> (p) 
            ''',
            {
                'doc_uri': "/corpus/{0}/document/{1}".format(corpus_id, document_id),
                'page_uri': "/corpus/{0}/document/{1}/page/{2}".format(corpus_id, document_id, self.ref_no),
                'page_label': self.label if self.label else self.ref_no,
                'page_ref_no': self.ref_no
            }
        )

        for file_key, file in self.files.items():
            file.link(corpus_id=corpus_id, document_id=document_id, page_ref_no=self.ref_no)

    def to_dict(self):
        return {
            'instance': self.instance,
            'label': self.label,
            'ref_no': self.ref_no,
            'files': [file.to_dict() for file_key, file in self.files.items()]
        }


class PageSet(mongoengine.EmbeddedDocument):
    label = mongoengine.StringField()
    ref_nos = mongoengine.ListField(mongoengine.StringField())
    kvp = mongoengine.DictField()

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


class Job(object):
    def __init__(self, id=None):
        if id:
            self._load(id)
        else:
            self.id = None
            self.corpus_id = None
            self.document_id = None
            self.task_id = None
            self.jobsite_id = None
            self.scholar_id = None
            self.submitted_time = None
            self.status = None
            self.status_time = None
            self.stage = 0
            self.timeout = 0
            self.tries = 0
            self.error = ""
            self.configuration = {}
            self.percent_complete = 0

    def _load(self, id):
        results = run_neo(
            '''
                MATCH (j:Job { uri: $job_uri })
                return j
            ''',
            {
                'job_uri': "/job/{0}".format(id)
            }
        )
        if len(results) == 1 and 'j' in results[0].keys():
            self._load_from_result(results[0]['j'])
            
    def _load_from_result(self, result):
        self.id = result['uri'].replace('/job/', '')
        self.corpus_id = result['corpus_id']
        self.document_id = result['document_id']
        self.task_id = result['task_id']
        self.jobsite_id = result['jobsite_id']
        self.scholar_id = result['scholar_id']
        self.submitted_time = datetime.fromtimestamp(result['submitted_time'])
        self.status = result['status']
        self.status_time = datetime.fromtimestamp(result['status_time'])
        self.stage = result['stage']
        self.timeout = result['timeout']
        self.tries = result['tries']
        self.error = result['error']
        self.configuration = json.loads(result['configuration'])

        # check process completion
        self.percent_complete = 0
        results = run_neo(
            '''
                MATCH (j:Job { uri: $job_uri }) -[rel:hasProcess]-> (p:Process)
                return p
            ''',
            {'job_uri': "/job/{0}".format(self.id)}
        )
        if results:
            processes_created = len(results)
            processes_completed = 0
            for proc in results:
                if proc['p']['status'] == 'complete':
                    processes_completed += 1
            if processes_completed > 0:
                self.percent_complete = int((processes_completed / processes_created) * 100)

    def save(self):
        if not self.id:
            self.id = str(ObjectId())
        if not self.submitted_time:
            self.submitted_time = datetime.now()
        if not self.status_time:
            self.status_time = self.submitted_time

        run_neo(
            '''
                MATCH (c:Corpus { uri: $corpus_uri })
                MATCH (d:Document { uri: $document_uri })
                MERGE (j:Job { uri: $job_uri })
                SET j.corpus_id = $job_corpus_id
                SET j.document_id = $job_document_id
                SET j.task_id = $job_task_id
                SET j.jobsite_id = $job_jobsite_id
                SET j.scholar_id = $job_scholar_id
                SET j.submitted_time = $job_submitted_time
                SET j.status = $job_status
                SET j.status_time = $job_status_time
                SET j.stage = $job_stage
                SET j.timeout = $job_timeout
                SET j.tries = $job_tries
                SET j.error = $job_error
                SET j.configuration = $job_configuration
                MERGE (c) -[:hasJob]-> (j) <-[:hasJob]- (d)
            ''',
            {
                'corpus_uri': "/corpus/{0}".format(self.corpus_id),
                'document_uri': "/corpus/{0}/document/{1}".format(self.corpus_id, self.document_id),
                'job_uri': "/job/{0}".format(self.id),
                'job_corpus_id': self.corpus_id,
                'job_document_id': self.document_id,
                'job_task_id': self.task_id,
                'job_jobsite_id': self.jobsite_id,
                'job_scholar_id': self.scholar_id,
                'job_submitted_time': int(self.submitted_time.timestamp()),
                'job_status': self.status,
                'job_status_time': int(self.status_time.timestamp()),
                'job_stage': self.stage,
                'job_timeout': self.timeout,
                'job_tries': self.tries,
                'job_error': self.error,
                'job_configuration': json.dumps(self.configuration)
            }
        )

    def to_dict(self):
        return {
            'id': self.id,
            'corpus_id': self.corpus_id,
            'document_id': self.document_id,
            'task_id': self.task_id,
            'jobsite_id': self.jobsite_id,
            'scholar_id': self.scholar_id,
            'submitted_time': int(self.submitted_time.timestamp()),
            'status': self.status,
            'status_time': int(self.status_time.timestamp()),
            'stage': self.stage,
            'timeout': self.timeout,
            'tries': self.tries,
            'error': self.error,
            'configuration': self.configuration,
            'percent_complete': self.percent_complete
        }

    def set_status(self, status):
        self.status = status
        self.status_time = datetime.now()

        run_neo(
            '''
                MATCH (j:Job { uri: $job_uri })
                SET j.status = $job_status
                SET j.status_time = $job_status_time
            ''',
            {
                'job_uri': "/job/{0}".format(self.id),
                'job_status': self.status,
                'job_status_time': int(self.status_time.timestamp())
            }
        )

    def add_process(self, process_id):
        run_neo(
            '''
                MATCH (j:Job { uri: $job_uri })
                MERGE (p:Process { uri: $process_uri })
                SET p.status = 'running'
                SET p.created = $process_created
                MERGE (j) -[rel:hasProcess]-> (p)
            ''',
            {
                'job_uri': "/job/{0}".format(self.id),
                'process_uri': "/job/{0}/process/{1}".format(self.id, process_id),
                'process_created': int(datetime.now().timestamp())
            }
        )

    def complete_process(self, process_id):
        run_neo(
            '''
                MATCH (j:Job { uri: $job_uri }) -[rel:hasProcess]-> (p:Process { uri: $process_uri })
                SET p.status = 'complete'
            ''',
            {
                'job_uri': "/job/{0}".format(self.id),
                'process_uri': "/job/{0}/process/{1}".format(self.id, process_id)
            }
        )

    def clear_processes(self):
        run_neo(
            '''
                MATCH (j:Job { uri: $job_uri }) -[rel:hasProcess]-> (p:Process)
                DETACH DELETE p
            ''',
            {'job_uri': "/job/{0}".format(self.id)}
        )

    @property
    def corpus(self):
        if not hasattr(self, '_corpus'):
            self._corpus = Corpus.objects(id=self.corpus_id)[0]
        return self._corpus

    @property
    def document(self):
        if not hasattr(self, '_document'):
            self._document = Document.objects(corpus=self.corpus_id, id=self.document_id)[0]
        return self._document

    @property
    def task(self):
        if not hasattr(self, '_task'):
            self._task = Task.objects(id=self.task_id)[0]
        return self._task

    @property
    def jobsite(self):
        if not hasattr(self, '_jobsite'):
            self._jobsite = JobSite.objects(id=self.jobsite_id)[0]
        return self._jobsite

    @property
    def scholar(self):
        if not hasattr(self, '_scholar'):
            self._scholar = Scholar.objects(id=self.scholar_id)[0]
        return self._scholar

    def complete(self, status=None, error_msg=None):
        if status:
            self.status = status
            self.status_time = datetime.now()
        if error_msg:
            self.error = error_msg

        ct = CompletedTask()
        ct.job_id = self.id
        ct.task = self.task.id
        ct.task_version = self.task.version
        ct.task_configuration = deepcopy(self.configuration)
        ct.jobsite = ObjectId(self.jobsite_id)
        ct.scholar = ObjectId(self.scholar_id)
        ct.submitted = self.submitted_time
        ct.completed = self.status_time
        ct.status = self.status
        ct.error = self.error

        self.document.modify(push__completed_tasks=ct, set__last_updated=datetime.now())

        run_neo(
            '''
                MATCH (j:Job { uri: $job_uri })
                OPTIONAL MATCH (j) -[rel:hasProcess]-> (p)
                DETACH DELETE j, p
            ''',
            {
                'job_uri': '/job/{0}'.format(self.id)
            }
        )

    @staticmethod
    def setup_retry_for_completed_task(corpus_id, document_id, completed_task):
        j = Job()
        j.id = completed_task.job_id
        j.corpus_id = corpus_id
        j.document_id = document_id
        j.task_id = str(completed_task.task.id)
        j.jobsite_id = str(completed_task.jobsite.id)
        j.scholar_id = str(completed_task.scholar.id)
        j.configuration = deepcopy(completed_task.task_configuration)
        j.status = 'preparing'
        j.save()
        return j

    @staticmethod
    def get_jobs(corpus_id=None, document_id=None):
        jobs = []
        results = None
        
        if not corpus_id and not document_id:
            results = run_neo(
                '''
                    MATCH (j:Job)
                    RETURN j
                ''', {}
            )
        elif corpus_id and not document_id:
            results = run_neo(
                '''
                    MATCH (c:Corpus { uri: $corpus_uri }) -[rel:hasJob]-> (j:Job)
                    RETURN j
                ''',
                {
                    'corpus_uri': "/corpus/{0}".format(corpus_id)
                }
            )
        elif corpus_id and document_id:
            results = run_neo(
                '''
                    MATCH (c:Corpus { uri: $corpus_uri }) -[:hasJob]-> (j:Job) <-[:hasJob]- (d:Document { uri: $document_uri })
                    return j
                ''',
                {
                    'corpus_uri': "/corpus/{0}".format(corpus_id),
                    'document_uri': "/corpus/{0}/document/{1}".format(corpus_id, document_id)
                }
            )
        
        if results:
            for result in results:
                j = Job()
                j._load_from_result(result['j'])
                jobs.append(j)
        
        return jobs


class CompletedTask(mongoengine.EmbeddedDocument):
    job_id = mongoengine.StringField()
    task = mongoengine.ReferenceField('Task')
    task_version = mongoengine.StringField()
    task_configuration = mongoengine.DictField()
    jobsite = mongoengine.ReferenceField('JobSite')
    scholar = mongoengine.ReferenceField('Scholar')
    submitted = mongoengine.DateTimeField()
    completed = mongoengine.DateTimeField()
    status = mongoengine.StringField()
    error = mongoengine.StringField()


class Corpus(mongoengine.Document):
    name = mongoengine.StringField(unique=True)
    description = mongoengine.StringField()
    uri = mongoengine.StringField(unique=True)
    path = mongoengine.StringField()
    kvp = mongoengine.DictField()
    files = mongoengine.ListField(mongoengine.EmbeddedDocumentField(File))
    document_sets = mongoengine.MapField(mongoengine.EmbeddedDocumentField('DocumentSet'))
    open_access = mongoengine.BooleanField(default=False)
    field_settings = mongoengine.DictField(default=lambda: {
        # AVAILABLE FIELD SETTING TYPES: keyword, text, integer, date
        'title': {
            "label": "Title",
            "type": "text",
            "display": True,
            "search": True,
            "sort": True,
        },
        'author': {
            "label": "Author",
            "type": "text",
            "display": True,
            "search": True,
            "sort": True
        },
        'path': {
            "label": "Path",
            "type": "text",
            "display": False,
            "search": False,
            "sort": False
        },
        'work': {
            "label": "Work",
            "type": "text",
            "display": False,
            "search": False,
            "sort": False
        },
        'expression': {
            "label": "Expression",
            "type": "text",
            "display": False,
            "search": False,
            "sort": False
        },
        'manifestation': {
            "label": "Manifestation",
            "type": "text",
            "display": False,
            "search": False,
            "sort": False
        },
        'pub_date': {
            "label": "Publication Date",
            "type": "date",
            "display": True,
            "search": True,
            "sort": True
        },
    })

    def get_document(self, document_id, only=[]):
        try:
            documents = Document.objects(id=document_id, corpus=self)
            if only:
                documents = documents.only(*only)
            return documents[0]
        except:
            return None

    def search_documents(self, q=None, search_fields=None, sort_fields=None, search_pages=False, document_id=None, start_record=0, end_record=50):
        if q or search_fields:
            index = 'corpus-{0}-documents'.format(self.id)
            should = []
            must = []
            page_query_string = None
            page_query_type = "should"

            if q and not search_fields:
                should.append(SimpleQueryString(query=q))
                if search_pages:
                    page_query_string = q
            else:
                for search_field in search_fields.keys():
                    if search_field == 'pages.contents':
                        search_pages = True
                        page_query_string = search_fields[search_field]
                        page_query_type = "must"
                    must.append(Q("match", **{search_field: search_fields[search_field]}))

            if search_pages and page_query_string:
                page_query = Q(
                    "nested",
                    path="pages",
                    query=Q(
                        "match",
                        pages__contents=page_query_string
                    ),
                    inner_hits={
                        "highlight": {
                            "fields": {
                                "pages.contents": {'fragment_size': 50}
                            }
                        },
                        "from": 0,
                        "size": 100,
                        "_source": ['pages.ref_no']
                    }
                )
                if page_query_type == 'should':
                    should.append(page_query)
                else:
                    must.append(page_query)

            if document_id:
                must.append(Q('term', _id=document_id))

            if should or must:
                query = Q('bool', should=should, must=must)

                search = Search(
                    using=get_connection(),
                    index=index
                ).query(
                    query
                ).source(
                    includes=['_id'] + [field for field, info in self.field_settings.items() if info['display']],
                ).highlight_options(order='score')

                if sort_fields:
                    search = search.sort(*sort_fields)

                search = search[start_record:end_record]

                print("Searching index {0}".format(index))
                print(json.dumps(search.to_dict(), indent=4))
                response = search.execute()
                return response.to_dict()
            else:
                print("Error constructing search query.")
                return []
        else:
            return []

    @property
    def document_index(self):
        if not hasattr(self, '_document_index') or self._document_index is None:
            self._document_index = Index('corpus-{0}-documents'.format(self.id))
        return self._document_index

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
                    mapping.field(field_name, Keyword())
                elif field_type == 'text':
                    subfields = {}
                    if field_setting['sort']:
                        subfields = { 'raw': Keyword() }
                    mapping.field(field_name, 'text', analyzer=corpora_analyzer, fields=subfields)
                elif field_type == 'integer':
                    mapping.field(field_name, Integer())
                elif field_type == 'date':
                    mapping.field(field_name, Date())

        return mapping

    def running_jobs(self):
        return Job.get_jobs(corpus_id=str(self.id))

    def rebuild_index(self):
        if self.document_index.exists():
            print("deleting corpus documents index...")
            self.document_index.delete()
            sleep(10)
            self._document_index = None
            self.document_index.mapping(self.get_document_index_mapping())
            self.document_index.save()
            corpus_documents = Document.objects(corpus=self.id)
            for corpus_document in corpus_documents:
                corpus_document.save(index_pages=True)

    def make_path(self):
        corpus_path = "/corpora/{0}".format(self.id)
        os.makedirs("{0}/files".format(corpus_path), exist_ok=True)
        return corpus_path

    def save(self, **kwargs):
        new_corpus = False
        if not self.uri:
            new_corpus = True
            self.uri = "temp-{0}".format(ObjectId())

        super().save(**kwargs)

        if new_corpus:
            self.uri = "/corpus/{0}".format(self.id)
            self.path = self.make_path()
            self.update(**{'set__uri': self.uri, 'set__path': self.path})

        # Create node in Neo4j for corpus
        run_neo('''
                MERGE (c:Corpus { uri: $corpus_uri })
                SET c.name = $corpus_title
            ''',
            {
                'corpus_uri': "/corpus/{0}".format(self.id),
                'corpus_title': self.name
            }
        )

        # Add this corpus to Corpora Elasticsearch index
        get_connection().index(
            index='corpora',
            id=str(self.id),
            body={
                'name': self.name,
                'description': self.description,
                'open_access': self.open_access
            }
        )

        # Create Elasticsearch index for documents
        if not self.document_index.exists():
            self.document_index.mapping(self.get_document_index_mapping())
            self.document_index.save()
        else:
            # TODO: check if document index mapping has been changed, and if so,
            # call manager.tasks.rebuild_document_index(corpus_id)
            pass


class Document(mongoengine.Document):
    corpus = mongoengine.ReferenceField(Corpus, required=True)
    title = mongoengine.StringField()
    uri = mongoengine.StringField(unique=True)
    path = mongoengine.StringField()
    work = mongoengine.StringField()
    expression = mongoengine.StringField()
    manifestation = mongoengine.StringField()
    author = mongoengine.StringField()
    pub_date = mongoengine.StringField()
    kvp = mongoengine.DictField()
    files = mongoengine.MapField(mongoengine.EmbeddedDocumentField(File))
    pages = mongoengine.MapField(mongoengine.EmbeddedDocumentField(Page))
    page_sets = mongoengine.MapField(mongoengine.EmbeddedDocumentField(PageSet))
    completed_tasks = mongoengine.ListField(mongoengine.EmbeddedDocumentField(CompletedTask))
    last_updated = mongoengine.DateTimeField(default=datetime.now())

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
                    'doc_uri': "/corpus/{0}/document/{1}".format(self.corpus.id, self.id)
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
                        self._page_file_collections[slug]['page_files'][ref_no] = file.to_dict()

                cache_page_file_collections(str(self.corpus.id), str(self.id), self._page_file_collections)

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
                'pfc_uri': "/corpus/{0}/document/{1}/page-file-collection/{2}".format(corpus_id, document_id, slug)
            }
        )

        if results:
            pfc = {
                'label': results[0]['pfc']['label'],
                'page_files': PageNavigator(json.loads(results[0]['pfc']['page_file_dict_json']))
            }

        return pfc

    def save_file(self, file):
        self.modify(**{'set__files__{0}'.format(file.key): file, 'set__last_updated': datetime.now()})
        file.link(corpus_id=self.corpus.pk, document_id=self.id)

    def running_jobs(self):
        return Job.get_jobs(corpus_id=str(self.corpus.id), document_id=str(self.id))

    def save_page(self, page):
        self.modify(**{'set__pages__{0}'.format(page.ref_no): page, 'set__last_updated': datetime.now()})
        page.link(corpus_id=self.corpus.id, document_id=self.id)

    def save_page_file(self, page_ref_no, file):
        self.modify(**{'set__pages__{0}__files__{1}'.format(page_ref_no, file.key): file, 'set__last_updated': datetime.now()})
        file.link(corpus_id=self.corpus.id, document_id=self.id, page_ref_no=page_ref_no)

    def make_path(self):
        breakout_dir = str(self.id)[-6:-2]
        path = "/corpora/{0}/{1}/{2}".format(self.corpus.id, breakout_dir, self.id)
        files_path = "{0}/files".format(path)
        pages_path = "{0}/pages".format(path)
        os.makedirs(files_path, exist_ok=True)
        os.makedirs(pages_path, exist_ok=True)
        return path

    def save(self, index_pages=False, perform_linking=False, **kwargs):
        self.last_updated = datetime.now()
        new_document = False
        if not self.uri:
            new_document = True
            self.uri = "temp-{0}".format(ObjectId())

        super().save(**kwargs)

        if new_document:
            self.uri = "/corpus/{0}/document/{1}".format(self.corpus.id, self.id)
            self.path = self.make_path()
            self.save()
        else:
            # Create document node and attach to corpus
            run_neo('''
                    MATCH (c:Corpus { uri: $corpus_uri })
                    MERGE (d:Document { uri: $doc_uri })
                    SET d.title = $doc_title
                    SET d.author = $doc_author
                    MERGE (c) -[rel:hasDocument]-> (d)
                ''',
                {
                    'corpus_uri': "/corpus/{0}".format(self.corpus.id),
                    'doc_uri': "/corpus/{0}/document/{1}".format(self.corpus.id, self.id),
                    'doc_title': self.title,
                    'doc_author': self.author
                }
            )

            # Index document in Elasticsearch
            default_date = datetime(1, 1, 1, 0, 0)
            body = {}
            for field_name, field_setting in self.corpus.field_settings.items():
                if field_setting['search']:
                    body[field_name] = get_field_value_from_path(self, field_name)
                    if field_setting['type'] == 'date':
                        if not body[field_name]:
                            body[field_name] = default_date
                        else:
                            body[field_name] = parser.parse(body[field_name], default=default_date)
            get_connection().index(
                index='corpus-{0}-documents'.format(self.corpus.id),
                id=str(self.id),
                body=body
            )

            # Trigger huey task for indexing document pages in Elasticsearch
            if index_pages:
                pages = {}
                for ref_no, page in self.pages.items():
                    pages[ref_no] = page.to_dict()

                index_document_pages(str(self.corpus.id), str(self.id), pages)

            if perform_linking:
                for file_key, file in self.files.items():
                    file.link(corpus_id=self.corpus.id, document_id=self.id)

                for ref_no, page in self.pages.items():
                    page.link(corpus_id=self.corpus.id, document_id=self.id)

    meta = {
        'indexes':
            [
                'corpus',
                {
                    'fields': ['corpus', 'title']
                },
                {
                    'fields': ['corpus', 'author']
                },
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
                },
                {
                    'fields': ['$title', '$author'],
                    'default_language': 'english'
                }
            ]
    }


class DocumentSet(mongoengine.EmbeddedDocument):
    documents = mongoengine.ListField(mongoengine.ReferenceField(Document))


class JobSite(mongoengine.Document):
    name = mongoengine.StringField(unique=True)
    type = mongoengine.StringField()
    job_dir = mongoengine.StringField()
    max_jobs = mongoengine.IntField(default=0)
    transfer_type = mongoengine.StringField()
    transfer_client_id = mongoengine.StringField()
    transfer_username = mongoengine.StringField()
    transfer_password = mongoengine.StringField()
    transfer_source = mongoengine.StringField()
    transfer_destination = mongoengine.StringField()
    transfer_token = mongoengine.StringField()
    refresh_token = mongoengine.StringField()
    token_expiry = mongoengine.IntField()
    task_registry = mongoengine.DictField()  # For example of how task_registry is setup, see manager/management/commands/initialize_corpora.py

    def save(self, index_pages=False, **kwargs):
        super().save(**kwargs)

        # Create jobsite node
        run_neo('''
                MERGE (js:JobSite { uri: $js_uri })
                SET js.name = $js_name
                SET js.type = $js_type
            ''',
            {
                'js_uri': "/jobsite/{0}".format(self.id),
                'js_name': self.name,
                'js_type': self.type
            }
        )

        # Create relationships with registered tasks
        for task_name, task_info in self.task_registry.items():
            run_neo('''
                    MATCH (js:JobSite { uri: $js_uri })
                    MATCH (t:Task { uri: $task_uri })
                    MERGE (js) -[:hasRegisteredTask]-> (t)
                ''',
                {
                    'js_uri': "/jobsite/{0}".format(self.id),
                    'task_uri': "/task/{0}".format(task_info['task_id']),
                    'js_type': self.type
                }
            )

    @classmethod
    def pre_delete(self, sender, document, **kwargs):
        run_neo('''
                MATCH (js:JobSite { uri: $jobsite_uri })
                DETACH DELETE js
            ''',
            {
                'jobsite_uri': "/jobsite/{0}".format(document.id),
            }
        )


class Task(mongoengine.Document):
    name = mongoengine.StringField(unique_with='jobsite_type')
    version = mongoengine.StringField()
    jobsite_type = mongoengine.StringField()
    configuration = mongoengine.DictField()

    def save(self, index_pages=False, **kwargs):
        super().save(**kwargs)

        # Create task node
        run_neo('''
                MERGE (t:Task { uri: $task_uri })
                SET t.name = $task_name
            ''',
            {
                'task_uri': "/task/{0}".format(self.id),
                'task_name': self.name
            }
        )

    @classmethod
    def pre_delete(self, sender, document, **kwargs):
        # TODO: Think through what happens when documents reference task slated for deletion as a "completed task."
        # With potentially thousands of documents referencing the task, going through every document and looking for
        # instances of this task would be very time consuming. Yet, should the task disappear due to deletion,
        # MongoEngine will throw data integrity errors :/ Thankfully, haven't had to delete any tasks yet...
        # My guess is that this will involve creating a dummy task called "Deleted Task" that gets associated with
        # completed tasks. That way, document files can still maintain provenance.

        run_neo('''
                MATCH (t:Task { uri: $task_uri })
                DETACH DELETE t
            ''',
            {
                'task_uri': "/task/{0}".format(document.id),
            }
        )


class Scholar(mongoengine.Document):
    username = mongoengine.StringField(unique=True)
    fname = mongoengine.StringField()
    lname = mongoengine.StringField()
    email = mongoengine.EmailField()
    available_corpora = mongoengine.ListField(mongoengine.LazyReferenceField(Corpus, reverse_delete_rule=mongoengine.PULL))
    available_tasks = mongoengine.ListField(mongoengine.LazyReferenceField(Task, reverse_delete_rule=mongoengine.PULL))
    available_jobsites = mongoengine.ListField(mongoengine.LazyReferenceField(JobSite, reverse_delete_rule=mongoengine.PULL))
    is_admin = mongoengine.BooleanField(default=False)
    auth_token = mongoengine.StringField(default=secrets.token_urlsafe(32))

    def save(self, index_pages=False, **kwargs):
        super().save(**kwargs)

        # Create task node
        run_neo('''
                MERGE (s:Scholar { uri: $scholar_uri })
                SET s.username = $scholar_username
                SET s.name = $scholar_name
                SET s.email = $scholar_email
                SET s.is_admin = $scholar_is_admin
            ''',
            {
                'scholar_uri': "/scholar/{0}".format(self.id),
                'scholar_username': self.username,
                'scholar_name': "{0} {1}".format(self.fname, self.lname),
                'scholar_email': self.email,
                'scholar_is_admin': self.is_admin
            }
        )

        # Wire up permissions (not relevant if user is admin)
        for corpus in self.available_corpora:
            run_neo('''
                    MATCH (s:Scholar { uri: $scholar_uri })
                    MATCH (c:Corpus { uri: $corpus_uri })
                    MERGE (s) -[:canAccess]-> (c)
                ''',
                {
                    'scholar_uri': "/scholar/{0}".format(self.id),
                    'corpus_uri': "/corpus/{0}".format(corpus.pk)
                }
            )

        for task in self.available_tasks:
            run_neo('''
                    MATCH (s:Scholar { uri: $scholar_uri })
                    MATCH (t:Task { uri: $task_uri })
                    MERGE (s) -[:canAccess]-> (t)
                ''',
                {
                    'scholar_uri': "/scholar/{0}".format(self.id),
                    'task_uri': "/task/{0}".format(task.pk)
                }
            )

        for jobsite in self.available_jobsites:
            run_neo('''
                    MATCH (s:Scholar { uri: $scholar_uri })
                    MATCH (js:JobSite { uri: $jobsite_uri })
                    MERGE (s) -[:canAccess]-> (js)
                ''',
                {
                    'scholar_uri': "/task/{0}".format(self.id),
                    'jobsite_uri': "/jobsite/{0}".format(jobsite.pk)
                }
            )

    @classmethod
    def pre_delete(self, sender, document, **kwargs):
        run_neo('''
                MATCH (s:Scholar { uri: $scholar_uri })
                DETACH DELETE s
            ''',
            {
                'scholar_uri': "/scholar/{0}".format(document.id),
            }
        )


# SIGNALS FOR HANDLING MONGOENGINE DOCUMENT PRE-DELETION (mostly for deleting Neo4J nodes)
mongoengine.signals.pre_delete.connect(Scholar.pre_delete, sender=Scholar)
mongoengine.signals.pre_delete.connect(Task.pre_delete, sender=Task)
mongoengine.signals.pre_delete.connect(JobSite.pre_delete, sender=JobSite)


# UTILITY CLASSES / FUNCTIONS
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


def process_corpus_file(path, desc=None, prov_type=None, prov_id=None, primary=False):
    file = None

    if os.path.exists(path):
        file = File()
        file.path = path
        file.primary_witness = primary
        file.basename = os.path.basename(path)
        file.extension = path.split('.')[-1].lower()
        file.byte_size = os.path.getsize(path)
        file.description = desc
        file.provenance_type = prov_type
        file.provenance_id = prov_id

        if file.extension.lower() in ['tif', 'tiff', 'jpeg', 'jpg', 'png', 'gif']:
            img = Image.open(file.path)
            file.width, file.height = img.size

    return file


def file_path_key(path):
    return zlib.compress(path.encode('utf-8')).hex()


def get_corpus(corpus_id, only=[]):
    try:
        corpus = Corpus.objects(id=corpus_id)
        if only:
            corpus = corpus.only(*only)
        return corpus[0]
    except:
        return None


def search_corpora(q, sort_fields=[], start_record=0, end_record=50):
    search = Search(
        using=get_connection(),
        index="corpora"
    ).query(
        SimpleQueryString(query=q)
    )

    if sort_fields:
        search = search.sort(*sort_fields)

    search = search[start_record:end_record]

    print("Searching index corpora")
    print(json.dumps(search.to_dict(), indent=4))
    response = search.execute()
    return response.to_dict()


def get_field_value_from_path(obj, path):
    path_parts = path.split('.')
    value = obj

    for part in path_parts:
        if hasattr(value, part):
            value = getattr(value, part)
        elif part in value:
            value = value[part]

    return value


def run_neo(cypher, params={}):
    results = None
    with settings.NEO4J.session() as neo:
        try:
            results = list(neo.run(cypher, **params))
        except:
            print("Error running Neo4J cypher!")
            print("Cypher: {0}".format(cypher))
            print("Params: {0}".format(json.dumps(params, indent=4)))
            print(traceback.format_exc())
        finally:
            neo.close()
    return results
