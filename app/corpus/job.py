import traceback
import mongoengine
from copy import deepcopy
from datetime import datetime
from django.conf import settings
from .utilities import run_neo, publish_message


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


# rig up post delete signal for Task
mongoengine.signals.post_delete.connect(Task._post_delete, sender=Task)


class CompletedTask(mongoengine.EmbeddedDocument):
    job_id = mongoengine.StringField()
    task_name = mongoengine.StringField()
    task_version = mongoengine.StringField()
    task_configuration = mongoengine.DictField()
    scholar_name = mongoengine.StringField()
    submitted = mongoengine.DateTimeField()
    completed = mongoengine.DateTimeField()
    status = mongoengine.StringField()
    report_path = mongoengine.StringField()
    error = mongoengine.StringField()

    @classmethod
    def from_dict(cls, prov_info):
        prov = CompletedTask()
        for attr in [
            'job_id',
            'task_name',
            'task_version',
            'task_configuration',
            'scholar_name',
            'submitted',
            'completed',
            'status',
            'report_path',
            'error'
        ]:
            if attr in prov_info:
                setattr(prov, attr, prov_info[attr])

        return prov

    def to_dict(self):
        return {
            'job_id': self.job_id,
            'task_name': self.task_name,
            'task_version': self.task_version,
            'task_configuration': deepcopy(self.task_configuration),
            'scholar_name': self.scholar_name,
            'submitted': int(self.submitted.timestamp()),
            'completed': int(self.completed.timestamp()),
            'status': self.status,
            'report_path': self.report_path,
            'error': self.error
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


# rig up post delete signal for JobSite
mongoengine.signals.post_delete.connect(JobSite._post_delete, sender=JobSite)


class Process(mongoengine.EmbeddedDocument):
    id = mongoengine.StringField()
    status = mongoengine.StringField()
    created = mongoengine.DateTimeField(default=datetime.now())


class Job(object):
    def __new__(cls, job_id=None):
        if job_id:
            job_tracker = None
            try:
                job_tracker = JobTracker.objects(id=job_id)[0]
            except:
                job_tracker = None

            return job_tracker
        return JobTracker()

    @staticmethod
    def setup_retry_for_completed_task(corpus, scholar, content_type, content_id, completed_task):
        task_matches = Task.objects.filter(name=completed_task.task_name, version=completed_task.task_version)
        if task_matches.count() == 1:
            task = task_matches[0]
            local_jobsite = JobSite.objects(name='Local')[0]

            j = Job()
            j.id = completed_task.job_id
            j.corpus = corpus
            j.content_type = content_type
            j.content_id = content_id
            j.task_id = str(task.id)
            j.jobsite = local_jobsite
            j.scholar = scholar
            j.configuration = deepcopy(completed_task.task_configuration)
            j.save()
            return j

        return None

    @staticmethod
    def get_jobs(corpus_id=None, content_type=None, content_id=None, count_only=False, limit=None, skip=0):
        jobs = JobTracker.objects()
        if corpus_id:
            jobs = jobs.filter(corpus=corpus_id)

            if content_type:
                jobs = jobs.filter(content_type=content_type)

                if content_id:
                    jobs = jobs.filter(content_id=content_id)

        if count_only:
            counts = {
                'total': jobs.count(),
                'by_status': {},
                'by_task': {},
            }

            by_status_pipeline = [{"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }},
            {"$group": {
                "_id": None,
                "counts": {
                    "$push": {"k": "$_id", "v": "$count"}
                }
            }},
            {"$replaceRoot": {
                "newRoot": {"$arrayToObject": "$counts"}
            }}]
            counts['by_status'] = [s for s in jobs.aggregate(by_status_pipeline)]

            by_task_pipeline = [{"$group": {
                "_id": "$task_id",
                "count": {"$sum": 1}
            }},
                {"$group": {
                    "_id": None,
                    "counts": {
                        "$push": {"k": "$_id", "v": "$count"}
                    }
                }},
                {"$replaceRoot": {
                    "newRoot": {"$arrayToObject": "$counts"}
                }}]
            counts['by_task'] = [s for s in jobs.aggregate(by_task_pipeline)]

            return counts
        elif skip and limit:
            jobs = jobs[skip:(skip + limit)]
        elif limit:
            jobs = jobs[:limit]
        elif skip:
            jobs = jobs[skip:]

        return jobs


class JobTracker(mongoengine.Document):
    corpus = mongoengine.ReferenceField('Corpus')
    content_type = mongoengine.StringField()
    content_id = mongoengine.StringField()
    task_id = mongoengine.StringField()
    jobsite = mongoengine.ReferenceField(JobSite)
    scholar = mongoengine.ReferenceField('Scholar')
    submitted_time = mongoengine.DateTimeField(default=datetime.now)
    status = mongoengine.StringField(default='queueing')
    status_time = mongoengine.DateTimeField(default=datetime.now)
    report_path = mongoengine.StringField()
    stage = mongoengine.IntField(default=0)
    timeout = mongoengine.IntField()
    tries = mongoengine.IntField(default=0)
    error = mongoengine.StringField()
    configuration = mongoengine.DictField()
    processes = mongoengine.EmbeddedDocumentListField(Process)
    subprocesses_launched = mongoengine.MapField(mongoengine.BooleanField())
    subprocesses_completed = mongoengine.MapField(mongoengine.BooleanField())
    percent_complete = mongoengine.IntField(default=0)

    def to_dict(self):
        return {
            'id': str(self.id),
            'corpus_id': self.corpus_id,
            'content_type': self.content_type,
            'content_id': self.content_id,
            'task_id': self.task_id,
            'task_name': self.task.name,
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

        if status == 'running':
            if 'parameters' in self.configuration:
                for param in self.configuration['parameters']:
                    if 'type' in self.configuration['parameters'][param] and self.configuration['parameters'][param]['type'] == 'password':
                        self.configuration['parameters'][param]['value'] = '**********'

        self.save()
        self.publish_status()

    def publish_status(self):
        if self.percent_complete > 100:
            self.percent_complete = 100

        publish_message(self.corpus_id, 'job', {
            'job_id': self.id,
            'task_name': self.task.name if self.task else self.task_id,
            'status': self.status,
            'percent_complete': self.percent_complete,
        })

    def report(self, message, overwrite=False):
        if self.task and self.task.create_report and self.report_path:
            mode = 'a+'
            if overwrite:
                mode = 'w'

            with open(self.report_path, mode, encoding='utf-8') as report_out:
                report_out.write(message + '\n')

    def add_process(self, process_id):
        self.modify(**{f'set__subprocesses_launched__{process_id}': True})

    def complete_process(self, process_id):
        self.modify(**{f'set__subprocesses_completed__{process_id}': True})
        self.reload('subprocesses_launched', 'subprocesses_completed')

        if self.total_subprocesses_launched > 0:
            self.percent_complete = int((self.total_subprocesses_completed / self.total_subprocesses_launched) * 100)
            self.publish_status()

    def clear_processes(self):
        self.processes = []
        self.subprocesses_launched = {}
        self.subprocesses_completed = {}
        self.save()

    def kill(self):
        if self.processes:
            for proc in self.processes:
                task_id = proc.id
                if task_id:
                    try:
                        settings.HUEY.revoke_by_id(task_id)
                    except:
                        print('Attempt to revoke process {0} in Huey task queue failed:'.format(task_id))
                        print(traceback.format_exc())

        self.delete()

    @property
    def corpus_id(self):
        if self.corpus:
            return str(self.corpus.id)
        return None

    @property
    def content(self):
        if self.content_type == 'Corpus':
            return self.corpus
        if not hasattr(self, '_content'):
            self._content = self.corpus.get_content(self.content_type, self.content_id)
        return self._content

    @property
    def task(self):
        if not hasattr(self, '_task'):
            try:
                self._task = Task.objects(id=self.task_id)[0]
            except:
                self._task = None
        return self._task

    @property
    def jobsite_id(self):
        if self.jobsite:
            return str(self.jobsite.id)
        return None

    @property
    def scholar_id(self):
        if self.scholar:
            return str(self.scholar.id)
        return None

    @property
    def total_subprocesses_launched(self):
        return len(self.subprocesses_launched.keys())

    @property
    def total_subprocesses_completed(self):
        return len(self.subprocesses_completed.keys())

    def complete(self, status=None, error_msg=None):
        if status:
            self.status = status
            self.status_time = datetime.now()
        if error_msg:
            self.error = error_msg

        if self.report_path:
            if self.error:
                self.report(f"\nERROR: This job encountered the following problem and was unable to complete:\n\n{self.error}")
            else:
                self.report("\nCORPORA JOB COMPLETE")

        if self.content and self.task and self.task.track_provenance:
            scholar_name = "None"
            if self.scholar:
                scholar_name = f"{self.scholar.fname} {self.scholar.lname} ({self.scholar.username})".strip()

            ct = CompletedTask()
            ct.job_id = str(self.id)
            ct.task_name = self.task.name
            ct.task_version = self.task.version
            ct.task_configuration = deepcopy(self.configuration)
            ct.scholar_name = scholar_name
            ct.submitted = self.submitted_time
            ct.completed = self.status_time
            ct.report_path = self.report_path
            ct.status = self.status
            ct.error = self.error

            self.content.provenance.append(ct)
            self.content.save()

        self.publish_status()
        self.delete()


