import mongoengine
import os
import json
import secrets
import traceback
import importlib
import zlib
import shutil
import logging
import redis
import git
import re
from math import ceil
from copy import deepcopy
from datetime import datetime, timezone
from dateutil import parser
from bson.objectid import ObjectId
from bson import DBRef
from PIL import Image
from django.conf import settings
from django.utils.text import slugify
from elasticsearch_dsl import Index, Mapping, analyzer, Keyword, Text, Integer, Date, \
    Nested, token_filter, char_filter, Q, Search
from elasticsearch_dsl.query import SimpleQueryString, Ids
from elasticsearch_dsl.connections import get_connection
from django.template import Template, Context


FIELD_TYPES = ('text', 'large_text', 'keyword', 'html', 'choice', 'number', 'decimal', 'boolean', 'date', 'file', 'repo', 'link', 'iiif-image', 'cross_reference', 'embedded')
MIME_TYPES = ('text/html', 'text/css', 'text/xml', 'text/turtle', 'application/json')


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
    has_intensity = mongoengine.BooleanField(default=False)
    synonym_file = mongoengine.StringField(choices=list(settings.ES_SYNONYM_OPTIONS.keys()))
    indexed_with = mongoengine.ListField()
    unique_with = mongoengine.ListField()
    stats = mongoengine.DictField()
    inherited = mongoengine.BooleanField(default=False)

    def get_dict_value(self, value, parent_uri, field_intensities={}):
        dict_value = None

        if self.multiple:
            if self.type == 'embedded' and hasattr(value, 'keys'):
                dict_value = {}
                for key in value.keys():
                    dict_value[key] = self.to_primitive(value[key], parent_uri)
            else:
                dict_value = []
                for val in value:
                    dict_value.append(self.to_primitive(val, parent_uri, field_intensities))
        else:
            dict_value = self.to_primitive(value, parent_uri, field_intensities)

        return dict_value

    def to_primitive(self, value, parent_uri, field_intensities={}):
        if value:
            if self.type == 'date':
                dt = datetime.combine(value, datetime.min.time())
                return dt.isoformat()
            elif self.type == 'cross_reference':
                value_dict = value.to_dict(ref_only=True)
                if self.has_intensity and 'id' in value_dict:
                    value_dict['intensity'] = field_intensities.get(
                        '{field_name}-{val_id}'.format(field_name=self.name, val_id=value_dict['id']),
                        1
                    )
                return value_dict
            elif self.type == 'repo':
                return value.to_dict()
            elif self.type in ['embedded', 'file']:
                return value.to_dict(parent_uri)
        return value
    
    def get_mongoengine_field_class(self):
        if self.type == 'number':
            if self.unique and not self.unique_with:
                return mongoengine.IntField(unique=True, sparse=True)
            else:
                return mongoengine.IntField()
        elif self.type == 'decimal':
            if self.unique and not self.unique_with:
                return mongoengine.FloatField(unique=True, sparse=True)
            else:
                return mongoengine.FloatField()
        elif self.type == 'boolean':
            if self.unique and not self.unique_with:
                return mongoengine.BooleanField(unique=True, sparse=True)
            else:
                return mongoengine.BooleanField()
        elif self.type == 'date':
            if self.unique and not self.unique_with:
                return mongoengine.DateField(unique=True, sparse=True)
            else:
                return mongoengine.DateField()
        elif self.type == 'file':
            return mongoengine.EmbeddedDocumentField(File)
        elif self.type == 'repo':
            return mongoengine.EmbeddedDocumentField(GitRepo)
        elif self.type != 'cross_reference':
            if self.unique and not self.unique_with:
                return mongoengine.StringField(unique=True, sparse=True)
            else:
                return mongoengine.StringField()

    def get_elasticsearch_analyzer(self):
        analyzer_filters = ['lowercase', 'classic', 'stop']
        if self.synonym_file and self.synonym_file in settings.ES_SYNONYM_OPTIONS:
            analyzer_filters.insert(1, token_filter(
                '{0}_synonym_filter'.format(self.synonym_file),
                'synonym',
                lenient=True,
                synonyms_path=settings.ES_SYNONYM_OPTIONS[self.synonym_file]['file']
            ))

        if self.type in ['text', 'large_text']:
            return analyzer(
                '{0}_analyzer'.format(self.name).lower(),
                tokenizer='classic',
                filter=analyzer_filters,
            )

        elif self.type == 'html':
            return analyzer(
                '{0}_analyzer'.format(self.name).lower(),
                tokenizer='classic',
                filter=analyzer_filters,
                char_filter=['html_strip']
            )

        return None

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
            'has_intensity': self.has_intensity,
            'synonym_file': self.synonym_file,
            'indexed_with': [index for index in self.indexed_with],
            'unique_with': [unq for unq in self.unique_with],
            'stats': deepcopy(self.stats),
            'inherited': self.inherited
        }


class Task(mongoengine.Document):
    name = mongoengine.StringField(unique_with='jobsite_type')
    version = mongoengine.StringField()
    jobsite_type = mongoengine.StringField(default="HUEY")
    content_type = mongoengine.StringField(default="Corpus")
    track_provenance = mongoengine.BooleanField(default=True)
    create_report = mongoengine.BooleanField(default=False)
    configuration = mongoengine.DictField()

    def save(self, index_pages=False, **kwargs):
        super().save(**kwargs)

        # Create task node
        run_neo('''
                MERGE (t:_Task { uri: $task_uri })
                SET t.name = $task_name
            ''',
            {
                'task_uri': "/task/{0}".format(self.id),
                'task_name': self.name
            }
        )

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'version': self.version,
            'jobsite_type': self.jobsite_type,
            'content_type': self.content_type,
            'track_provenance': self.track_provenance,
            'create_report': self.create_report,
            'configuration': self.configuration
        }

    @classmethod
    def _post_delete(self, sender, document, **kwargs):
        # TODO: Think through what happens when documents reference task slated for deletion as a "completed task."
        # With potentially thousands of documents referencing the task, going through every document and looking for
        # instances of this task would be very time consuming. Yet, should the task disappear due to deletion,
        # MongoEngine will throw data integrity errors :/ Thankfully, haven't had to delete any tasks yet...
        # My guess is that this will involve creating a dummy task called "Deleted Task" that gets associated with
        # completed tasks. That way, document files can still maintain provenance.

        run_neo('''
                MATCH (t:_Task { uri: $task_uri })
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
                MERGE (js:_JobSite { uri: $js_uri })
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
                    MATCH (js:_JobSite { uri: $js_uri })
                    MATCH (t:_Task { uri: $task_uri })
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
                MATCH (js:_JobSite { uri: $jobsite_uri })
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
            self.report_path = None
            self.stage = 0
            self.timeout = 0
            self.tries = 0
            self.error = ""
            self.configuration = {}
            self.percent_complete = 0

    def _load(self, id):
        results = run_neo(
            '''
                MATCH (j:_Job { uri: $job_uri })
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
        if 'report_path' in result:
            self.report_path = result['report_path']
        else:
            self.report_path = None
        self.stage = result['stage']
        self.timeout = result['timeout']
        self.tries = result['tries']
        self.error = result['error']
        if 'percent_complete' in result:
            self.percent_complete = result['percent_complete']
        else:
            self.percent_complete = 0
        self.configuration = json.loads(result['configuration'])

        # check process completion
        results = run_neo(
            '''
                MATCH (j:_Job { uri: $job_uri }) -[rel:hasProcess]-> (p:_Process)
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
                    MERGE (j:_Job {{ uri: $job_uri }})
                    SET j.corpus_id = $job_corpus_id
                    SET j.content_type = $job_content_type
                    SET j.content_id = $job_content_id
                    SET j.task_id = $job_task_id
                    SET j.jobsite_id = $job_jobsite_id
                    SET j.scholar_id = $job_scholar_id
                    SET j.submitted_time = $job_submitted_time
                    SET j.status = $job_status
                    SET j.status_time = $job_status_time
                    SET j.report_path = $job_report_path
                    SET j.stage = $job_stage
                    SET j.timeout = $job_timeout
                    SET j.tries = $job_tries
                    SET j.error = $job_error
                    SET j.percent_complete = $percent_complete
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
                    'job_report_path': self.report_path,
                    'job_stage': self.stage,
                    'job_timeout': self.timeout,
                    'job_tries': self.tries,
                    'job_error': self.error,
                    'percent_complete': self.percent_complete,
                    'job_configuration': json.dumps(self.configuration)
                }
            )
        else:
            run_neo(
                '''
                    MATCH (c:Corpus {{ uri: $corpus_uri }})
                    MATCH (d:{0} {{ uri: $content_uri }})
                    MERGE (j:_Job {{ uri: $job_uri }})
                    SET j.corpus_id = $job_corpus_id
                    SET j.content_type = $job_content_type
                    SET j.content_id = $job_content_id
                    SET j.task_id = $job_task_id
                    SET j.jobsite_id = $job_jobsite_id
                    SET j.scholar_id = $job_scholar_id
                    SET j.submitted_time = $job_submitted_time
                    SET j.status = $job_status
                    SET j.status_time = $job_status_time
                    SET j.report_path = $job_report_path
                    SET j.stage = $job_stage
                    SET j.timeout = $job_timeout
                    SET j.tries = $job_tries
                    SET j.error = $job_error
                    SET j.percent_complete = $percent_complete
                    SET j.configuration = $job_configuration
                    MERGE (c) -[:hasJob]-> (j) -[:hasJobTarget]-> (d)
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
                    'job_report_path': self.report_path,
                    'job_stage': self.stage,
                    'job_timeout': self.timeout,
                    'job_tries': self.tries,
                    'job_error': self.error,
                    'percent_complete': self.percent_complete,
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
            'report_path': self.report_path,
            'stage': self.stage,
            'timeout': self.timeout,
            'tries': self.tries,
            'error': self.error,
            'configuration': self.configuration,
            'percent_complete': self.percent_complete
        }

    def get_param_value(self, parameter):
        if 'parameters' in self.configuration and parameter in self.configuration['parameters'] and 'value' in self.configuration['parameters'][parameter]:
            return self.configuration['parameters'][parameter]['value']
        return None

    def set_status(self, status, percent_complete=None):
        self.status = status
        self.status_time = datetime.now()
        if percent_complete:
            self.percent_complete = percent_complete

        run_neo(
            '''
                MATCH (j:_Job { uri: $job_uri })
                SET j.status = $job_status
                SET j.status_time = $job_status_time
                SET j.percent_complete = $percent_complete
            ''',
            {
                'job_uri': "/job/{0}".format(self.id),
                'job_status': self.status,
                'job_status_time': int(self.status_time.timestamp()),
                'percent_complete': self.percent_complete
            }
        )

    def report(self, message, overwrite=False):
        if self.task.create_report and self.report_path:
            mode = 'a+'
            if overwrite:
                mode = 'w'

            with open(self.report_path, mode, encoding='utf-8') as report_out:
                report_out.write(message + '\n')

    def add_process(self, process_id):
        run_neo(
            '''
                MATCH (j:_Job { uri: $job_uri })
                MERGE (p:_Process { uri: $process_uri })
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
                MATCH (j:_Job { uri: $job_uri }) -[rel:hasProcess]-> (p:_Process { uri: $process_uri })
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
                MATCH (j:_Job { uri: $job_uri }) -[rel:hasProcess]-> (p:_Process)
                DETACH DELETE p
            ''',
            {'job_uri': "/job/{0}".format(self.id)}
        )

    def kill(self):
        results = run_neo(
            '''
                MATCH (j:_Job { uri: $job_uri }) -[rel:hasProcess]-> (p:_Process)
                return p
            ''',
            {'job_uri': "/job/{0}".format(self.id)}
        )
        if results:
            for proc in results:
                task_id = proc['p']['uri'].split('/')[-1]
                if task_id:
                    try:
                        settings.HUEY.revoke_by_id(task_id)
                    except:
                        print('Attempt to revoke process {0} in Huey task queue failed:'.format(task_id))
                        print(traceback.format_exc())

        run_neo(
            '''
                MATCH (j:_Job { uri: $job_uri })
                OPTIONAL MATCH (j) -[rel:hasProcess]-> (p)
                DETACH DELETE j, p
            ''',
            {
                'job_uri': '/job/{0}'.format(self.id)
            }
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

        if self.report_path:
            self.report("\nCORPORA JOB COMPLETE")

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
            ct.report_path = self.report_path
            ct.status = self.status
            ct.error = self.error

            self.content.provenance.append(ct)
            self.content.save()

        run_neo(
            '''
                MATCH (j:_Job { uri: $job_uri })
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
    def get_jobs(corpus_id=None, content_type=None, content_id=None, count_only=False, limit=None, skip=0):
        jobs = []
        results = None

        return_statement = "RETURN j"
        if count_only:
            return_statement = "RETURN count(j) as job_count"
        elif limit:
            return_statement += " SKIP {0} LIMIT {1}".format(skip, limit)

        if not corpus_id and not content_type and not content_id:
            results = run_neo(
                '''
                    MATCH (j:_Job)
                    {0}
                '''.format(return_statement), {}
            )
        elif corpus_id and not content_type:
            results = run_neo(
                '''
                    MATCH (c:Corpus {{ uri: $corpus_uri }}) -[rel:hasJob]-> (j:_Job)
                    {0}
                '''.format(return_statement),
                {
                    'corpus_uri': "/corpus/{0}".format(corpus_id)
                }
            )
        elif corpus_id and content_type and not content_id:
            results = run_neo(
                '''
                    MATCH (c:Corpus {{ uri: $corpus_uri }}) -[:hasJob]-> (j:_Job) -[:hasJobTarget]-> (d:{0})
                    {1}
                '''.format(content_type, return_statement),
                {
                    'corpus_uri': "/corpus/{0}".format(corpus_id)
                }
            )
        elif corpus_id and content_type and content_id:
            results = run_neo(
                '''
                    MATCH (c:Corpus {{ uri: $corpus_uri }}) -[:hasJob]-> (j:_Job) -[:hasJobTarget]-> (d:{0} {{ uri: $content_uri }})
                    {1}
                '''.format(content_type, return_statement),
                {
                    'corpus_uri': "/corpus/{0}".format(corpus_id),
                    'content_uri': "/corpus/{0}/{1}/{2}".format(corpus_id, content_type, content_id)
                }
            )

        if results:
            if count_only:
                return results[0]['job_count']

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
    available_corpora = mongoengine.DictField() # corpus_id: Viewer|Editor
    available_tasks = mongoengine.ListField(mongoengine.LazyReferenceField(Task, reverse_delete_rule=mongoengine.PULL))
    available_jobsites = mongoengine.ListField(mongoengine.LazyReferenceField(JobSite, reverse_delete_rule=mongoengine.PULL))
    is_admin = mongoengine.BooleanField(default=False)
    auth_token = mongoengine.StringField(default=secrets.token_urlsafe(32))
    auth_token_ips = mongoengine.ListField(mongoengine.StringField())

    def save(self, index_pages=False, **kwargs):
        super().save(**kwargs)
        permissions = ""

        # Create/update scholar node
        run_neo('''
                MERGE (s:_Scholar { uri: $scholar_uri })
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
        for corpus_id, role in self.available_corpora.items():
            permissions += "{0}:{1},".format(corpus_id, role)



        # Add this scholar to Scholar Elasticsearch index
        if permissions:
            permissions = permissions[:-1]

        get_connection().index(
            index='scholar',
            id=str(self.id),
            body={
                'username': self.username,
                'fname': self.fname,
                'lname': self.lname,
                'email': self.email,
                'is_admin': self.is_admin,
                'available_corpora': permissions
            }
        )

    def get_preference(self, content_type, content_uri, preference):
        results = run_neo(
            '''
                MATCH (s:_Scholar {{ uri: $scholar_uri }}) -[prefs:hasPreferences]-> (c:{content_type} {{ uri: $content_uri }})
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
                MATCH (s:_Scholar {{ uri: $scholar_uri }})
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
        # Delete Neo4J nodes
        run_neo('''
                MATCH (s:_Scholar { uri: $scholar_uri })
                DETACH DELETE s
            ''',
            {
                'scholar_uri': "/scholar/{0}".format(document.id),
            }
        )

        # Remove scholar from ES index
        es_scholar = Search(index='scholar').query("match", _id=str(document.id))
        es_scholar.delete()


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
    report_path = mongoengine.StringField()
    error = mongoengine.StringField()

    @classmethod
    def from_dict(cls, prov_info):
        prov = CompletedTask()
        valid = True
        for attr in ['job_id', 'task_configuration', 'status', 'report_path', 'error']:
            if attr in prov_info:
                setattr(prov, attr, prov_info[attr])
            else:
                valid = False

        if valid:
            if 'task_id' in prov_info and 'jobsite_id' in prov_info and 'scholar_id' in prov_info and 'submitted' in prov_info and 'completed' in prov_info:
                try:
                    task = Task.objects(id=prov_info['task_id'])[0]
                    prov.task = task

                    if 'task_version' in prov_info:
                        prov.task_version = prov_info['task_version']

                    jobsite = JobSite.objects(id=prov_info['jobsite_id'])[0]
                    prov.jobsite = jobsite

                    scholar = Scholar.objects(id=prov_info['scholar_id'])[0]
                    prov.scholar = scholar

                    prov.submitted = datetime.fromtimestamp(prov_info['submitted'])
                    prov.completed = datetime.fromtimestamp(prov_info['completed'])
                except:
                    print(traceback.format_exc())
                    valid = False
            else:
                valid = False

        if valid:
            return prov

        return None

    def to_dict(self):
        return {
            'job_id': self.job_id,
            'task_id': str(self.task.id),
            'task_name': str(self.task.name),
            'task_version': self.task_version,
            'task_configuration': deepcopy(self.task_configuration),
            'jobsite_id': str(self.jobsite.id),
            'scholar_id': str(self.scholar.id),
            'scholar_name': "{0} {1}".format(self.scholar.fname, self.scholar.lname),
            'submitted': int(self.submitted.timestamp()),
            'completed': int(self.completed.timestamp()),
            'status': self.status,
            'report_path': self.report_path,
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
    view_widget_url = mongoengine.StringField()
    edit_widget_url = mongoengine.StringField()
    inherited_from_module = mongoengine.StringField()
    inherited_from_class = mongoengine.StringField()
    base_mongo_indexes = mongoengine.StringField()
    has_file_field = mongoengine.BooleanField(default=False)
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
        mongoengine.signals.pre_delete.connect(ct_class._pre_delete, sender=ct_class)

        return ct_class

    def _has_intensity_field(self):
        for field in self.fields:
            if field.has_intensity:
                return True
        return False

    def get_field_dict(self, include_embedded=False):
        fd = {}
        for field in self.fields:
            if field.type != 'embedded' or include_embedded:
                fd[field.name] = field
        return fd

    def to_dict(self):
        ct_dict = {
            'name': self.name,
            'plural_name': self.plural_name,
            'fields': [field.to_dict() for field in self.fields],
            'show_in_nav': self.show_in_nav,
            'proxy_field': self.proxy_field,
            'templates': {},
            'view_widget_url': self.view_widget_url,
            'edit_widget_url': self.edit_widget_url,
            'inherited_from_module': self.inherited_from_module,
            'inherited_from_class': self.inherited_from_class,
            'base_mongo_indexes': self.base_mongo_indexes,
            'has_file_field': self.has_file_field,
            'invalid_field_names': deepcopy(self.invalid_field_names),
        }

        for template_name in self.templates:
            ct_dict['templates'][template_name] = self.templates[template_name].to_dict()

        return ct_dict


class File(mongoengine.EmbeddedDocument):
    uri = mongoengine.StringField(blank=True)
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
        uri_parts = [part for part in content_uri.split('/') if part]
        if uri_parts[0] == 'corpus' and len(uri_parts) > 1:
            corpus_id = uri_parts[1]

            run_neo(
                '''
                    MATCH (n:{content_type} {{ uri: $content_uri }})
                    MERGE (f:_File {{ uri: $file_uri }})
                    SET f.path = $file_path
                    SET f.corpus_id = $corpus_id
                    SET f.is_image = $is_image
                    MERGE (n) -[rel:hasFile]-> (f)
                '''.format(content_type=content_type),
                {
                    'content_uri': content_uri,
                    'file_uri': "{0}/file/{1}".format(content_uri, self.key),
                    'corpus_id': corpus_id,
                    'file_path': self.path,
                    'is_image': self.is_image
                }
            )

    def _unlink(self, content_uri):
        run_neo(
            '''
                MATCH (f:_File { uri: $file_uri })
                DETACH DELETE f
            ''',
            {
                'file_uri': "{0}/file/{1}".format(content_uri, self.key)
            }
        )

    @classmethod
    def process(cls, path, desc=None, prov_type=None, prov_id=None, primary=False, parent_uri=''):
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

    def get_url(self, parent_uri, url_type="auto"):
        uri = "{0}/file/{1}".format(parent_uri, self.key)
        url = "/file/uri/{0}/".format(uri.replace('/', '|'))
        if (url_type == "auto" and self.is_image) or url_type == "image":
            url = "/image/uri/{0}/".format(uri.replace('/', '|'))
        return url

    @classmethod
    def from_dict(cls, file_dict):
        file = File()
        valid = True
        for attr in ['uri', 'primary_witness', 'path', 'basename', 'extension', 'byte_size',
                     'description', 'provenance_type', 'provenance_id', 'height', 'width',
                     'is_image', 'iiif_info', 'collection_label']:
            if attr in file_dict:
                setattr(file, attr, file_dict[attr])
            else:
                valid = False
                break

        if valid:
            return File

        return None

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
            'is_image': self.is_image,
            'iiif_info': self.iiif_info,
            'collection_label': self.collection_label
        }


class GitRepo(mongoengine.EmbeddedDocument):

    name = mongoengine.StringField()
    path = mongoengine.StringField()
    remote_url = mongoengine.StringField()
    remote_branch = mongoengine.StringField()
    last_pull = mongoengine.DateTimeField()
    error = mongoengine.BooleanField(default=False)

    def pull(self, parent):
        if self.path and self.remote_url and self.remote_branch:
            repo = None

            # need to clone
            if not os.path.exists(self.path):
                os.makedirs(self.path)
                repo = git.Repo.init(self.path)
                origin = repo.create_remote('origin', self.remote_url)
                assert origin.exists()
                assert origin == repo.remotes.origin == repo.remotes['origin']
                origin.fetch()
                repo.create_head(self.remote_branch, origin.refs[self.remote_branch])
                repo.heads[self.remote_branch].set_tracking_branch(origin.refs[self.remote_branch])
                repo.heads[self.remote_branch].checkout()

            elif self.last_pull:
                repo = git.Repo(self.path)
                assert not repo.bare
                assert repo.remotes.origin.exists()
                repo.remotes.origin.fetch()

            if repo:
                repo.remotes.origin.pull()
                self.last_pull = datetime.now()
                self.error = False
                parent.save()

    @classmethod
    def from_dict(cls, repo_dict):
        repo = GitRepo()
        valid = True
        for attr in ['name', 'path', 'remote_url', 'remote_branch', 'last_pull', 'error']:
            if attr in repo_dict:
                if attr == 'last_pull':
                    repo.last_pull = datetime.fromtimestamp(repo_dict['last_pull'])
                else:
                    setattr(repo, attr, repo_dict[attr])
            else:
                valid = False

        if valid:
            return repo

        return None

    def to_dict(self):
        return {
            'name': self.name,
            'path': self.path,
            'remote_url': self.remote_url,
            'remote_branch': self.remote_branch,
            'last_pull': int(datetime.combine(self.last_pull, datetime.min.time()).timestamp()) if self.last_pull else None,
            'error': self.error
        }


class Corpus(mongoengine.Document):
    name = mongoengine.StringField(unique=True)
    description = mongoengine.StringField()
    uri = mongoengine.StringField(unique=True)
    path = mongoengine.StringField()
    kvp = mongoengine.DictField()
    files = mongoengine.MapField(mongoengine.EmbeddedDocumentField(File))
    repos = mongoengine.MapField(mongoengine.EmbeddedDocumentField(GitRepo))
    open_access = mongoengine.BooleanField(default=False)
    content_types = mongoengine.MapField(mongoengine.EmbeddedDocumentField(ContentType))
    provenance = mongoengine.EmbeddedDocumentListField(CompletedTask)

    def save_file(self, file):
        self.modify(**{'set__files__{0}'.format(file.key): file})
        file._do_linking(content_type='Corpus', content_uri=self.uri)

    def get_content(self, content_type, content_id_or_query={}, only=[], exclude=[], all=False, single_result=False):
        content = None

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
                    if exclude:
                        content = content.exclude(*exclude)
                    if single_result:
                        content = content[0]
                except:
                    return None
            else:
                content = content_obj()
                content.corpus_id = str(self.id)
                content.content_type = content_type

        return content

    def get_or_create_content(self, content_type, fields={}, use_cache=False):
        content = None
        cache_key = None

        if use_cache:
            cache_key = "/corpus/{0}/cached-{1}:{2}".format(
                self.id,
                content_type,
                json.dumps(fields)
            )
            content_id = self.redis_cache.get(cache_key)
            if content_id:
                content = self.get_content(content_type, content_id)

        if not content:
            content = self.get_content(content_type, fields, single_result=True)
            if content and cache_key:
                self.redis_cache.set(cache_key, str(content.id), ex=settings.REDIS_CACHE_EXPIRY_SECONDS)
            elif not content:
                content = self.get_content(content_type)
                content.from_dict(fields)
                content.save()

                if cache_key:
                    self.redis_cache.set(cache_key, str(content.id), ex=settings.REDIS_CACHE_EXPIRY_SECONDS)

        return content

    def make_link(self, source_uri, target_uri, link_label, link_attrs={}, cardinality=1):
        # cardinality values:
        # 0: source --- target
        # 1: source --> target
        # 2: source <-- target
        # 3: source <-> target

        source_uri_parts = [part for part in source_uri.split('/') if part]
        target_uri_parts = [part for part in target_uri.split('/') if part]

        if len(source_uri_parts) == 4 and len(target_uri_parts) == 4:
            if source_uri_parts[1] == str(self.id) and target_uri_parts[1] == source_uri_parts[1]:

                source_content_type = source_uri_parts[2]
                target_content_type = target_uri_parts[2]

                if source_content_type in self.content_types and target_content_type in self.content_types:

                    relationship_start = '-'
                    relationship_end = '->'

                    if cardinality == 0:
                        relationship_end = '-'
                    elif cardinality == 2:
                        relationship_start = '<-'
                        relationship_end = '-'
                    elif cardinality == 3:
                        relationship_start = '<-'

                    link_attr_string = ""
                    if link_attrs:
                        first_attr = True
                        link_attr_string = " { "
                        for key in link_attrs.keys():
                            if not first_attr:
                                link_attr_string += ", "
                            else:
                                first_attr = False

                            link_attr_string += "{0}: ".format(key)
                            if hasattr(link_attrs[key], 'append'):
                                link_attr_string += json.dumps(link_attrs[key])
                            else:
                                link_attr_string += link_attrs[key]
                        link_attr_string += " }"

                    cypher = '''
                        MATCH (src:{source_content_type} {{ uri: $source_uri }})
                        MATCH (trg:{target_content_type} {{ uri: $target_uri }})
                        MERGE (src) {rel_start}[rel:{link_label}{link_props}]{rel_end} (trg)
                    '''.format(
                        source_content_type=source_content_type,
                        target_content_type=target_content_type,
                        rel_start=relationship_start,
                        rel_end=relationship_end,
                        link_label=link_label,
                        link_props=link_attr_string
                    )

                    run_neo(
                        cypher,
                        {
                            'source_uri': source_uri,
                            'target_uri': target_uri
                        }
                    )

    def get_content_dbref(self, content_type, content_id):
        if not type(content_id) == ObjectId:
            content_id = ObjectId(content_id)
        return DBRef(
            "corpus_{0}_{1}".format(self.id, content_type),
            content_id
        )

    def search_content(
            self,
            content_type,
            page=1,
            page_size=50,
            general_query="",
            fields_query={},
            fields_term={},
            fields_phrase={},
            fields_wildcard={},
            fields_filter={},
            fields_range={},
            fields_highlight=[],
            fields_exist=[],
            fields_sort=[],
            only=[],
            excludes=[],
            content_view=None,
            operator="and",
            highlight_num_fragments=5,
            highlight_fragment_size=100,
            only_highlights=False,
            aggregations={},
            next_page_token=None,
            es_debug=False,
            es_debug_query=False
    ):
        results = {
            'meta': {
                'content_type': content_type,
                'total': 0,
                'page': page,
                'page_size': page_size,
                'num_pages': 1,
                'has_next_page': False,
                'aggregations': {}
            },
            'records': []
        }

        if content_type in self.content_types:
            start_index = (page - 1) * page_size
            end_index = page * page_size

            # for keeping track of possible aggregations and their
            # corresponding types, like "terms" or "nested"
            agg_type_map = {}

            index_name = "corpus-{0}-{1}".format(self.id, content_type.lower())
            index = Index(index_name)
            should = []
            must = []
            filter = []

            # GENERAL QUERY
            if general_query:
                if operator == 'and':
                    must.append(SimpleQueryString(query=general_query))
                else:
                    should.append(SimpleQueryString(query=general_query))

            # helper function for determining local operators for queries below
            def determine_local_operator(search_field, operator):
                if search_field.endswith('+'):
                    return search_field[:-1], "and"
                elif search_field.endswith('|'):
                    print("or query")
                    return search_field[:-1], "or"
                return search_field, operator

            # FIELDS QUERY
            for search_field in fields_query.keys():
                field_values = [value_part for value_part in fields_query[search_field].split('__') if value_part]
                search_field, local_operator = determine_local_operator(search_field, operator)
                field_type = None

                if '.' in search_field:
                    field_parts = search_field.split('.')
                    xref_ct = self.content_types[content_type].get_field(field_parts[0]).cross_reference_type

                    if field_parts[1] == 'label':
                        field_type = 'text'
                    elif field_parts[1] in ['uri', 'id']:
                        field_type = 'keyword'
                    else:
                        field_type = self.content_types[xref_ct].get_field(field_parts[1]).type
                else:
                    if search_field == 'label':
                        field_type = 'text'
                    elif search_field in ['uri', 'id']:
                        field_type = 'keyword'
                    else:
                        field_type = self.content_types[content_type].get_field(search_field).type

                if not field_values:
                    if '.' in search_field:
                        field_parts = search_field.split('.')
                        must.append(Q(
                            "nested",
                            path=field_parts[0],
                            query=~Q(
                                'exists',
                                field=search_field
                            )
                        ))
                    else:
                        must.append(~Q('exists', field=search_field))

                for field_value in field_values:
                    q = None

                    search_criteria = {
                        search_field: {'query': field_value}
                    }

                    if field_type in ['text', 'large_text', 'html']:
                        search_criteria[search_field]['operator'] = 'and'
                        search_criteria[search_field]['fuzziness'] = 'AUTO'
                    elif field_type == 'date':
                        search_criteria[search_field]['query'] = parse_date_string(field_value).isoformat()

                    if '.' in search_field:
                        field_parts = search_field.split('.')
                        q = Q(
                            "nested",
                            path=field_parts[0],
                            query=Q('match', **search_criteria)
                        )
                    else:
                        q = Q('match', **search_criteria)

                    if q:
                        if local_operator == 'and':
                            must.append(q)
                        else:
                            should.append(q)

            # PHRASE QUERY
            for search_field in fields_phrase.keys():
                field_values = [value_part for value_part in fields_phrase[search_field].split('__') if value_part]
                search_field, local_operator = determine_local_operator(search_field, operator)

                for field_value in field_values:
                    q = None

                    if '.' in search_field:
                        field_parts = search_field.split('.')
                        q = Q(
                            "nested",
                            path=field_parts[0],
                            query=Q(
                                'match_phrase',
                                **{search_field: field_value}
                            )
                        )
                    else:
                        q = Q('match_phrase', **{search_field: field_value})

                    if q:
                        if local_operator == 'and':
                            must.append(q)
                        else:
                            should.append(q)

            # TERMS QUERY
            for search_field in fields_term.keys():
                field_values = [value_part for value_part in fields_term[search_field].split('__') if value_part]
                search_field, local_operator = determine_local_operator(search_field, operator)

                q = None

                if '.' in search_field:
                    field_parts = search_field.split('.')
                    q = Q(
                        "nested",
                        path=field_parts[0],
                        query=Q(
                            'terms',
                            **{search_field: field_values}
                        )
                    )
                else:
                    q = Q('terms', **{search_field: field_values})

                if q:
                    if local_operator == 'and':
                        must.append(q)
                    else:
                        should.append(q)

            # WILDCARD QUERY
            for search_field in fields_wildcard.keys():
                field_values = [value_part for value_part in fields_wildcard[search_field].split('__') if value_part]
                search_field, local_operator = determine_local_operator(search_field, operator)

                for field_value in field_values:
                    if '*' not in field_value:
                        field_value += '*'

                    q = None

                    if '.' in search_field:
                        field_parts = search_field.split('.')
                        q = Q(
                            "nested",
                            path=field_parts[0],
                            query=Q(
                                'wildcard',
                                **{search_field: field_value}
                            )
                        )
                    else:
                        q = Q('wildcard', **{search_field: field_value})

                    if q:
                        if local_operator == 'and':
                            must.append(q)
                        else:
                            should.append(q)

            # EXISTENCE QUERY
            for search_field in fields_exist:
                q = None

                if '.' in search_field:
                    field_parts = search_field.split('.')
                    q = Q(
                        "nested",
                        path=field_parts[0],
                        query=Q(
                            'exists',
                            field=search_field
                        )
                    )
                else:
                    q = Q('exists', field=search_field)

                if q:
                    if operator == 'and':
                        must.append(q)
                    else:
                        should.append(q)

            # FILTER QUERY
            if fields_filter:
                for search_field in fields_filter.keys():
                    field_values = [value_part for value_part in fields_filter[search_field].split('__') if value_part]
                    for field_value in field_values:
                        if '.' in search_field:
                            field_parts = search_field.split('.')
                            filter.append(Q(
                                "nested",
                                path=field_parts[0],
                                query=Q(
                                    'term',
                                    **{search_field: field_value}
                                )
                            ))
                        else:
                            if search_field == 'id':
                                search_field = '_id'
                            filter.append(Q('term', **{search_field: field_value}))

            # RANGE QUERY
            if fields_range:
                for search_field in fields_range.keys():
                    field_values = [value_part for value_part in fields_range[search_field].split('__') if value_part]
                    field_converter = None
                    field_type = None
                    range_query = None

                    for field_value in field_values:
                        if '.' in search_field:
                            field_parts = search_field.split('.')
                            xref_ct = self.content_types[content_type].get_field(field_parts[0]).cross_reference_type

                            if field_parts[1] == 'label':
                                field_type = 'text'
                            elif field_parts[1] in ['uri', 'id']:
                                field_type = 'keyword'
                            else:
                                field_type = self.content_types[xref_ct].get_field(field_parts[1]).type
                        else:
                            if search_field == 'label':
                                field_type = 'text'
                            elif search_field in ['uri', 'id']:
                                field_type = 'keyword'
                            else:
                                field_type = self.content_types[content_type].get_field(search_field).type

                        if field_type in ['number', 'decimal', 'date']:
                            # default field conversion for number value
                            field_converter = lambda x: int(x)

                            if field_type == 'decimal':
                                field_converter = lambda x: float(x)
                            elif field_type == 'date':
                                field_converter = lambda x: parse_date_string(x).isoformat()

                            range_parts = [part for part in field_value.split('to') if part]
                            if len(range_parts) == 2:
                                range_query = Q(
                                    "range",
                                    **{search_field: {
                                        'gte': field_converter(range_parts[0]),
                                        'lte': field_converter(range_parts[1])
                                    }}
                                )
                            elif len(range_parts) == 1 and field_value.endswith('to'):
                                range_query = Q(
                                    "range",
                                    **{search_field: {
                                        'gte': field_converter(range_parts[0]),
                                    }}
                                )
                            elif len(range_parts) == 1 and field_value.startswith('to'):
                                range_query = Q(
                                    "range",
                                    **{search_field: {
                                        'lte': field_converter(range_parts[0]),
                                    }}
                                )

                        if range_query:
                            if '.' in search_field:
                                field_parts = search_field.split('.')
                                range_query = Q(
                                    'nested',
                                    path=field_parts[0],
                                    query=range_query
                                )

                            if operator == 'and':
                                filter.append(range_query)
                            else:
                                should.append(range_query)



            # CONTENT VIEW
            if content_view:
                filter.append(Q('terms', **{'_id': {
                    'index': 'content_view',
                    'id': content_view,
                    'path': 'ids'
                }}))

            if should or must or filter:

                search_query = Q('bool', should=should, must=must, filter=filter)

                extra = {'track_total_hits': True}
                if fields_query and fields_highlight:
                    extra['min_score'] = 0.001

                using_page_token = False
                if next_page_token:
                    next_page_info = self.redis_cache.get(next_page_token)
                    if next_page_info:
                        next_page_info = json.loads(next_page_info)
                        extra['search_after'] = next_page_info['search_after']
                        results['meta']['page'] = next_page_info['page_num']
                        results['meta']['page_size'] = next_page_info['page_size']
                        using_page_token = True

                search_cmd = Search(using=get_connection(), index=index_name, extra=extra).query(search_query)

                # HANDLE RETURNING FIELD RESTRICTIONS (ONLY and EXCLUDES)
                if only or excludes:
                    if only and '_id' not in only:
                        only.append('_id')

                    search_cmd = search_cmd.source(includes=only, excludes=excludes)

                # ADD ANY AGGREGATIONS TO SEARCH
                for agg_name, agg in aggregations.items():
                    # agg should be of type elasticsearch_dsl.A, so calling A's .to_dict()
                    # method to get at what type ('terms', 'nested', etc) of aggregation
                    # this is.
                    agg_dict = agg.to_dict()
                    agg_descriptor = list(agg_dict.keys())[0]
                    if agg_descriptor == 'nested':
                        agg_descriptor += '_' + list(agg_dict['aggs']['names'].keys())[0]
                    agg_type_map[agg_name] = agg_descriptor
                    search_cmd.aggs.bucket(agg_name, agg)

                # HANDLE SORTING (by default, all data sorted by ID for "search_after" functionality)
                adjusted_fields_sort = []
                sorting_by_id = False

                if fields_sort:
                    mappings = index.get()[index_name]['mappings']['properties']

                    for x in range(0, len(fields_sort)):
                        field_name = list(fields_sort[x].keys())[0]
                        sort_direction = fields_sort[x][field_name]
                        subfield_name = None

                        if field_name == 'id':
                            adjusted_fields_sort.append({
                                '_id': sort_direction
                            })
                            sorting_by_id = True
                        else:
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

                if not sorting_by_id:
                    adjusted_fields_sort.append({
                        '_id': 'asc'
                    })
                search_cmd = search_cmd.sort(*adjusted_fields_sort)

                if fields_highlight:
                    # todo: Update to newer version of Elasticsearch supporting max_analyzed_offset setting for queries (at least 7.12) to support line below
                    # search_cmd = search_cmd.highlight_options(max_analyzed_offset=90000)
                    search_cmd = search_cmd.highlight(*fields_highlight, fragment_size=highlight_fragment_size, number_of_fragments=highlight_num_fragments)

                if using_page_token:
                    search_cmd = search_cmd[0:results['meta']['page_size']]
                else:
                    search_cmd = search_cmd[start_index:end_index]

                # execute search
                try:
                    es_logger = None
                    es_log_level = None
                    if es_debug or es_debug_query:
                        print(json.dumps(search_cmd.to_dict(), indent=4))
                        es_logger = logging.getLogger('elasticsearch')
                        es_log_level = es_logger.getEffectiveLevel()
                        es_logger.setLevel(logging.DEBUG)

                    search_results = search_cmd.execute().to_dict()

                    if es_debug:
                        print(json.dumps(search_results, indent=4))
                        es_logger.setLevel(es_log_level)

                    results['meta']['total'] = search_results['hits']['total']['value']
                    if results['meta']['page_size'] > 0:
                        results['meta']['num_pages'] = ceil(results['meta']['total'] / results['meta']['page_size'])
                        results['meta']['has_next_page'] = results['meta']['page'] < results['meta']['num_pages']
                    else:
                        results['meta']['num_pages'] = 0
                        results['meta']['has_next_page'] = False

                    hit = None
                    for hit in search_results['hits']['hits']:
                        record = deepcopy(hit['_source'])
                        record['id'] = hit['_id']
                        record['_search_score'] = hit['_score']

                        if fields_highlight:
                            if 'highlight' in hit:
                                record['_search_highlights'] = hit['highlight']
                                results['records'].append(record)
                            elif not only_highlights:
                                results['records'].append(record)
                        else:
                            results['records'].append(record)

                    # search_after
                    if (end_index >= 9000 or using_page_token) and results['meta']['has_next_page']:
                        next_page_token = str(ObjectId())

                        if hit and 'sort' in hit:
                            next_page_info = {
                                'search_after': hit['sort'],
                                'page_num': results['meta']['page'] + 1,
                                'page_size': results['meta']['page_size']
                            }
                            next_page_info = json.dumps(next_page_info)
                            self.redis_cache.set(next_page_token, next_page_info, ex=300)
                            results['meta']['next_page_token'] = next_page_token

                    if 'aggregations' in search_results:
                        for agg_name in search_results['aggregations'].keys():
                            results['meta']['aggregations'][agg_name] = {}

                            if agg_type_map[agg_name].startswith('nested'):
                                if agg_type_map[agg_name].endswith('_terms'):
                                    for agg_result in search_results['aggregations'][agg_name]['names']['buckets']:
                                        results['meta']['aggregations'][agg_name][agg_result['key']] = agg_result['doc_count']
                                elif agg_type_map[agg_name].endswith('_max') or agg_type_map[agg_name].endswith('_min'):
                                    results['meta']['aggregations'][agg_name] = search_results['aggregations'][agg_name]['names']['value']

                            elif agg_type_map[agg_name] in ['max', 'min']:
                                results['meta']['aggregations'][agg_name] = search_results['aggregations'][agg_name]['value']

                            elif agg_type_map[agg_name] == 'terms':
                                for agg_result in search_results['aggregations'][agg_name]['buckets']:
                                    results['meta']['aggregations'][agg_name][agg_result['key']] = agg_result['doc_count']

                except:
                    print('Error executing elasticsearch query in corpus.search_content:')
                    print(traceback.format_exc())

        return results

    def explore_content(
            self,
            left_content_type,
            left_id=None,
            left_content=[],
            relationship_cypher=None,
            relationship=None,
            cardinality=1,
            right_content_type=None,
            right_id=None,
            order_by=None):

        results_added = 0
        if left_content_type in self.content_types:
            left_uri_constraints = []
            left_id_map = {}

            if not left_content:
                left_content = []
                if left_id:
                    left_content.append(self.get_content(left_content_type, left_id))
                else:
                    left_content = self.get_content(left_content_type, all=True)

            if left_content:
                left_content = [lefty for lefty in left_content] # <- in case left content is a queryset
                for left_index in range(0, len(left_content)):
                    left_uri_constraints.append(
                        "/corpus/{0}/{1}/{2}".format(
                            self.id,
                            left_content_type,
                            left_content[left_index].id
                        )
                    )

                    left_id_map[str(left_content[left_index].id)] = left_index

                left_cypher = "(left:{0})".format(left_content_type)

                # determine relationship cypher based on relationship and cardinality
                if not relationship_cypher:
                    relationship_cypher = "[rel]"
                    if relationship:
                        relationship_cypher = "[rel:{0}]".format(relationship)

                    relationship_start = '-'
                    relationship_end = '->'

                    if cardinality == 0:
                        relationship_end = '-'
                    elif cardinality == 2:
                        relationship_start = '<-'
                        relationship_end = '-'
                    elif cardinality == 3:
                        relationship_start = '<-'

                    relationship_cypher = "{0}{1}{2}".format(relationship_start, relationship_cypher, relationship_end)

                right_cypher = "(right)"
                if right_content_type:
                    right_cypher = "(right:{0})".format(right_content_type)

                order_cypher = ""
                if order_by:
                    order_cypher = " ORDER BY {0}".format(order_by)

                cypher = '''
                    MATCH {0} {1} {2}
                    WHERE left.corpus_id = $corpus_id
                    AND right.corpus_id = $corpus_id
                    AND left.uri IN $left_uri_constraints
                    RETURN left.id, type(rel), right.uri{3}
                '''.format(left_cypher, relationship_cypher, right_cypher, order_cypher)

                print(cypher)

                results = run_neo(cypher, {
                    'corpus_id': str(self.id),
                    'left_uri_constraints': left_uri_constraints
                })

                for result in results:
                    result = result.data()
                    left_id = result['left.id']
                    relation = result['type(rel)']
                    right_uri = result['right.uri']
                    right_uri_parts = [uri_part for uri_part in right_uri.split('/') if uri_part]
                    if len(right_uri_parts) == 4:
                        right_id = right_uri_parts[3]
                        right_content_type = right_uri_parts[2]

                        if left_id in left_id_map:
                            left_index = left_id_map[left_id]
                            right_dict = {
                                'content_type': right_content_type,
                                'id': right_id,
                                'uri': right_uri
                            }

                            if not hasattr(left_content[left_index], '_exploration'):
                                setattr(left_content[left_index], '_exploration', {})

                            if relation not in left_content[left_index]._exploration:
                                left_content[left_index]._exploration[relation] = [right_dict]
                            else:
                                left_content[left_index]._exploration[relation].append(right_dict)

                            results_added += 1

        print(results_added)
        return left_content

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
            'in_lists': True,
            'indexed': False,
            'indexed_with': [],
            'unique': False,
            'unique_with': [],
            'multiple': False,
            'proxy_field': "",
            'inherited': False,
            'cross_reference_type': '',
            'has_intensity': False,
            'synonym_file': None
        }

        default_invalid_field_names = [
            'corpus_id',
            'content_type',
            'last_updated',
            'provenance',
            'field_intensities',
            'path',
            'label',
            'uri',
        ]

        invalid_field_names = deepcopy(default_invalid_field_names)
        if 'invalid_field_names' in schema:
            invalid_field_names += schema['invalid_field_names']
            invalid_field_names = list(set(invalid_field_names))

        # NEW CONTENT TYPE
        if ct_name not in self.content_types:
            new_content_type = ContentType()
            new_content_type.name = schema['name']
            new_content_type.plural_name = schema['plural_name']
            new_content_type.show_in_nav = schema['show_in_nav']
            new_content_type.proxy_field = schema['proxy_field']
            new_content_type.view_widget_url = schema.get('view_widget_url', None)
            new_content_type.edit_widget_url = schema.get('edit_widget_url', None)
            new_content_type.has_file_field = schema.get('has_file_field', False)
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

                if 'base_mongo_indexes' in schema and schema['base_mongo_indexes']:
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
                    new_field.has_intensity = field['has_intensity']
                    new_field.inherited = field['inherited']
                    new_field.synonym_file = field['synonym_file']

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

            if 'view_widgel_url' in schema:
                self.content_types[ct_name].view_widget_url = schema['view_widget_url']
            if 'edit_widget_url' in schema:
                self.content_types[ct_name].edit_widget_url = schema['edit_widget_url']

            if 'synonym_file' in schema:
                self.content_types[ct_name].synonym_file = schema['synonym_file']

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
                        new_field.type = schema['fields'][x]['type']
                        new_field.in_lists = schema['fields'][x].get('in_lists', default_field_values['in_lists'])
                        new_field.indexed = schema['fields'][x].get('indexed', default_field_values['indexed'])
                        new_field.indexed_with = schema['fields'][x].get('indexed_with', default_field_values['indexed_with'])
                        new_field.unique = schema['fields'][x].get('unique', default_field_values['unique'])
                        new_field.unique_with = schema['fields'][x].get('unique_with', default_field_values['unique_with'])
                        new_field.multiple = schema['fields'][x].get('multiple', default_field_values['multiple'])
                        new_field.inherited = schema['fields'][x].get('inherited', default_field_values['inherited'])
                        new_field.cross_reference_type = schema['fields'][x].get('cross_reference_type', default_field_values['cross_reference_type'])
                        new_field.has_intensity = schema['fields'][x].get('has_intensity', default_field_values['has_intensity'])
                        new_field.synonym_file = schema['fields'][x].get('synonym_file', default_field_values['synonym_file'])

                        self.content_types[ct_name].fields.append(new_field)
                        if new_field.in_lists:
                            reindex = True
                    else:
                        field_index = old_fields[schema['fields'][x]['name']]
                        self.content_types[ct_name].fields[field_index].label = schema['fields'][x]['label']

                        if self.content_types[ct_name].fields[field_index].in_lists != schema['fields'][x].get('in_lists', default_field_values['in_lists']) and \
                                self.content_types[ct_name].fields[field_index].type != 'embedded':
                            self.content_types[ct_name].fields[field_index].in_lists = schema['fields'][x].get('in_lists', default_field_values['in_lists'])
                            reindex = True

                        if not self.content_types[ct_name].fields[field_index].inherited:
                            self.content_types[ct_name].fields[field_index].type = schema['fields'][x]['type']
                            self.content_types[ct_name].fields[field_index].indexed = schema['fields'][x].get('indexed', default_field_values['indexed'])
                            self.content_types[ct_name].fields[field_index].indexed_with = schema['fields'][x].get('indexed_with', default_field_values['indexed_with'])
                            self.content_types[ct_name].fields[field_index].unique = schema['fields'][x].get('unique', default_field_values['unique'])
                            self.content_types[ct_name].fields[field_index].unique_with = schema['fields'][x].get('unique_with', default_field_values['unique_with'])
                            self.content_types[ct_name].fields[field_index].multiple = schema['fields'][x].get('multiple', default_field_values['multiple'])
                            self.content_types[ct_name].fields[field_index].cross_reference_type = schema['fields'][x].get('cross_reference_type', default_field_values['cross_reference_type'])
                            self.content_types[ct_name].fields[field_index].has_intensity = schema['fields'][x].get('has_intensity', default_field_values['has_intensity'])
                            self.content_types[ct_name].fields[field_index].synonym_file = schema['fields'][x].get('synonym_file', default_field_values['synonym_file'])

            if not valid:
                self.reload()

        if valid:
            related_content_types = []

            # ENSURE NEO4J INDEXES ON NEW CONTENT TYPE AND DEPENDENT NODES
            if not existing:
                new_node_indexes = [ct_name]
                if 'dependent_nodes' in schema:
                    for dependent_node in schema['dependent_nodes']:
                        new_node_indexes.append(dependent_node)

                ensure_neo_indexes(new_node_indexes)

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
                if field.type in ['file', 'repo']:
                    self.content_types[ct_name].has_file_field = True
                    break

            if not had_file_field and self.content_types[ct_name].has_file_field:
                resave = True

            if reindex or relabel or resave:
                queued_job_ids.append(self.queue_local_job(task_name="Adjust Content", parameters={
                    'content_type': ct_name,
                    'reindex': reindex,
                    'relabel': relabel,
                    'resave': resave,
                    'related_content_types': ','.join(related_content_types)
                }))

            self.save()

        return queued_job_ids

    def delete_content_type(self, content_type):
        if content_type in self.content_types:
            # Delete Neo4J nodes
            # Commenting out deletion of child nodes:
            # Sometimes child nodes are valid instances of content type
            # nodes_deleted = 1
            # while nodes_deleted > 0:
            #    nodes_deleted = run_neo(
            #        '''
            #            MATCH (n:{0} {{corpus_id: $corpus_id}}) -[*]-> (x {{corpus_id: $corpus_id}})
            #            WITH x LIMIT 1000
            #            DETACH DELETE x
            #            RETURN count(*)
            #        '''.format(content_type),
            #        {'corpus_id': str(self.id)}
            #    )[0][0]

            nodes_deleted = 1
            while nodes_deleted > 0:
                nodes_deleted = run_neo(
                    '''
                        MATCH (x:{0} {{corpus_id: $corpus_id}})
                        WITH x LIMIT 1000
                        DETACH DELETE x
                        RETURN count(*)
                    '''.format(content_type),
                    {'corpus_id': str(self.id)}
                )[0][0]

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
                'large_text': 'large_text',
                'keyword': 'keyword',
                'html': 'text',
                'number': 'integer',
                'decimal': 'float',
                'boolean': 'boolean',
                'date': 'date',
                'file': 'keyword',
                'image': 'keyword',
                'iiif-image': 'keyword',
                'link': 'keyword',
                'cross_reference': None,
                'document': 'text',
            }

            index_name = "corpus-{0}-{1}".format(self.id, ct.name.lower())
            index = Index(index_name)
            if index.exists():
                index.delete()

            label_analyzer = analyzer(
                'corpora_label_analyzer',
                tokenizer='classic',
                filter=['stop', 'lowercase', 'classic']
            )

            mapping = Mapping()
            mapping.field('label', 'text', analyzer=label_analyzer, fields={'raw': Keyword()})
            mapping.field('uri', 'keyword')

            for field in ct.fields:
                if field.type != 'embedded' and field.in_lists:
                    field_type = field_type_map[field.type]

                    if field.type == 'cross_reference' and field.cross_reference_type in self.content_types:
                        xref_ct = self.content_types[field.cross_reference_type]
                        xref_mapping_props = {
                            'id': 'keyword',
                            'label': {
                                'type': 'text',
                                'analyzer': label_analyzer,
                                'fields': {
                                    'raw': {
                                        'type': 'keyword'
                                    }
                                }
                            },
                            'uri': 'keyword'
                        }

                        if field.has_intensity:
                            xref_mapping_props['intensity'] = 'integer'

                        for xref_field in xref_ct.fields:
                            if xref_field.in_lists and not xref_field.type == 'cross_reference':
                                xref_field_type = field_type_map[xref_field.type]

                                if xref_field.type in ['text', 'large_text', 'html']:

                                    xref_field_type = {
                                        'type': 'text',
                                        'analyzer': xref_field.get_elasticsearch_analyzer(),
                                    }

                                    if xref_field.type == 'text':
                                        xref_field_type['fields'] = {
                                            'raw': {
                                                'type': 'keyword'
                                            }
                                        }

                                xref_mapping_props[xref_field.name] = xref_field_type

                        mapping.field(field.name, Nested(properties=xref_mapping_props))

                    elif field_type == 'text':
                        subfields = {'raw': {'type': 'keyword'}}
                        mapping.field(field.name, field_type, analyzer=field.get_elasticsearch_analyzer(), fields=subfields)

                    # large text fields assumed too large to provide a "raw" subfield for sorting
                    elif field_type in ['large_text', 'html']:
                        mapping.field(field.name, 'text', analyzer=field.get_elasticsearch_analyzer())
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

    def import_content_crystal(self, path):
        content_path = None
        crystal_path = None
        last_step = path.split('/')[-1]

        if last_step.endswith('.json'):
            crystal_path = path
            content_path = os.path.dirname(path)
        else:
            content_path = path
            crystal_path = "{0}/{1}.json".format(path, last_step)

        if content_path and crystal_path and os.path.exists(content_path) and os.path.exists(crystal_path):
            content_dict = None
            with open(crystal_path, 'r', encoding='utf-8') as crystal_in:
                content_dict = json.load(crystal_in)

            if content_dict:
                ct_name = content_dict['content_type']
                if ct_name in self.content_types:
                    ct = self.content_types[ct_name]
                    old_corpus_id = content_dict['corpus_id']

                    content_json = None
                    with open(crystal_path, 'r', encoding='utf-8') as crystal_in:
                        content_json = crystal_in.read()

                    content_json = content_json.replace(old_corpus_id, str(self.id))
                    content_dict = json.loads(content_json)

                    content_obj = self.get_content(ct_name)
                    content_obj.id = ObjectId(content_dict['id'])
                    content_obj.label = content_dict['label']
                    content_obj.uri = content_dict['uri']

                    successfully_saved = False

                    if ct.inherited_from_module:
                        from_dict_method = getattr(content_obj, "from_dict", None)
                        if callable(from_dict_method):
                            content_obj.from_dict(content_dict)
                            content_obj.save()
                            successfully_saved = True
                    else:
                        all_fields_present = True
                        for field in ct.fields:
                            if field.name in content_dict:
                                setattr(content_obj, field.name, content_dict[field.name])
                            else:
                                all_fields_present = False
                                break

                        if all_fields_present:
                            content_obj.save()
                            successfully_saved = True

                    if successfully_saved:
                        content_files = [f for f in os.listdir(content_path) if not f.startswith('.')]
                        if len(content_files) > 1:
                            content_obj._make_path(force=True)
                            shutil.copytree(content_path, content_obj.path, dirs_exist_ok=True)

    def _make_path(self):
        corpus_path = "/corpora/{0}".format(self.id)
        os.makedirs("{0}/files".format(corpus_path), exist_ok=True)
        return corpus_path

    @property
    def redis_cache(self):
        if not hasattr(self, '_redis_cache'):
            setattr(self, '_redis_cache', redis.Redis(host=settings.REDIS_HOST, decode_responses=True))
        return self._redis_cache

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
        corpus_id = str(document.id)

        # Delete Content Type indexes and collections
        for content_type in document.content_types.keys():
            # Delete ct index
            index_name = "corpus-{0}-{1}".format(corpus_id, content_type.lower())
            index = Index(index_name)
            if index.exists():
                index.delete()

            # Drop ct MongoDB collection
            document.content_types[content_type].get_mongoengine_class(document).drop_collection()

        # Delete all Neo4J nodes associated with corpus
        run_neo(
            '''
                MATCH (x {corpus_id: $corpus_id})
                DETACH DELETE x
            ''',
            {'corpus_id': corpus_id}
        )
        run_neo(
            '''
                MATCH (x:Corpus {uri: $corpus_uri})
                DETACH DELETE x
            ''',
            {'corpus_uri': '/corpus/{0}'.format(corpus_id)}
        )

        # Delete any available_corpora entries in Scholar objects
        scholars = Scholar.objects
        scholars = scholars.batch_size(10)
        for scholar in scholars:
            if corpus_id in scholar.available_corpora.keys():
                del scholar.available_corpora[corpus_id]
                scholar.save()

        # Remove corpus from ES index
        es_corpus_doc = Search(index='corpora').query("match", _id=corpus_id)
        es_corpus_doc.delete()

        # Delete corpus files
        if os.path.exists(document.path):
            shutil.rmtree(document.path)
        
    def to_dict(self, include_views=False):
        corpus_dict = {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'path': self.path,
            'uri': self.uri,
            'kvp': deepcopy(self.kvp),
            'open_access': self.open_access,
            'files': {},
            'repos': {},
            'content_types': {},
        }

        for file_key in self.files:
            corpus_dict['files'][file_key] = self.files[file_key].to_dict(parent_uri=self.uri)

        for repo_name in self.repos:
            corpus_dict['repos'][repo_name] = self.repos[repo_name].to_dict()

        for ct_name in self.content_types:
            corpus_dict['content_types'][ct_name] = self.content_types[ct_name].to_dict()

        if include_views:
            content_views = ContentView.objects(corpus=self.id, status='populated').order_by('name')
            for cv in content_views:
                if cv.target_ct in corpus_dict['content_types']:
                    if 'views' not in corpus_dict['content_types'][cv.target_ct]:
                        corpus_dict['content_types'][cv.target_ct]['views'] = []
                    corpus_dict['content_types'][cv.target_ct]['views'].append(cv.to_dict())

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


class CorpusExport(mongoengine.Document):
    corpus_id = mongoengine.StringField()
    corpus_name = mongoengine.StringField()
    corpus_description = mongoengine.StringField()
    name = mongoengine.StringField(unique_with='corpus_id')
    path = mongoengine.StringField()
    status = mongoengine.StringField()
    created = mongoengine.DateTimeField(default=datetime.now())


class Content(mongoengine.Document):
    corpus_id = mongoengine.StringField(required=True)
    content_type = mongoengine.StringField(required=True)
    last_updated = mongoengine.DateTimeField(default=datetime.now())
    provenance = mongoengine.EmbeddedDocumentListField(CompletedTask)
    field_intensities = mongoengine.DictField(default={})
    path = mongoengine.StringField()
    label = mongoengine.StringField()
    uri = mongoengine.StringField()

    def get_intensity(self, field_name, value):
        if hasattr(self, field_name):
            if type(value) is ObjectId:
                value = str(ObjectId)
            elif hasattr(value, 'id'):
                value = str(value.id)

            if type(value) is str:
                return self.field_intensities.get('{field_name}-{value}'.format(field_name=field_name, value=value), 0)
        return 0

    def set_intensity(self, field_name, value, intensity):
        if hasattr(self, field_name):
            if type(value) is ObjectId:
                value = str(ObjectId)
            elif hasattr(value, 'id'):
                value = str(value.id)

            if type(value) is str:
                self.field_intensities['{field_name}-{value}'.format(field_name=field_name, value=value)] = int(intensity)

    @classmethod
    def _pre_save(cls, sender, document, **kwargs):
        document.last_updated = datetime.now()

    def save(self, do_indexing=True, do_linking=True, relabel=True, **kwargs):
        super().save(**kwargs)
        path_created = self._make_path()
        label_created = self._make_label(relabel)
        uri_created = self._make_uri()

        if path_created or label_created or uri_created:
            self.update(
                set__path=self.path,
                set__label=self.label,
                set__uri=self.uri
            )

        if do_indexing or do_linking:
            cx_fields = [field.name for field in self._ct.fields if field.type == 'cross_reference']
            if cx_fields:
                self.reload(*cx_fields)

            if do_indexing:
                self._do_indexing()
            if do_linking:
                self._do_linking()

    @classmethod
    def _pre_delete(cls, sender, document, **kwargs):
        # delete Neo4J node
        run_neo(
            '''
                MATCH (d:{content_type} {{ uri: $content_uri }})
                DETACH DELETE d
            '''.format(content_type=document.content_type),
            {
                'content_uri': document.uri
            }
        )

        # delete from ES index
        es_index = "corpus-{0}-{1}".format(document.corpus_id, document.content_type.lower())
        Search(index=es_index).query("match", _id=str(document.id)).delete()

        # mark any relevant content views as needs_refresh
        cvs = ContentView.objects(corpus=document._corpus, status='populated', relevant_cts=document.content_type)
        for cv in cvs:
            print(cv.name)
            cv.set_status('needs_refresh')
            cv.save()

        # delete any files
        if document.path and os.path.exists(document.path):
            document._corpus.queue_local_job(task_name="Content Deletion Cleanup", parameters={'content_path': document.path})

    def _make_label(self, force=True):
        if force or not self.label:
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

    def _make_path(self, force=False):
        if not self.path and (self._ct.has_file_field or force):
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
                    self.path + "/files"
                )

                os.rename(old_path, new_path)

                new_file = File.process(
                    new_path,
                    parent_uri=self.uri,
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
                if field_value or ((field.type == 'number' or field.type == 'decimal') and field_value == 0):
                    if field.cross_reference_type:
                        if field.multiple:
                            field_value = []
                            for xref in getattr(self, field.name):
                                xref_dict = {
                                    'id': str(xref.id),
                                    'label': xref.label,
                                    'uri': xref.uri
                                }

                                if field.has_intensity:
                                    xref_dict['intensity'] = self.field_intensities.get(
                                        '{field_name}-{val_id}'.format(field_name=field.name, val_id=xref.id),
                                        1
                                    )

                                for xref_field in self._corpus.content_types[field.cross_reference_type].fields:
                                    if xref_field.in_lists and not xref_field.cross_reference_type:
                                        xref_dict[xref_field.name] = xref_field.get_dict_value(getattr(xref, xref_field.name), xref.uri)
                                field_value.append(xref_dict)
                        else:
                            xref = field_value
                            field_value = {
                                'id': str(xref.id),
                                'label': xref.label,
                                'uri': xref.uri
                            }

                            if field.has_intensity:
                                field_value['intensity'] = self.field_intensities.get(
                                    '{field_name}-{val_id}'.format(field_name=field.name, val_id=xref.id),
                                    1
                                )

                            for xref_field in self._corpus.content_types[field.cross_reference_type].fields:
                                if xref_field.in_lists and xref_field.type != "cross_reference":
                                    field_value[xref_field.name] = xref_field.get_dict_value(getattr(xref, xref_field.name), xref.uri)

                        index_obj[field.name] = field_value

                    elif field.type == 'file' and hasattr(field_value, 'path'):
                        index_obj[field.name] = field_value.path

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
        # here we're making sure the node exists
        run_neo(
            '''
                MERGE (d:{content_type} {{ uri: $content_uri }})
                SET d.id = $content_id
                SET d.corpus_id = $corpus_id
                SET d.label = $content_label
            '''.format(content_type=self.content_type),
            {
                'corpus_id': str(self.corpus_id),
                'content_uri': self.uri,
                'content_id': str(self.id),
                'content_label': self.label
            }
        )

        # here we're deleting all outbound relationships (they will be rebuilt below as necessary);
        # this is to ensure changed or deleted cross references are reflected in the graph (no stale
        # relationships)
        run_neo(
            '''
                MATCH (d:{content_type} {{ uri: $content_uri }}) -[rel]-> ()
                DELETE rel
            '''.format(content_type=self.content_type),
            {
                'content_uri': self.uri,
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
                            node_dict = {
                                'id': cross_ref.id,
                                'uri': cross_ref.uri,
                                'label': cross_ref.label,
                                'field': field.name
                            }

                            if field.has_intensity:
                                node_dict['intensity'] = self.field_intensities.get(
                                    '{field_name}-{val_id}'.format(field_name=field.name, val_id=cross_ref.id),
                                    1
                                )

                            nodes[cross_ref_type].append(node_dict)
                    else:
                        node_dict = {
                            'id': field_value.id,
                            'uri': field_value.uri,
                            'label': field_value.label,
                            'field': field.name
                        }

                        if field.has_intensity:
                            node_dict['intensity'] = self.field_intensities.get(
                                '{field_name}-{val_id}'.format(field_name=field.name, val_id=field_value.id),
                                1
                            )

                        nodes[cross_ref_type].append(node_dict)

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
                    intensity_specifier = ''
                    if 'intensity' in node:
                        intensity_specifier = ' {{ intensity: {0} }}'.format(node['intensity'])

                    run_neo(
                        '''
                            MERGE (a:{content_type} {{ uri: $content_uri }})
                            MERGE (b:{cx_type} {{ uri: $cx_uri }})
                            MERGE (a)-[rel:has{field}{intensity_specifier}]->(b)
                        '''.format(
                            content_type=self.content_type,
                            cx_type=node_label,
                            field=node['field'],
                            intensity_specifier=intensity_specifier
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
                content_dict[field.name] = field.get_dict_value(getattr(self, field.name), self.uri, self.field_intensities)

        return content_dict

    def from_dict(self, field_values):
        for field in field_values.keys():
            if field == 'id':
                field_values[field] = ObjectId(field_values[field])
            setattr(self, field, field_values[field])

    def crystalize(self):
        if not self.path:
            self._make_path(force=True)
            self.update(set__path=self.path)

        make_crystal = True
        crystal_path = "{0}/{1}.json".format(self.path, self.id)
        if os.path.exists(crystal_path):
            crystal_updated = datetime.fromtimestamp(os.path.getmtime(crystal_path))
            if crystal_updated > self.last_updated:
                make_crystal = False

        if make_crystal:
            with open(crystal_path, 'w', encoding='utf-8') as crystal_out:
                json.dump(self.to_dict(), crystal_out, indent=4)

    meta = {
        'abstract': True
    }


class ContentView(mongoengine.Document):
    corpus = mongoengine.ReferenceField(Corpus)
    created_by = mongoengine.ReferenceField(Scholar)
    name = mongoengine.StringField(unique_with='corpus')
    target_ct = mongoengine.StringField()
    relevant_cts = mongoengine.ListField(mongoengine.StringField())
    search_filter = mongoengine.StringField()
    graph_path = mongoengine.StringField()
    es_document_id = mongoengine.StringField()
    neo_super_node_uri = mongoengine.StringField()
    status = mongoengine.StringField()
    status_date = mongoengine.DateTimeField(default=datetime.now())

    def set_status(self, status):
        self.status = status
        self.status_date = datetime.now()

    def populate(self):
        valid_spec = True
        filtered_with_graph_path = False
        es_conn = get_connection()
        index = Index('content_view')

        if index.exists() and \
                self.name and \
                self.corpus and \
                self.target_ct in self.corpus.content_types:

            ids = []
            graph_steps = {}

            if not self.es_document_id or not self.neo_super_node_uri:
                name_slug = slugify(self.name).replace('-', '_')
                view_identifier = "corpus_{0}_{1}".format(self.corpus.id, name_slug)
                self.es_document_id = view_identifier
                self.neo_super_node_uri = "/contentview/{0}".format(view_identifier)
            else:
                run_neo("MATCH (supernode:ContentView { uri: $cv_uri }) DETACH DELETE supernode", {'cv_uri': self.neo_super_node_uri})

            self.relevant_cts = [self.target_ct]
            self.set_status("populating")
            self.save()

            if self.graph_path:
                ct_pattern = re.compile(r'\(([a-zA-Z]*)')
                ids_pattern = re.compile(r'\[([^\]]*)\]')

                graph_step_specs = [step for step in self.graph_path.split('-') if step]
                for step_index in range(0, len(graph_step_specs)):
                    step_spec = graph_step_specs[step_index]
                    step_ct = None
                    step_ids = []

                    ct_match = re.search(ct_pattern, step_spec)
                    if ct_match:
                        step_ct = ct_match.group(1)

                    ids_match = re.search(ids_pattern, step_spec)
                    if ids_match:
                        step_ids = [ct_id for ct_id in ids_match.group(1).split(',') if ct_id]

                    if step_ct and step_ct in self.corpus.content_types:
                        graph_steps[step_index] = {'ct': step_ct, 'ids': step_ids}
                        self.relevant_cts.append(step_ct)
                    else:
                        valid_spec = False
                        break

                if graph_steps and valid_spec:
                    match_nodes = []
                    where_clauses = []

                    for step_index, step_info in graph_steps.items():
                        match_nodes.append("(ct{0}:{1})".format(step_index, step_info['ct']))
                        if step_info['ids']:
                            step_uris = ['/corpus/{0}/{1}/{2}'.format(self.corpus.id, step_info['ct'], ct_id) for ct_id in step_info['ids']]
                            where_clauses.append("ct{0}.uri in ['{1}']".format(
                                step_index,
                                "','".join(step_uris)
                            ))

                    cypher = "MATCH (target:{0}) -- {1}".format(self.target_ct, " -- ".join(match_nodes))
                    if where_clauses:
                        cypher += "\nWHERE {0}".format(" AND ".join(where_clauses))

                    count_cypher = cypher + "\nRETURN count(distinct target)"
                    data_cypher = cypher + "\nRETURN distinct target.uri"

                    try:
                        count_results = run_neo(count_cypher, {})
                        count = count_results[0].value()

                        if count <= 60000:
                            data_results = run_neo(data_cypher, {})
                            ids = [res.value().split('/')[-1] for res in data_results]
                            es_conn.index(
                                index='content_view',
                                id=self.es_document_id,
                                body={
                                    'ids': ids,
                                }
                            )

                            filtered_with_graph_path = True
                        else:
                            valid_spec = False
                            self.set_status("error: content views must contain less than 60,000 results")

                    except:
                        print(traceback.format_exc())
                        valid_spec = False
                        self.set_status("error")
                        self.save()

            if self.search_filter and valid_spec and self.status == 'populating':

                search_dict = json.loads(self.search_filter)
                if filtered_with_graph_path:
                    search_dict['content_view'] = self.es_document_id

                search_dict['page_size'] = 1000
                search_dict['only'] = ['id']

                ids = []
                page = 1
                num_pages = 1

                while page <= num_pages and valid_spec:
                    search_dict['page'] = page
                    results = self.corpus.search_content(self.target_ct, **search_dict)
                    if results:
                        if results['meta']['num_pages'] > num_pages:
                            num_pages = results['meta']['num_pages']

                        if results['meta']['total'] <= 60000:
                            for record in results['records']:
                                ids.append(record['id'])
                        else:
                            valid_spec = False
                            self.set_status("error: content views must contain less than 60,000 results")

                    page += 1

                if valid_spec:
                    es_conn.index(
                        index='content_view',
                        id=self.es_document_id,
                        body={
                            'ids': ids,
                        }
                    )

            if valid_spec and ids:
                total = len(ids)
                cursor = 0
                window = 1000

                run_neo("MERGE (cv:_ContentView { uri: $cv_uri })", {'cv_uri': self.neo_super_node_uri})

                supernode_cypher = '''
                    MATCH (cv:_ContentView {{ uri: $cv_uri }}), (target:{0})
                    WHERE target.uri IN $uris 
                    MERGE (cv) -[rel:hasContent]-> (target)
                '''.format(self.target_ct)

                while cursor < total:
                    uris = ["/corpus/{0}/{1}/{2}".format(self.corpus.id, self.target_ct, id) for id in ids[cursor:window]]
                    run_neo(
                        supernode_cypher,
                        {
                            'cv_uri': self.neo_super_node_uri,
                            'uris': uris
                        }
                    )
                    cursor += window
                self.set_status("populated")

            self.save()

    def clear(self):
        # delete ES content_view document
        Search(index='content_view').query('match', _id=self.es_document_id).delete()

        # delete Neo super node
        run_neo(
            '''
                MATCH (cv:_ContentView { uri: $cv_uri })
                DETACH DELETE cv
            ''',
            {
                'cv_uri': self.neo_super_node_uri
            }
        )

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'es_document_id': self.es_document_id,
            'neo_super_node_uri': self.neo_super_node_uri,
            'target_ct': self.target_ct,
            'status': self.status
        }

# SIGNALS FOR HANDLING MONGOENGINE DOCUMENT PRE/POST-DELETION (mostly for deleting Neo4J nodes)
mongoengine.signals.post_save.connect(Corpus._post_save, sender=Corpus)
mongoengine.signals.post_delete.connect(Scholar._post_delete, sender=Scholar)
mongoengine.signals.post_delete.connect(Task._post_delete, sender=Task)
mongoengine.signals.post_delete.connect(JobSite._post_delete, sender=JobSite)
mongoengine.signals.pre_delete.connect(Corpus._pre_delete, sender=Corpus)


# UTILITY CLASSES / FUNCTIONS
def get_corpus(corpus_id, only=[]):
    try:
        corpus = Corpus.objects(id=corpus_id)
        if only:
            corpus = corpus.only(*only)
        return corpus[0]
    except:
        return None


def search_corpora(
        search_dict,
        ids=[],
        open_access_only=False
):
    results = {
        'meta': {
            'content_type': 'Corpus',
            'total': 0,
            'page': search_dict['page'],
            'page_size': search_dict['page_size'],
            'num_pages': 1,
            'has_next_page': False
        },
        'records': []
    }

    start_index = (search_dict['page'] - 1) * search_dict['page_size']
    end_index = search_dict['page'] * search_dict['page_size']

    index = "corpora"
    should = []
    must = []
    if search_dict['general_query']:
        should.append(SimpleQueryString(query=search_dict['general_query']))

    if 'fields_query' in search_dict and search_dict['fields_query']:
        for search_field in search_dict['fields_query'].keys():
            must.append(Q('match', **{search_field: search_dict['fields_query'][search_field]}))

    if ids:
        must.append(Q('terms', _id=ids) | Q('match', open_access=True))
    elif open_access_only:
        must.append(Q('match', open_access=True))

    if should or must:
        search_query = Q('bool', should=should, must=must)
        search_cmd = Search(using=get_connection(), index=index, extra={'track_total_hits': True}).query(search_query)

        if 'fields_sort' in search_dict and search_dict['fields_sort']:
            search_cmd = search_cmd.sort(*search_dict['fields_sort'])

        search_cmd = search_cmd[start_index:end_index]
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


def search_scholars(search_dict):
    page = search_dict.get('page', 1)
    page_size = search_dict.get('page_size', 50)
    general_query = search_dict.get('general_query', '*')
    fields_query = search_dict.get('fields_query', None)
    fields_sort = search_dict.get('fields_sort', None)

    results = {
        'meta': {
            'content_type': 'Scholar',
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

    index = "scholar"
    should = []
    must = []
    if general_query:
        should.append(SimpleQueryString(query=general_query))

    if fields_query:
        for search_field in fields_query.keys():
            must.append(Q('match', **{search_field: fields_query[search_field]}))

    if should or must:
        search_query = Q('bool', should=should, must=must)
        search_cmd = Search(using=get_connection(), index=index, extra={'track_total_hits': True}).query(search_query)

        if fields_sort:
            search_cmd = search_cmd.sort(*fields_sort)

        search_cmd = search_cmd[start_index:end_index]
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


def run_neo(cypher, params={}, tries=0):
    results = None
    with settings.NEO4J.session() as neo:
        try:
            results = list(neo.run(cypher, **params))
        except:
            error = traceback.format_exc()
            if 'defunct connection' in error and tries < 3:
                print("Attempting to recover from stale Neo4J connection...")
                neo.close()
                return run_neo(cypher, params, tries + 1)

            print("Error running Neo4J cypher!")
            print("Cypher: {0}".format(cypher))
            print("Params: {0}".format(json.dumps(params, indent=4)))
            print(error)
        finally:
            neo.close()
    return results


def get_network_json(cypher):
    net_json = {
        'nodes': [],
        'edges': [],
    }

    node_id_to_uri_map = {}
    rel_ids = []

    results = run_neo(cypher)

    for result in results:
        graph = result.items()[0][1].graph

        for node in graph.nodes:
            if node.id not in node_id_to_uri_map:
                node_props = {}
                for key, val in node.items():
                    node_props[key] = val

                uri = node_props.get('uri', str(node.id))
                label = node_props.get('label', str(node.id))
                node_type = list(node.labels)[0]

                if node_type == 'Corpus':
                    label = node_props.get('name', str('Corpus'))

                net_json['nodes'].append({
                    'id': uri,
                    'group': node_type,
                    'label': label
                })

                node_id_to_uri_map[node.id] = uri

        for rel in graph.relationships:
            if rel.id not in rel_ids and rel.start_node.id in node_id_to_uri_map and rel.end_node.id in node_id_to_uri_map:
                edge_dict = {
                    'id': str(rel.id),
                    'title': rel.type,
                    'from': node_id_to_uri_map[rel.start_node.id],
                    'to': node_id_to_uri_map[rel.end_node.id],
                }

                intensity = rel.get('intensity')
                if intensity:
                    edge_dict['value'] = intensity

                net_json['edges'].append(edge_dict)

                rel_ids.append(rel.id)

    return net_json


def ensure_neo_indexes(node_names):
    existing_node_indexes = [row['tokenNames'][0] for row in run_neo("CALL db.indexes", {})]
    for node_name in node_names:
        if node_name not in existing_node_indexes:
            run_neo("CREATE CONSTRAINT ON(ct:{0}) ASSERT ct.uri IS UNIQUE".format(node_name), {})
            run_neo("CREATE INDEX ON :{0}(corpus_id)".format(node_name), {})


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
