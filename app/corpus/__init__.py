import mongoengine
import os
import secrets
import traceback
from datetime import datetime
from bson.objectid import ObjectId
from PIL import Image
from django.conf import settings
from manager.tasks import index_document
from elasticsearch_dsl import Index, Mapping, Keyword, Text, Integer, Date, Nested
from elasticsearch_dsl.connections import get_connection


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


class Page(mongoengine.EmbeddedDocument):
    instance = mongoengine.StringField()
    label = mongoengine.StringField()
    ref_no = mongoengine.IntField()
    kvp = mongoengine.DictField()
    files = mongoengine.ListField(mongoengine.EmbeddedDocumentField(File))

    def get_file_index(self, path):
        for x in range(0, len(self.files)):
            if self.files[x].path == path:
                return x
        return -1

    def get_file(self, path):
        file_index = self.get_file_index(path)
        if file_index > -1:
            return self.files[file_index]
        return None


# TODO: evaluate the use of this model for iiif manifest view
class View(mongoengine.EmbeddedDocument):
    name = mongoengine.StringField()
    type = mongoengine.StringField()
    contents = mongoengine.StringField()
    file_collections = mongoengine.ListField(mongoengine.StringField())
    metadata = mongoengine.DictField()


class Job(mongoengine.EmbeddedDocument):
    id = mongoengine.ObjectIdField(required=True, default=lambda: ObjectId())
    document = mongoengine.ReferenceField('Document', required=True)
    name = mongoengine.StringField()
    task = mongoengine.ReferenceField('Task')
    scholar = mongoengine.ReferenceField('Scholar')
    job_site = mongoengine.ReferenceField('JobSite')
    file_transfers = mongoengine.DictField()
    transfer_code = mongoengine.StringField()
    submitted_time = mongoengine.DateTimeField(default=datetime.now())
    status = mongoengine.StringField()
    status_time = mongoengine.DateTimeField(default=datetime.now())
    processes = mongoengine.ListField()
    processes_completed = mongoengine.ListField()
    stage = mongoengine.IntField(default=0)
    tries = mongoengine.IntField()
    error = mongoengine.StringField()
    configuration = mongoengine.DictField()

    def add_file_transfer(self, path, type):
        if path not in self.file_transfers:
            self.file_transfers[path] = {'type': type, 'status': 'queued'}
        else:
            self.file_transfers[path]['status'] = 'queued'


class Corpus(mongoengine.Document):
    name = mongoengine.StringField(unique=True)
    description = mongoengine.StringField()
    path = mongoengine.StringField()
    kvp = mongoengine.DictField()
    files = mongoengine.ListField(mongoengine.EmbeddedDocumentField(File))
    jobs = mongoengine.ListField(mongoengine.EmbeddedDocumentField(Job))
    open_access = mongoengine.BooleanField(default=False)
    field_settings = mongoengine.ListField(default=lambda: [
        # AVAILABLE FIELD SETTING TYPES: keyword, text, integer, date
        {
            "field": "title",
            "label": "Title",
            "display": True,
            "type": "text",
            "search": True,
            "sort": True,
        },
        {
            "field": "author",
            "label": "Author",
            "display": True,
            "type": "text",
            "search": True,
            "sort": True
        },
        {
            "field": "path",
            "label": "Path",
            "display": False,
            "search": False
        },
        {
            "field": "work",
            "label": "Work",
            "display": False,
            "search": False
        },
        {
            "field": "expression",
            "label": "Expression",
            "display": False,
            "search": False
        },
        {
            "field": "manifestation",
            "label": "Manifestation",
            "display": False,
            "search": False
        },
        {
            "field": "pub_date",
            "label": "Publication Date",
            "display": True,
            "type": "date",
            "search": True
        },
    ])

    def get_document(self, document_id):
        try:
            document = Document.objects(id=document_id, corpus=self)[0]
            return document
        except:
            return None

    def get_job_index(self, job_id):
        for x in range(0, len(self.jobs)):
            if self.jobs[x].id == ObjectId(job_id):
                return x
        return -1

    def get_job(self, job_id):
        job_index = self.get_job_index(job_id)
        if job_index > -1:
            return self.jobs[job_index]
        return None

    def save_job(self, job):
        job_index = self.get_job_index(job.id)
        if job_index > -1:
            self.update(**{'set__jobs__{0}'.format(str(job_index)): job})
        else:
            self.update(push__jobs=job)

    def complete_job_process(self, job_id, process_id):
        job_index = self.get_job_index(job_id)
        if job_index > -1:
            self.update(**{'push__jobs__{0}__processes_completed'.format(str(job_index)): process_id})

    def complete_job(self, job):
        self.update(pull__jobs=job)
        job.status = 'complete'
        job.document.update(push__jobs=job)

    @property
    def document_index(self):
        if not hasattr(self, '_document_index'):
            self._document_index = Index('/corpus/{0}/documents'.format(self.id))
        return self._document_index

    def get_document_index_mapping(self):
        mapping = Mapping()
        mapping.field('document_id', Keyword())

        page_field = Nested(
            properties={
                'ref_no': Integer(),
                'content': Text()
            }
        )
        mapping.field('pages', page_field)

        for field_setting in self.field_settings:
            if field_setting['search']:
                field_type = field_setting.get('type', 'keyword')
                if field_type not in ['keyword', 'text', 'integer', 'date']:
                    field_type = 'keyword'
                if field_type == 'keyword':
                    mapping.field(field_setting['field'], Keyword())
                elif field_type == 'text':
                    subfields = {}
                    if field_setting['sort']:
                        subfields = { 'raw': Keyword() }
                    mapping.field(field_setting['field'], Text(), fields=subfields)
                elif field_type == 'integer':
                    mapping.field(field_setting['field'], Integer())
                elif field_type == 'date':
                    mapping.field(field_setting['field'], Date())

        return mapping

    def save(self, **kwargs):
        super().save(**kwargs)

        # Create node in Neo4j for corpus
        run_neo('''
                MERGE (c:Corpus { key: $corpus_key })
                SET c.name = $corpus_title
            ''',
            {
                'corpus_key': "/corpus/{0}".format(self.id),
                'corpus_title': self.name
            }
        )

        # Add this corpus to Corpora Elasticsearch index
        get_connection().index(
            index='/corpora',
            id=str(self.id),
            body={
                'corpus_id': str(self.id),
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

    meta = {
        'indexes':
            [
                {
                    'fields': ['jobs.status'],
                    'sparse': True
                }
            ]
    }


class Document(mongoengine.Document):
    corpus = mongoengine.ReferenceField(Corpus, required=True)
    title = mongoengine.StringField()
    path = mongoengine.StringField(unique=True)
    work = mongoengine.StringField()
    expression = mongoengine.StringField()
    manifestation = mongoengine.StringField()
    author = mongoengine.StringField()
    pub_date = mongoengine.StringField()
    kvp = mongoengine.DictField()
    files = mongoengine.ListField(mongoengine.EmbeddedDocumentField(File))
    pages = mongoengine.ListField(mongoengine.EmbeddedDocumentField(Page))
    views = mongoengine.ListField(mongoengine.EmbeddedDocumentField(View))
    jobs = mongoengine.ListField(mongoengine.EmbeddedDocumentField(Job))

    @property
    def page_file_collections(self):
        # TODO: build page file collections in neo; try querying neo first. will help scale large numbers of file types.
        # maybe also build an "events" or "provenance" aparatus at doc level, also queried first by neo but with a refresh
        # that can be triggered by a flag in doc.kvp

        if '_page_file_collections' not in self.kvp or self.kvp.get('_reload_page_file_collections', False):
            collections = {}
            collection_counter = 0

            for page in self.pages:
                for file in page.files:
                    collection_key = ""
                    if file.primary_witness:
                        collection_key += "Primary "
                    collection_key = "{0}{1} from {2} ({3})".format(collection_key, file.description,
                                                                    file.provenance_type, file.provenance_id).strip()
                    if collection_key not in collections:
                        collection_counter += 1
                        collections[collection_key] = {
                            'provenance_type': file.provenance_type,
                            'provenance_id': file.provenance_id,
                            'description': file.description,
                            'files': [],
                            'collection_counter': collection_counter
                        }
                    collections[collection_key]['files'].append({
                        'page': page.ref_no,
                        'path': file.path,
                        'basename': file.basename,
                        'extension': file.extension,
                        'byte_size': file.byte_size,
                        'height': getattr(file, 'height', ''),
                        'width': getattr(file, 'width', '')
                    })

            self.kvp['_page_file_collections'] = collections
            self.update(**{"set__kvp___page_file_collections": collections})
            self.update(**{"set__kvp___reload_page_file_collections": False})

        return self.kvp['_page_file_collections']

    def get_file_index(self, path):
        for x in range(0, len(self.files)):
            if self.files[x].path == path:
                return x
        return -1

    def get_file(self, path):
        file_index = self.get_file_index(path)
        if file_index > -1:
            return self.files[file_index]
        return None

    def save_file(self, file):
        file_index = self.get_file_index(file.path)
        if file_index > -1:
            self.update(**{'set__files__{0}'.format(str(file_index)): file})
        else:
            self.update(push__files=file)

        run_neo('''
                MATCH (d:Document { key: $doc_key })
                MERGE (f:File { key: $file_key })
                SET f.primary_witness = $file_primary_witness
                SET f.description = $file_description
                SET f.index = $file_index
                MERGE (d) -[rel:hasFile]-> (f)
            ''',
            {
                'doc_key': "/corpus/{0}/document/{1}".format(self.corpus.id, self.id),
                'file_key': file.path,
                'file_primary_witness': file.primary_witness,
                'file_description': file.description,
                'file_index': file_index
            }
        )

        # TODO: huey task for indexing file contents?

    def get_page_index(self, ref_no):
        for x in range(0, len(self.pages)):
            if self.pages[x].ref_no == ref_no:
                return x
        return -1

    def get_page(self, ref_no):
        page_index = self.get_page_index(int(ref_no))
        if page_index > -1:
            return self.pages[page_index]
        return None

    def save_page(self, page):
        page_index = self.get_page_index(page.ref_no)
        if page_index > -1:
            self.update(**{'set__pages__{0}'.format(page_index): page})
        else:
            self.update(push__pages=page)

        run_neo('''
                MATCH (d:Document { key: $doc_key })
                MERGE (p:Page { key: $page_key })
                SET p.label = $page_label
                SET p.ref_no = $page_ref_no
                SET p.index = $page_index
                MERGE (d) -[rel:hasPage]-> (p) 
            ''',
            {
                'doc_key': "/corpus/{0}/document/{1}".format(self.corpus.id, self.id),
                'page_key': "/corpus/{0}/document/{1}/page/{2}".format(self.corpus.id, self.id, page.ref_no),
                'page_label': page.label if page.label else str(page.ref_no),
                'page_ref_no': page.ref_no,
                'page_index': page_index
            }
        )

        self.update(**{'set__kvp___reload_page_file_collections': True})

    def save_page_file(self, page_ref_no, file):
        page_index = self.get_page_index(int(page_ref_no))
        if page_index > -1:
            file_index = self.pages[page_index].get_file_index(file.path)
            if file_index > -1:
                self.update(**{'set__pages__{0}__files__{1}'.format(str(page_index), str(file_index)): file})
            else:
                self.update(**{'push__pages__{0}__files'.format(str(page_index)): file})

            run_neo('''
                    MATCH (p:Page { key: $page_key })
                    MERGE (f:File { key: $file_key })
                    SET p.index = $page_index
                    SET f.primary_witness = $file_primary_witness
                    SET f.description = $file_description
                    SET f.index = $file_index
                    MERGE (p) -[rel:hasFile]-> (f)
                ''',
                {
                    'page_key': "/corpus/{0}/document/{1}/page/{2}".format(self.corpus.id, self.id, page_ref_no),
                    'page_index': page_index,
                    'file_key': file.path,
                    'file_primary_witness': file.primary_witness,
                    'file_description': file.description,
                    'file_index': file_index
                }
            )

            self.update(**{'set__kvp___reload_page_file_collections': True})

            # TODO: huey task for indexing file contents?

    def sort_pages(self):
        self.pages = sorted(self.pages, key=lambda p: p.ref_no)
        self.save()

    def save(self, index=True, **kwargs):
        super().save(**kwargs)

        # Create document node and attach to corpus
        run_neo('''
                MATCH (c:Corpus { key: $corpus_key })
                MERGE (d:Document { key: $doc_key })
                SET d.title = $doc_title
                SET d.author = $doc_author
                MERGE (c) -[rel:hasDocument]-> (d)
            ''',
            {
                'corpus_key': "/corpus/{0}".format(self.corpus.id),
                'doc_key': "/corpus/{0}/document/{1}".format(self.corpus.id, self.id),
                'doc_title': self.title,
                'doc_author': self.author
            }
        )

        # Trigger indexing of document in Elasticsearch
        if index:
            index_document(str(self.corpus.id), str(self.id))

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
                    'fields': ['id', 'views.type', 'views.name'],
                    'unique': True,
                    'sparse': True
                },
                {
                    'fields': ['$title', '$author'],
                    'default_language': 'english'
                }
            ]
    }


class DocumentSet(mongoengine.Document):
    corpus = mongoengine.ReferenceField(Corpus)
    name = mongoengine.StringField(unique_with=['corpus'])
    documents = mongoengine.ListField(mongoengine.ReferenceField(Document, reverse_delete_rule=mongoengine.PULL))


class PageSet(mongoengine.Document):
    corpus = mongoengine.ReferenceField(Corpus)
    name = mongoengine.StringField(unique_with=['corpus'])
    pages = mongoengine.ListField(mongoengine.DictField())


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
    task_registry = mongoengine.DictField()  # { 'Import Document Pages from PDF': {'task_id': '', 'python': 'extract_pdf_pages(corpus_id, job_id)' }


class Task(mongoengine.Document):
    name = mongoengine.StringField(unique_with='jobsite_type')
    version = mongoengine.StringField()
    jobsite_type = mongoengine.StringField()
    configuration = mongoengine.DictField()


class Scholar(mongoengine.Document):
    username = mongoengine.StringField(unique=True)
    fname = mongoengine.StringField()
    lname = mongoengine.StringField()
    email = mongoengine.EmailField()
    available_corpora = mongoengine.ListField(mongoengine.ReferenceField(Corpus, reverse_delete_rule=mongoengine.PULL))
    available_tasks = mongoengine.ListField(mongoengine.ReferenceField(Task, reverse_delete_rule=mongoengine.PULL))
    available_jobsites = mongoengine.ListField(
        mongoengine.ReferenceField(JobSite, reverse_delete_rule=mongoengine.PULL))
    is_admin = mongoengine.BooleanField(default=False)
    auth_token = mongoengine.StringField(default=secrets.token_urlsafe(32))


# UTILITY FUNTIONS

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


def get_corpus(corpus_id):
    try:
        corpus = Corpus.objects(id=corpus_id)[0]
        return corpus
    except:
        return None


def run_neo(cypher, params={}):
    results = None
    with settings.NEO4J.session() as neo:
        try:
            print(cypher)
            results = list(neo.run(cypher, **params))
        except:
            print(traceback.format_exc())
        finally:
            neo.close()
