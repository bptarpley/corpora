import mongoengine
import os
import json
import secrets
import traceback
import importlib
import zlib
import shutil
from math import ceil
from copy import deepcopy
from datetime import datetime, timezone
from dateutil import parser
from bson.objectid import ObjectId
from bson import DBRef
from PIL import Image
from django.conf import settings
from elasticsearch_dsl import Index, Mapping, analyzer, Keyword, Text, Integer, Date, \
    Nested, char_filter, Q, Search
from elasticsearch_dsl.query import SimpleQueryString
from elasticsearch_dsl.connections import get_connection
from django.template import Template, Context


FIELD_TYPES = ('text', 'keyword', 'html', 'choice', 'number', 'date', 'file', 'link', 'cross_reference', 'embedded')
MIME_TYPES = ('text/html', 'text/xml', 'application/json')


class Field(mongoengine.EmbeddedDocument):
    name = mongoengine.StringField(required=True)
    label = mongoengine.StringField()
    indexed = mongoengine.BooleanField(default=False)
    unique = mongoengine.BooleanField(default=False)
    multiple = mongoengine.BooleanField(default=False)
    in_lists = mongoengine.BooleanField(default=True)
    type = mongoengine.StringField(choices=FIELD_TYPES)
    choices = mongoengine.ListField()
    cross_reference_type = mongoengine.StringField()
    indexed_with = mongoengine.ListField()
    unique_with = mongoengine.ListField()
    stats = mongoengine.DictField()
    inherited = mongoengine.BooleanField(default=False)

    def get_dict_value(self, value, parent_uri):
        dict_value = None

        if self.multiple:
            if self.type == 'embedded' and hasattr(value, 'keys'):
                dict_value = {}
                for key in value.keys():
                    dict_value[key] = self.to_primitive(value[key], parent_uri)
            else:
                dict_value = []
                for val in value:
                    dict_value.append(self.to_primitive(val, parent_uri))
        else:
            dict_value = self.to_primitive(value, parent_uri)

        return dict_value

    def to_primitive(self, value, parent_uri):
        if value:
            if self.type == 'date':
                dt = datetime.combine(value, datetime.min.time())
                return int(dt.timestamp())
            elif self.type == 'cross_reference':
                return value.to_dict(ref_only=True)
            elif self.type == 'embedded':
                return value.to_dict(parent_uri)
            elif self.type == 'file':
                return value.to_dict(parent_uri)
        return value
    
    def get_mongoengine_field_class(self):
        if self.type == 'number':
            if self.unique and not self.unique_with:
                return mongoengine.IntField(unique=True)
            else:
                return mongoengine.IntField()
        elif self.type == 'date':
            if self.unique and not self.unique_with:
                return mongoengine.DateField(unique=True)
            else:
                return mongoengine.DateField()
        elif self.type == 'file':
            return mongoengine.EmbeddedDocumentField(File)
        elif self.type != 'cross_reference':
            if self.unique and not self.unique_with:
                return mongoengine.StringField(unique=True)
            else:
                return mongoengine.StringField()

    def to_dict(self):
        return {
            'name': self.name,
            'label': self.label,
            'indexed': self.indexed,
            'unique': self.unique,
            'multiple': self.multiple,
            'in_lists': self.in_lists,
            'type': self.type,
            'choices': [choice for choice in self.choices],
            'cross_reference_type': self.cross_reference_type,
            'indexed_with': [index for index in self.indexed_with],
            'unique_with': [unq for unq in self.unique_with],
            'stats': deepcopy(self.stats),
            'inherited': self.inherited
        }


class Task(mongoengine.Document):
    name = mongoengine.StringField(unique_with='jobsite_type')
    version = mongoengine.StringField()
    jobsite_type = mongoengine.StringField()
    content_type = mongoengine.StringField(default="Corpus")
    track_provenance = mongoengine.BooleanField(default=True)
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
    def _post_delete(self, sender, document, **kwargs):
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

    meta = {
        'indexes': [
            'content_type'
        ]
    }


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
    def _post_delete(self, sender, document, **kwargs):
        run_neo('''
                MATCH (js:JobSite { uri: $jobsite_uri })
                DETACH DELETE js
            ''',
            {
                'jobsite_uri': "/jobsite/{0}".format(document.id),
            }
        )


class Job(object):
    def __init__(self, id=None):
        if id:
            self._load(id)
        else:
            self.id = None
            self.corpus_id = None
            self.content_type = None
            self.content_id = None
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
        self.content_type = result['content_type']
        self.content_id = result['content_id']
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
        if not self.content_id and self.content_type == 'Corpus':
            run_neo(
                '''
                    MATCH (c:Corpus {{ uri: $corpus_uri }})
                    MERGE (j:Job {{ uri: $job_uri }})
                    SET j.corpus_id = $job_corpus_id
                    SET j.content_type = $job_content_type
                    SET j.content_id = $job_content_id
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
                    MERGE (c) -[:hasJob]-> (j)
                '''.format(self.content_type),
                {
                    'corpus_uri': "/corpus/{0}".format(self.corpus_id),
                    'job_uri': "/job/{0}".format(self.id),
                    'job_corpus_id': self.corpus_id,
                    'job_content_type': self.content_type,
                    'job_content_id': self.content_id,
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
        else:
            run_neo(
                '''
                    MATCH (c:Corpus {{ uri: $corpus_uri }})
                    MATCH (d:{0} {{ uri: $content_uri }})
                    MERGE (j:Job {{ uri: $job_uri }})
                    SET j.corpus_id = $job_corpus_id
                    SET j.content_type = $job_content_type
                    SET j.content_id = $job_content_id
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
                '''.format(self.content_type),
                {
                    'corpus_uri': "/corpus/{0}".format(self.corpus_id),
                    'content_uri': "/corpus/{0}/{1}/{2}".format(self.corpus_id, self.content_type, self.content_id),
                    'job_uri': "/job/{0}".format(self.id),
                    'job_corpus_id': self.corpus_id,
                    'job_content_type': self.content_type,
                    'job_content_id': self.content_id,
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
            'content_type': self.content_type,
            'content_id': self.content_id,
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
    def content(self):
        if not hasattr(self, '_content'):
            if self.content_type == 'Corpus':
                return self.corpus
            else:
                self._content = self.corpus.get_content(self.content_type, self.content_id)
        return self._content

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

        if self.task.track_provenance:
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

            self.content.provenance.append(ct)
            self.content.save()

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
    def setup_retry_for_completed_task(corpus_id, content_type, content_id, completed_task):
        j = Job()
        j.id = completed_task.job_id
        j.corpus_id = corpus_id
        j.content_type = content_type
        j.content_id = content_id
        j.task_id = str(completed_task.task.id)
        j.jobsite_id = str(completed_task.jobsite.id)
        j.scholar_id = str(completed_task.scholar.id)
        j.configuration = deepcopy(completed_task.task_configuration)
        j.status = 'preparing'
        j.save()
        return j

    @staticmethod
    def get_jobs(corpus_id=None, content_type=None, content_id=None):
        jobs = []
        results = None

        if not corpus_id and not content_type and not content_id:
            results = run_neo(
                '''
                    MATCH (j:Job)
                    RETURN j
                ''', {}
            )
        elif corpus_id and not content_type:
            results = run_neo(
                '''
                    MATCH (c:Corpus { uri: $corpus_uri }) -[rel:hasJob]-> (j:Job)
                    RETURN j
                ''',
                {
                    'corpus_uri': "/corpus/{0}".format(corpus_id)
                }
            )
        elif corpus_id and content_type and content_id:
            results = run_neo(
                '''
                    MATCH (c:Corpus {{ uri: $corpus_uri }}) -[:hasJob]-> (j:Job) <-[:hasJob]- (d:{0} {{ uri: $content_uri }})
                    return j
                '''.format(content_type),
                {
                    'corpus_uri': "/corpus/{0}".format(corpus_id),
                    'content_uri': "/corpus/{0}/{1}/{2}".format(corpus_id, content_type, content_id)
                }
            )

        if results:
            for result in results:
                j = Job()
                j._load_from_result(result['j'])
                jobs.append(j)

        return jobs


class Scholar(mongoengine.Document):
    username = mongoengine.StringField(unique=True)
    fname = mongoengine.StringField()
    lname = mongoengine.StringField()
    email = mongoengine.EmailField()
    available_corpora = mongoengine.ListField(mongoengine.LazyReferenceField('Corpus'))
    available_tasks = mongoengine.ListField(mongoengine.LazyReferenceField(Task, reverse_delete_rule=mongoengine.PULL))
    available_jobsites = mongoengine.ListField(mongoengine.LazyReferenceField(JobSite, reverse_delete_rule=mongoengine.PULL))
    is_admin = mongoengine.BooleanField(default=False)
    auth_token = mongoengine.StringField(default=secrets.token_urlsafe(32))
    auth_token_ips = mongoengine.ListField(mongoengine.StringField())

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
            run_neo(
                '''
                    MATCH (s:Scholar { uri: $scholar_uri })
                    MATCH (c:Corpus { uri: $corpus_uri })
                    MERGE (s) -[:canAccess]-> (c)
                ''',
                {
                    'scholar_uri': "/scholar/{0}".format(self.id),
                    'corpus_uri': "/corpus/{0}".format(corpus.pk)
                }
            )

    def get_preference(self, content_type, content_uri, preference):
        results = run_neo(
            '''
                MATCH (s:Scholar {{ uri: $scholar_uri }}) -[prefs:hasPreferences]-> (c:{content_type} {{ uri: $content_uri }})
                RETURN prefs.{preference} as preference
            '''.format(content_type=content_type, preference=preference),
            {
                'scholar_uri': "/scholar/{0}".format(self.id),
                'content_uri': content_uri
            }
        )

        if results and 'preference' in results[0].keys():
            return results[0]['preference']
        return None

    def set_preference(self, content_type, content_uri, preference, value):
        run_neo(
            '''
                MATCH (s:Scholar {{ uri: $scholar_uri }})
                MATCH (c:{content_type} {{ uri: $content_uri }})
                MERGE (s) -[prefs:hasPreferences]-> (c) 
                SET prefs.{preference} = $value
            '''.format(content_type=content_type, preference=preference),
            {
                'scholar_uri': "/scholar/{0}".format(self.id),
                'content_uri': content_uri,
                'value': value
            }
        )

    @classmethod
    def _post_delete(cls, sender, document, **kwargs):
        run_neo('''
                MATCH (s:Scholar { uri: $scholar_uri })
                DETACH DELETE s
            ''',
            {
                'scholar_uri': "/scholar/{0}".format(document.id),
            }
        )


class CompletedTask(mongoengine.EmbeddedDocument):
    job_id = mongoengine.StringField()
    task = mongoengine.ReferenceField(Task)
    task_version = mongoengine.StringField()
    task_configuration = mongoengine.DictField()
    jobsite = mongoengine.ReferenceField(JobSite)
    scholar = mongoengine.ReferenceField(Scholar)
    submitted = mongoengine.DateTimeField()
    completed = mongoengine.DateTimeField()
    status = mongoengine.StringField()
    error = mongoengine.StringField()

    def to_dict(self):
        return {
            'job_id': self.job_id,
            'task_id': str(self.task.id),
            'task_name': str(self.task.name),
            'task_configuration': deepcopy(self.task_configuration),
            'jobsite_id': str(self.jobsite.id),
            'scholar_id': str(self.scholar.id),
            'scholar_name': "{0} {1}".format(self.scholar.fname, self.scholar.lname),
            'submitted': int(self.submitted.timestamp()),
            'completed': int(self.completed.timestamp()),
            'status': self.status,
            'error': self.error
        }


class ContentTemplate(mongoengine.EmbeddedDocument):
    template = mongoengine.StringField()
    mime_type = mongoengine.StringField(choices=MIME_TYPES)

    def to_dict(self):
        return {
            'template': self.template,
            'mime_type': self.mime_type
        }


class ContentType(mongoengine.EmbeddedDocument):
    name = mongoengine.StringField(required=True)
    plural_name = mongoengine.StringField(required=True)
    fields = mongoengine.EmbeddedDocumentListField('Field')
    show_in_nav = mongoengine.BooleanField(default=True)
    proxy_field = mongoengine.StringField()
    templates = mongoengine.MapField(mongoengine.EmbeddedDocumentField(ContentTemplate))
    inherited_from_module = mongoengine.StringField()
    inherited_from_class = mongoengine.StringField()
    base_mongo_indexes = mongoengine.StringField()
    has_file_field = mongoengine.BooleanField()
    invalid_field_names = mongoengine.ListField(mongoengine.StringField())

    def get_field(self, field_name):
        for index in range(0, len(self.fields)):
            if self.fields[index].name == field_name:
                return self.fields[index]
        return None

    def get_mongoengine_class(self, corpus):
        class_dict = {
            '_ct': self,
            '_corpus': corpus
        }

        indexes = []
        if self.base_mongo_indexes:
            indexes = json.loads(self.base_mongo_indexes)

        for field in self.fields:
            if not field.inherited:
                if field.type == 'cross_reference':
                    if field.cross_reference_type == self.name:
                        xref_class = self.name
                    else:
                        xref_class = corpus.content_types[field.cross_reference_type].get_mongoengine_class(corpus)

                    if field.unique and not field.unique_with:
                        class_dict[field.name] = mongoengine.ReferenceField(xref_class, unique=True)
                    else:
                        class_dict[field.name] = mongoengine.ReferenceField(xref_class)
                else:
                    class_dict[field.name] = field.get_mongoengine_field_class()

                if field.unique_with:
                    indexes.append({
                        'fields': [field.name] + [unique_with for unique_with in field.unique_with],
                        'unique': True,
                        'sparse': True
                    })

                if field.indexed:
                    if field.indexed_with:
                        indexes.append({
                            'fields': [field.name] + [indexed_with for indexed_with in field.indexed_with],
                        })
                    else:
                        indexes.append(field.name)

                if field.multiple:
                    class_dict[field.name] = mongoengine.ListField(class_dict[field.name])

        class_dict['meta'] = {
            'indexes': indexes,
            'collection': "corpus_{0}_{1}".format(corpus.id, self.name)
        }

        ct_class = Content

        if self.inherited_from_class:
            ct_module = importlib.import_module(self.inherited_from_module)
            ct_class = getattr(ct_module, self.inherited_from_class)

        ct_class = type(
            self.name,
            (ct_class,),
            class_dict
        )

        mongoengine.signals.pre_save.connect(ct_class._pre_save, sender=ct_class)

        return ct_class

    def to_dict(self):
        ct_dict = {
            'name': self.name,
            'plural_name': self.plural_name,
            'fields': [field.to_dict() for field in self.fields],
            'show_in_nav': self.show_in_nav,
            'proxy_field': self.proxy_field,
            'templates': {},
            'inherited': True if self.inherited_from_module else False,
            'invalid_field_names': deepcopy(self.invalid_field_names)
        }

        for template_name in self.templates:
            ct_dict['templates'][template_name] = self.templates[template_name].to_dict()

        return ct_dict


class File(mongoengine.EmbeddedDocument):

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
            self._key = self.generate_key(self.path)
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

    @property
    def is_image(self):
        return self.extension in settings.VALID_IMAGE_EXTENSIONS

    def _do_linking(self, content_type, content_uri):

        run_neo(
            '''
                MATCH (n:{content_type} {{ uri: $content_uri }})
                MERGE (f:File {{ uri: $file_uri }})
                SET f.path = $file_path
                SET f.is_image = $is_image
                MERGE (n) -[rel:hasFile]-> (f)
            '''.format(content_type=content_type),
            {
                'content_uri': content_uri,
                'file_uri': "{0}/file/{1}".format(content_uri, self.key),
                'file_path': self.path,
                'is_image': self.is_image
            }
        )

    def _unlink(self, content_uri):
        run_neo(
            '''
                MATCH (f:File { uri: $file_uri })
                DETACH DELETE f
            ''',
            {
                'file_uri': "{0}/file/{1}".format(content_uri, self.key)
            }
        )

    @classmethod
    def process(cls, path, desc=None, prov_type=None, prov_id=None, primary=False):
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

    @classmethod
    def generate_key(cls, path):
        return zlib.compress(path.encode('utf-8')).hex()

    def to_dict(self, parent_uri):
        return {
            'uri': "{0}/file/{1}".format(parent_uri, self.key),
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
            'iiif_info': self.iiif_info,
            'collection_label': self.collection_label
        }


class Corpus(mongoengine.Document):
    name = mongoengine.StringField(unique=True)
    description = mongoengine.StringField()
    uri = mongoengine.StringField(unique=True)
    path = mongoengine.StringField()
    kvp = mongoengine.DictField()
    files = mongoengine.MapField(mongoengine.EmbeddedDocumentField(File))
    open_access = mongoengine.BooleanField(default=False)
    content_types = mongoengine.MapField(mongoengine.EmbeddedDocumentField(ContentType))
    provenance = mongoengine.EmbeddedDocumentListField(CompletedTask)

    def save_file(self, file):
        self.modify(**{'set__files__{0}'.format(file.key): file})
        file._do_linking(content_type='Corpus', content_uri=self.uri)

    def get_content(self, content_type, content_id_or_query={}, only=[], all=False):
        content = None
        single_result = False

        if content_type in self.content_types:
            content_obj = self.content_types[content_type].get_mongoengine_class(self)

            if content_id_or_query or all:
                if type(content_id_or_query) is str or type(content_id_or_query) is ObjectId:
                    single_result = True
                    content_id_or_query = {'id': content_id_or_query}

                try:
                    content = content_obj.objects(**content_id_or_query)
                    if only:
                        content = content.only(*only)
                    if single_result:
                        content = content[0]
                except:
                    print("Error retrieving content:")
                    print(traceback.format_exc())
                    return None
            else:
                content = content_obj()
                content.corpus_id = str(self.id)
                content.content_type = content_type

        return content

    def get_content_dbref(self, content_type, content_id):
        if not type(content_id) == ObjectId:
            content_id = ObjectId(content_id)
        return DBRef(
            "corpus_{0}_{1}".format(self.id, content_type),
            content_id
        )

    def search_content(self, content_type, page=1, page_size=50, general_query="", fields_query=[], fields_sort=[], only=[]):
        results = {
            'meta': {
                'content_type': content_type,
                'total': 0,
                'page': page,
                'page_size': page_size,
                'num_pages': 1,
                'has_next_page': False
            },
            'records': []
        }

        if content_type in self.content_types:
            start_index = (page - 1) * page_size
            end_index = page * page_size

            index_name = "corpus-{0}-{1}".format(self.id, content_type.lower())
            index = Index(index_name)
            should = []
            must = []
            if general_query and not fields_query:
                should.append(SimpleQueryString(query=general_query))

            if fields_query:
                for search_field in fields_query.keys():
                    if '.' in search_field:
                        field_parts = search_field.split('.')
                        must.append(Q(
                            "nested",
                            path=field_parts[0],
                            query=Q(
                                "match_phrase",
                                **{search_field: fields_query[search_field]}
                            )
                        ))
                    else:
                        must.append(Q("match_phrase", **{search_field: fields_query[search_field]}))

            if general_query and fields_query:
                must.append(SimpleQueryString(query=general_query))

            if should or must:
                search_query = Q('bool', should=should, must=must)

                extra = {'track_total_hits': True}

                search_cmd = Search(using=get_connection(), index=index_name, extra=extra).query(search_query)

                if only:
                    if '_id' not in only:
                        only.append('_id')
                    search_cmd = search_cmd.source(includes=only)

                if fields_sort:
                    adjusted_fields_sort = []
                    mappings = index.get()[index_name]['mappings']['properties']
                    for x in range(0, len(fields_sort)):
                        field_name = list(fields_sort[x].keys())[0]
                        sort_direction = fields_sort[x][field_name]
                        subfield_name = None

                        if '.' in field_name:
                            field_parts = field_name.split('.')
                            field_name = field_parts[0]
                            subfield_name = field_parts[1]

                        if field_name in mappings:
                            field_type = mappings[field_name]['type']
                            if field_type == 'nested' and subfield_name:
                                field_type = mappings[field_name]['properties'][subfield_name]['type']

                            if subfield_name:
                                full_field_name = '{0}.{1}'.format(field_name, subfield_name)
                                adjusted_fields_sort.append({
                                    full_field_name + '.raw' if field_type == 'text' else full_field_name: {
                                        'order': sort_direction['order'],
                                        'nested_path': field_name
                                    }
                                })
                            else:
                                adjusted_fields_sort.append({
                                    field_name + '.raw' if field_type == 'text' else field_name: sort_direction
                                })

                    search_cmd = search_cmd.sort(*adjusted_fields_sort)

                search_cmd = search_cmd[start_index:end_index]
                print(json.dumps(search_cmd.to_dict(), indent=4))
                search_results = search_cmd.execute().to_dict()
                print(json.dumps(search_results, indent=4))
                results['meta']['total'] = search_results['hits']['total']['value']
                results['meta']['num_pages'] = ceil(results['meta']['total'] / results['meta']['page_size'])
                results['meta']['has_next_page'] = results['meta']['page'] < results['meta']['num_pages']

                for hit in search_results['hits']['hits']:
                    record = deepcopy(hit['_source'])
                    record['id'] = hit['_id']
                    record['_search_score'] = hit['_score']
                    results['records'].append(record)

        return results

    def save_content_type(self, schema):
        valid = True
        existing = False
        had_file_field = False
        reindex = False
        relabel = False
        resave = False
        queued_job_ids = []
        ct_name = schema['name']

        default_field_values = {
            'show_in_nav': True,
            'in_lists': True,
            'indexed': False,
            'indexed_with': [],
            'unique': False,
            'unique_with': [],
            'multiple': False,
            'proxy_field': "",
            'inherited': False,
            'cross_reference_type': '',
        }

        default_invalid_field_names = [
            'corpus_id',
            'content_type',
            'last_updated',
            'provenance',
            'path',
            'label',
            'uri',
        ]

        invalid_field_names = deepcopy(default_invalid_field_names)
        if 'invalid_field_names' in schema:
            invalid_field_names += schema['invalid_field_names']

        # NEW CONTENT TYPE
        if ct_name not in self.content_types:
            new_content_type = ContentType()
            new_content_type.name = schema['name']
            new_content_type.plural_name = schema['plural_name']
            new_content_type.show_in_nav = schema['show_in_nav']
            new_content_type.proxy_field = schema['proxy_field']
            new_content_type.invalid_field_names = invalid_field_names

            if 'templates' in schema:
                for template_name in schema['templates']:
                    template = ContentTemplate()
                    template.template = schema['templates'][template_name]['template']
                    template.mime_type = schema['templates'][template_name]['mime_type']
                    new_content_type.templates[template_name] = template

            if 'inherited_from_module' in schema and 'inherited_from_class' in schema:
                new_content_type.inherited_from_module = schema['inherited_from_module']
                new_content_type.inherited_from_class = schema['inherited_from_class']

                if 'base_mongo_indexes' in schema:
                    new_content_type.base_mongo_indexes = json.dumps(schema['base_mongo_indexes'])

            for field_dict in schema['fields']:
                if field_dict['name'] in invalid_field_names or field_dict['name'].startswith('_'):
                    print("Invalid field name: {0}".format(field_dict['name']))
                    valid = False
                else:
                    field = default_field_values.copy()
                    field.update(field_dict)

                    new_field = Field()
                    new_field.name = field['name']
                    new_field.label = field['label']
                    new_field.in_lists = field['in_lists']
                    new_field.indexed = field['indexed']
                    new_field.indexed_with = field['indexed_with']
                    new_field.unique = field['unique']
                    new_field.unique_with = field['unique_with']
                    new_field.multiple = field['multiple']
                    new_field.type = field['type']
                    new_field.cross_reference_type = field['cross_reference_type']
                    new_field.inherited = field['inherited']

                    if new_field.type == 'embedded':
                        new_field.in_lists = False

                    new_content_type.fields.append(new_field)

            if valid:
                reindex = True
                self.content_types[new_content_type.name] = new_content_type
        
        # EXISTING CONTENT TYPE
        else:
            existing = True
            had_file_field = self.content_types[ct_name].has_file_field
            self.content_types[ct_name].plural_name = schema['plural_name']
            self.content_types[ct_name].show_in_nav = schema['show_in_nav']
            self.content_types[ct_name].proxy_field = schema['proxy_field']

            label_template = self.content_types[ct_name].templates['Label'].template
            for template_name in schema['templates']:
                if template_name in self.content_types[ct_name].templates:
                    self.content_types[ct_name].templates[template_name].template = schema['templates'][template_name]['template']
                    self.content_types[ct_name].templates[template_name].mime_type = schema['templates'][template_name]['mime_type']
                else:
                    template = ContentTemplate()
                    template.template = schema['templates'][template_name]['template']
                    template.mime_type = schema['templates'][template_name]['mime_type']
                    self.content_types[ct_name].templates[template_name] = template

            if label_template != self.content_types[ct_name].templates['Label'].template:
                relabel = True
                reindex = True

            old_fields = {}
            for x in range(0, len(self.content_types[ct_name].fields)):
                old_fields[self.content_types[ct_name].fields[x].name] = x

            for x in range(0, len(schema['fields'])):
                if schema['fields'][x]['name'] in invalid_field_names or schema['fields'][x]['name'].startswith('_'):
                    valid = False
                elif valid:
                    if schema['fields'][x]['name'] not in old_fields:
                        new_field = Field()
                        new_field.name = schema['fields'][x]['name']
                        new_field.label = schema['fields'][x]['label']
                        new_field.in_lists = schema['fields'][x]['in_lists']
                        new_field.indexed = schema['fields'][x]['indexed']
                        new_field.indexed_with = schema['fields'][x]['indexed_with']
                        new_field.unique = schema['fields'][x]['unique']
                        new_field.unique_with = schema['fields'][x]['unique_with']
                        new_field.multiple = schema['fields'][x]['multiple']
                        new_field.type = schema['fields'][x]['type']
                        new_field.cross_reference_type = schema['fields'][x]['cross_reference_type']

                        self.content_types[ct_name].fields.append(new_field)
                        if new_field.in_lists:
                            reindex = True
                    else:
                        field_index = old_fields[schema['fields'][x]['name']]
                        self.content_types[ct_name].fields[field_index].label = schema['fields'][x]['label']

                        if self.content_types[ct_name].fields[field_index].in_lists != schema['fields'][x]['in_lists'] and \
                                self.content_types[ct_name].fields[field_index].type != 'embedded':
                            self.content_types[ct_name].fields[field_index].in_lists = schema['fields'][x]['in_lists']
                            reindex = True

                        if not self.content_types[ct_name].fields[field_index].inherited:
                            self.content_types[ct_name].fields[field_index].indexed = schema['fields'][x]['indexed']
                            self.content_types[ct_name].fields[field_index].indexed_with = schema['fields'][x]['indexed_with']
                            self.content_types[ct_name].fields[field_index].unique = schema['fields'][x]['unique']
                            self.content_types[ct_name].fields[field_index].unique_with = schema['fields'][x]['unique_with']
                            self.content_types[ct_name].fields[field_index].multiple = schema['fields'][x]['multiple']
                            self.content_types[ct_name].fields[field_index].type = schema['fields'][x]['type']
                            self.content_types[ct_name].fields[field_index].cross_reference_type = schema['fields'][x]['cross_reference_type']

            if not valid:
                self.reload()

        if valid:
            related_content_types = []

            if 'Label' not in self.content_types[ct_name].templates:
                template = ContentTemplate()
                template.template = "{content_type} ({{{{ {content_type}.id }}}})".format(content_type=ct_name)
                template.mime_type = "text/html"
                self.content_types[ct_name].templates['Label'] = template

            if reindex:
                self.build_content_type_elastic_index(ct_name)
                if not existing:
                    reindex = False
                else:
                    for related_ct in self.content_types.keys():
                        if related_ct != ct_name:
                            for related_field in self.content_types[related_ct].fields:
                                if related_field.type == 'cross_reference' and related_field.cross_reference_type == ct_name:
                                    self.build_content_type_elastic_index(related_ct)
                                    related_content_types.append(related_ct)

            self.content_types[ct_name].has_file_field = schema.get('has_file_field', False)
            for field in self.content_types[ct_name].fields:
                if field.type == 'file':
                    self.content_types[ct_name].has_file_field = True
                    break

            if not had_file_field and self.content_types[ct_name].has_file_field:
                resave = True

            if reindex or relabel or resave:
                queued_job_ids.append(self.queue_local_job(task_name="Adjust Content", parameters={
                    'content_type': ct_name,
                    'reindex': reindex,
                    'relabel': relabel,
                    'resave': resave
                }))

            self.save()

        return queued_job_ids

    def delete_content_type(self, content_type):
        if content_type in self.content_types:
            # Delete Neo4J nodes
            run_neo(
                '''
                    MATCH (x)
                    WHERE EXISTS (x.uri)
                    AND x.uri STARTS WITH '/corpus/{0}/{1}'
                    DETACH DELETE x
                '''.format(
                    self.id,
                    content_type
                ), {}
            )

            # Delete Elasticsearch index
            index_name = "corpus-{0}-{1}".format(self.id, content_type.lower())
            index = Index(index_name)
            if index.exists():
                index.delete()

            # Drop MongoDB collection
            self.content_types[content_type].get_mongoengine_class(self).drop_collection()

            # Delete files
            ct_path = "{0}/{1}".format(self.path, content_type)
            if os.path.exists(ct_path):
                shutil.rmtree(ct_path)

            # Remove from content_types
            del self.content_types[content_type]

            self.save()

    def clear_content_type_field(self, content_type, field_name):
        if content_type in self.content_types:
            ct = self.content_types[content_type]
            if field_name in [field.name for field in ct.fields]:
                ct.get_mongoengine_class(self).objects.update(**{'set__{0}'.format(field_name): None})

    def delete_content_type_field(self, content_type, field_name):
        if content_type in self.content_types:
            ct = self.content_types[content_type]

            if field_name in [field.name for field in ct.fields]:

                # find and delete field or references to field
                field_index = -1
                for x in range(0, len(ct.fields)):
                    if ct.fields[x].name == field_name and not ct.fields[x].inherited:
                        field_index = x
                    else:
                        if field_name in ct.fields[x].unique_with:
                            self.content_types[content_type].fields[x].unique_with.remove(field_name)
                        if field_name in ct.fields[x].indexed_with:
                            self.content_types[content_type].fields[x].indexed_with.remove(field_name)
                if field_index > -1:
                    self.content_types[content_type].fields.pop(field_index)
                    self.save()

                    # delete any indexes referencing field, then drop field from collection
                    print('field cleared. now attemtpting to drop indexes...')
                    collection_name = "corpus_{0}_{1}".format(self.id, content_type)
                    db = self._get_db()
                    index_info = db[collection_name].index_information()
                    for index_name in index_info.keys():
                        delete_index = False
                        for key in index_info[index_name]['key']:
                            if key[0] == field_name:
                                delete_index = True
                        if delete_index:
                            db[collection_name].drop_index(index_name)
                    print('indexes cleared. now attemtpting to unset fields...')
                    db[collection_name].update({}, {'$unset': {field_name: 1}}, multi=True)

    def build_content_type_elastic_index(self, content_type):
        if content_type in self.content_types:
            ct = self.content_types[content_type]
            field_type_map = {
                'text': 'text',
                'keyword': 'keyword',
                'html': 'text',
                'number': 'integer',
                'date': 'date',
                'file': 'text',
                'image': 'text',
                'link': 'text',
                'cross_reference': None,
                'document': 'text',
            }

            index_name = "corpus-{0}-{1}".format(self.id, ct.name.lower())
            index = Index(index_name)
            if index.exists():
                index.delete()

            corpora_analyzer = analyzer(
                'corpora_analyzer',
                tokenizer='classic',
                filter=['stop', 'lowercase', 'classic']
            )

            mapping = Mapping()
            mapping.field('label', 'text', analyzer=corpora_analyzer, fields={'raw': Keyword()})
            mapping.field('uri', 'keyword')

            for field in ct.fields:
                if field.type != 'embedded' and field.in_lists:
                    field_type = field_type_map[field.type]
                    nested_text_type = {
                        'type': 'text',
                        'analyzer': corpora_analyzer,
                        'fields': {
                            'raw': {
                                'type': 'keyword'
                            }
                        }
                    }

                    if field.type == 'cross_reference' and field.cross_reference_type in self.content_types:
                        xref_ct = self.content_types[field.cross_reference_type]
                        xref_mapping_props = {
                            'id': 'keyword',
                            'label': nested_text_type,
                            'uri': 'keyword'
                        }

                        for xref_field in xref_ct.fields:
                            if xref_field.in_lists and not xref_field.type == 'cross_reference':
                                xref_field_type = field_type_map[xref_field.type]
                                if xref_field.type == 'text':
                                    xref_field_type = nested_text_type

                                xref_mapping_props[xref_field.name] = xref_field_type

                        mapping.field(field.name, Nested(properties=xref_mapping_props))

                    elif field_type == 'text':
                        subfields = {'raw': {'type': 'keyword'}}
                        mapping.field(field.name, field_type, analyzer=corpora_analyzer, fields=subfields)
                    else:
                        mapping.field(field.name, field_type)

            index.mapping(mapping)
            index.save()

    def queue_local_job(self, content_type=None, content_id=None, task_id=None, task_name=None, scholar_id=None, parameters={}):
        local_jobsite = JobSite.objects(name='Local')[0]
        if task_name and not task_id:
            task_id = local_jobsite.task_registry[task_name]['task_id']

        if task_id:
            task = Task.objects(id=task_id)[0]

            if not content_type and task.content_type == 'Corpus':
                content_type = 'Corpus'

            if content_type:
                job = Job()
                job.corpus_id = str(self.id)
                job.task_id = str(task_id)
                job.content_type = content_type
                job.content_id = str(content_id) if content_id else None
                job.scholar_id = str(scholar_id) if scholar_id else None
                job.jobsite_id = str(local_jobsite.id)
                job.status = "queueing"
                job.configuration = deepcopy(task.configuration)

                for param in parameters.keys():
                    if param in job.configuration['parameters']:
                        job.configuration['parameters'][param]['value'] = parameters[param]

                job.save()
                return job.id
        return None

    def running_jobs(self):
        return Job.get_jobs(corpus_id=str(self.id))

    def _make_path(self):
        corpus_path = "/corpora/{0}".format(self.id)
        os.makedirs("{0}/files".format(corpus_path), exist_ok=True)
        return corpus_path

    @classmethod
    def _post_save(cls, sender, document, **kwargs):

        if not document.uri:
            document.uri = "/corpus/{0}".format(document.id)
            document.path = document._make_path()
            document.update(**{'set__uri': document.uri, 'set__path': document.path})

        # Create node in Neo4j for corpus
        run_neo('''
                    MERGE (c:Corpus { uri: $corpus_uri })
                    SET c.name = $corpus_title
                ''',
                {
                    'corpus_uri': "/corpus/{0}".format(document.id),
                    'corpus_title': document.name
                }
                )

        # Add this corpus to Corpora Elasticsearch index
        get_connection().index(
            index='corpora',
            id=str(document.id),
            body={
                'name': document.name,
                'description': document.description,
                'open_access': document.open_access
            }
        )

    @classmethod
    def _pre_delete(cls, sender, document, **kwargs):

        # Delete Content Type indexes and collections
        for content_type in document.content_types.keys():
            # Delete ct index
            index_name = "corpus-{0}-{1}".format(document.id, content_type.lower())
            index = Index(index_name)
            if index.exists():
                index.delete()

            # Drop ct MongoDB collection
            document.content_types[content_type].get_mongoengine_class(document).drop_collection()

        # Delete all Neo4J nodes associated with corpus
        run_neo(
            '''
                MATCH (x)
                WHERE EXISTS (x.uri)
                AND x.uri STARTS WITH '/corpus/{0}'
                DETACH DELETE x
            '''.format(document.id),
            {}
        )

        # Remove corpus from ES index
        es_corpus_doc = Search(index='corpora').query("match", _id=str(document.id))
        es_corpus_doc.delete()

        # Delete corpus files
        if os.path.exists(document.path):
            shutil.rmtree(document.path)
        
    def to_dict(self):
        corpus_dict = {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'path': self.path,
            'uri': self.uri,
            'kvp': deepcopy(self.kvp),
            'open_access': self.open_access,
            'files': {},
            'content_types': {},
        }

        for file_key in self.files:
            corpus_dict['files'][file_key] = self.files[file_key].to_dict(parent_uri=self.uri)

        for ct_name in self.content_types:
            corpus_dict['content_types'][ct_name] = self.content_types[ct_name].to_dict()

        corpus_dict['provenance'] = [prov.to_dict() for prov in self.provenance]

        return corpus_dict

    meta = {
        'indexes': [
            'open_access',
            {
                'fields': ['id', 'content_types.name'],
                'unique': True,
                'sparse': True
            },
            {
                'fields': ['id', 'content_types.plural_name'],
                'unique': True,
                'sparse': True
            },
            {
                'fields': ['id', 'content_types.name', 'content_types.fields.name'],
                'unique': True,
                'sparse': True
            }
        ]
    }


class Content(mongoengine.Document):
    corpus_id = mongoengine.StringField(required=True)
    content_type = mongoengine.StringField(required=True)
    last_updated = mongoengine.DateTimeField(default=datetime.now())
    provenance = mongoengine.EmbeddedDocumentListField(CompletedTask)
    path = mongoengine.StringField()
    label = mongoengine.StringField()
    uri = mongoengine.StringField()

    @classmethod
    def _pre_save(cls, sender, document, **kwargs):
        document.last_updated = datetime.now()

    def save(self, do_indexing=True, do_linking=True, **kwargs):
        super().save(**kwargs)
        modified = self._make_path() | self._make_label() | self._make_uri()

        if modified:
            self.update(
                set__path=self.path,
                set__label=self.label,
                set__uri=self.uri
            )

        if do_indexing:
            self._do_indexing()
        if do_linking:
            self._do_linking()

    def _make_label(self):
        if not self.label:
            label_template = Template(self._ct.templates['Label'].template)
            context = Context({self.content_type: self})
            self.label = label_template.render(context)
            return True
        return False

    def _make_uri(self):
        new_uri = self.uri

        if self._ct.proxy_field:
            proxy_field = self._ct.get_field(self._ct.proxy_field)
            proxy_field_value = getattr(self, self._ct.proxy_field)

            if proxy_field and \
                    proxy_field.multiple is False and \
                    proxy_field.cross_reference_type and \
                    proxy_field_value:
                proxy_ct = proxy_field.cross_reference_type
                proxy_id = proxy_field_value.id
                new_uri = "/corpus/{0}/{1}/{2}".format(self.corpus_id, proxy_ct, proxy_id)
        else:
            new_uri = "/corpus/{0}/{1}/{2}".format(
                self.corpus_id,
                self.content_type,
                self.id
            )

        if new_uri != self.uri:
            self.uri = new_uri
            return True
        return False

    def _make_path(self):
        if not self.path and self._ct.has_file_field:
            breakout_dir = str(self.id)[-6:-2]
            self.path = "/corpora/{0}/{1}/{2}/{3}".format(self.corpus_id, self.content_type, breakout_dir, self.id)
            os.makedirs(self.path + "/files", exist_ok=True)
            return True
        return False

    def _move_temp_file(self, field_name, field_index=None):
        field = self._ct.get_field(field_name)
        temp_uploads_dir = "{0}/{1}/temporary_uploads".format(self._corpus.path, self.content_type)
        file = None
        new_file = None

        if field:
            if field.multiple and field_index is not None:
                file = getattr(self, field_name)[field_index]
            else:
                file = getattr(self, field_name)

            if file and file.path.startswith(temp_uploads_dir):
                old_path = file.path

                new_path = old_path.replace(
                    temp_uploads_dir,
                    self.path
                )

                os.rename(old_path, new_path)

                new_file = File.process(
                    new_path,
                    desc=file.description,
                    prov_type=file.provenance_type,
                    prov_id=file.provenance_id
                )

            if file and new_file:
                file._unlink(self.uri)

                if field.multiple and field_index is not None:
                    getattr(self, field_name)[field_index] = new_file
                else:
                    setattr(self, field_name, new_file)

    def _do_indexing(self):
        index_obj = {}
        for field in self._ct.fields:
            if field.in_lists:
                field_value = getattr(self, field.name)
                if field_value:
                    if field.cross_reference_type:
                        if field.multiple:
                            field_value = []
                            for xref in getattr(self, field.name):
                                xref_dict = {
                                    'id': str(xref.id),
                                    'label': xref.label,
                                    'uri': xref.uri
                                }

                                for xref_field in self._corpus.content_types[field.cross_reference_type].fields:
                                    if xref_field.in_lists:
                                        xref_dict[xref_field.name] = xref_field.get_dict_value(getattr(xref, xref_field.name), xref.uri)
                                field_value.append(xref_dict)
                        else:
                            xref = field_value
                            field_value = {
                                'id': str(xref.id),
                                'label': xref.label,
                                'uri': xref.uri
                            }

                            for xref_field in self._corpus.content_types[field.cross_reference_type].fields:
                                if xref_field.in_lists:
                                    field_value[xref_field.name] = xref_field.get_dict_value(getattr(xref, xref_field.name), xref.uri)

                        index_obj[field.name] = field_value

                    elif field.type not in ['file']:
                        index_obj[field.name] = field.get_dict_value(field_value, self.uri)

        index_obj['label'] = self.label
        index_obj['uri'] = self.uri

        try:
            get_connection().index(
                index="corpus-{0}-{1}".format(self.corpus_id, self.content_type.lower()),
                id=str(self.id),
                body=index_obj
            )
        except:
            print("Error indexing {0} with ID {1}:".format(self.content_type, self.id))
            print(traceback.format_exc())

    def _do_linking(self):
        run_neo(
            '''
                MATCH (c:Corpus {{ uri: $corpus_uri }})
                MERGE (d:{content_type} {{ uri: $content_uri }})
                SET d.id = $content_id
                SET d.label = $content_label
                MERGE (c) -[rel:has{content_type}]-> (d)
            '''.format(content_type=self.content_type),
            {
                'corpus_uri': "/corpus/{0}".format(self.corpus_id),
                'content_uri': self.uri,
                'content_id': str(self.id),
                'content_label': self.label
            }
        )

        nodes = {}
        for field in self._ct.fields:
            field_value = getattr(self, field.name)
            if field_value:
                if field.cross_reference_type:
                    cross_ref_type = field.cross_reference_type
                    if cross_ref_type not in nodes:
                        nodes[cross_ref_type] = []

                    if field.multiple:
                        nodes[cross_ref_type] = []
                        for cross_ref in field_value:
                            nodes[cross_ref_type].append({
                                'id': cross_ref.id,
                                'uri': cross_ref.uri,
                                'label': cross_ref.label,
                                'field': field.name
                            })
                    else:
                        nodes[cross_ref_type].append({
                            'id': field_value.id,
                            'uri': field_value.uri,
                            'label': field_value.label,
                            'field': field.name
                        })
                elif field.multiple and hasattr(field_value, 'keys'):
                    for field_key in field_value.keys():
                        mapped_value = field_value[field_key]
                        if hasattr(mapped_value, '_do_linking'):
                            mapped_value._do_linking(self._ct.name, self.uri)
                elif field.multiple:
                    for list_value in field_value:
                        if hasattr(list_value, '_do_linking'):
                            list_value._do_linking(self._ct.name, self.uri)
                elif hasattr(field_value, '_do_linking'):
                    field_value._do_linking(self._ct.name, self.uri)

        if nodes:
            for node_label in nodes.keys():
                for node in nodes[node_label]:
                    run_neo(
                        '''
                            MERGE (a:{content_type} {{ uri: $content_uri }})
                            MERGE (b:{cx_type} {{ uri: $cx_uri }})
                            MERGE (a)-[rel:has{field}]->(b)
                        '''.format(
                            content_type=self.content_type,
                            cx_type=node_label,
                            field=node['field'],
                        ),
                        {
                            'content_uri': self.uri,
                            'cx_uri': node['uri']
                        }
                    )

    def to_dict(self, ref_only=False):
        content_dict = {
            'corpus_id': self.corpus_id,
            'content_type': self.content_type,
            'id': str(self.id),
            'last_updated': int(self.last_updated.timestamp()),
            'label': self.label,
            'uri': self.uri
        }

        if not ref_only:
            content_dict['provenance'] = [prov.to_dict() for prov in self.provenance]

            for field in self._ct.fields:
                content_dict[field.name] = field.get_dict_value(getattr(self, field.name), self.uri)

        return content_dict

    meta = {
        'abstract': True
    }



# SIGNALS FOR HANDLING MONGOENGINE DOCUMENT PRE-DELETION (mostly for deleting Neo4J nodes)
mongoengine.signals.post_save.connect(Corpus._post_save, sender=Corpus)
mongoengine.signals.post_delete.connect(Scholar._post_delete, sender=Scholar)
mongoengine.signals.post_delete.connect(Task._post_delete, sender=Task)
mongoengine.signals.post_delete.connect(JobSite._post_delete, sender=JobSite)
mongoengine.signals.pre_delete.connect(Corpus._pre_delete, sender=Corpus)
Scholar.register_delete_rule(Corpus, "available_corpora", mongoengine.PULL)


# UTILITY CLASSES / FUNCTIONS
def get_corpus(corpus_id, only=[]):
    try:
        corpus = Corpus.objects(id=corpus_id)
        if only:
            corpus = corpus.only(*only)
        return corpus[0]
    except:
        return None


def search_corpora(page=1, page_size=50, general_query="", fields_query=[], fields_sort=[], only=[], ids=[], open_access_only=False):
    results = {
        'meta': {
            'content_type': 'Corpus',
            'total': 0,
            'page': page,
            'page_size': page_size,
            'num_pages': 1,
            'has_next_page': False
        },
        'records': []
    }

    start_index = (page - 1) * page_size
    end_index = page * page_size

    index = "corpora"
    should = []
    must = []
    if general_query:
        should.append(SimpleQueryString(query=general_query))

    if fields_query:
        for search_field in fields_query.keys():
            must.append(Q('match', **{search_field: fields_query[search_field]}))

    if ids:
        must.append(Q('terms', _id=ids) | Q('match', open_access=True))
    elif open_access_only:
        must.append(Q('match', open_access=True))

    if should or must:
        search_query = Q('bool', should=should, must=must)
        search_cmd = Search(using=get_connection(), index=index, extra={'track_total_hits': True}).query(search_query)

        if fields_sort:
            search_cmd = search_cmd.sort(*fields_sort)

        search_cmd = search_cmd[start_index:end_index]
        print(json.dumps(search_cmd.to_dict(), indent=4))
        search_results = search_cmd.execute().to_dict()
        results['meta']['total'] = search_results['hits']['total']['value']
        results['meta']['num_pages'] = ceil(results['meta']['total'] / results['meta']['page_size'])
        results['meta']['has_next_page'] = results['meta']['page'] < results['meta']['num_pages']

        for hit in search_results['hits']['hits']:
            record = deepcopy(hit['_source'])
            record['id'] = hit['_id']
            record['_search_score'] = hit['_score']
            results['records'].append(record)

    return results


def get_field_value_from_path(obj, path):
    path = path.replace('__', '.')
    path_parts = path.split('.')
    value = obj

    for part in path_parts:
        if hasattr(value, part):
            value = getattr(value, part)
        elif part in value:
            value = value[part]
        else:
            return None

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


def parse_date_string(date_string):
    default_date = datetime(1, 1, 1, 0, 0)
    date_obj = None

    try:
        date_obj = parser.parse(date_string, default=default_date)
    except:
        pass

    return date_obj


def ensure_connection():
    try:
        c = Corpus.objects.count()
    except:
        mongoengine.disconnect_all()
        mongoengine.connect(
            settings.MONGO_DB,
            host=settings.MONGO_HOST,
            username=settings.MONGO_USER,
            password=settings.MONGO_PWD,
            authentication_source=settings.MONGO_AUTH_SOURCE,
            maxpoolsize=settings.MONGO_POOLSIZE
        )
