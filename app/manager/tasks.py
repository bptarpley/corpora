import os
import shutil
import json
import importlib
import time
import traceback
import tarfile
import pymysql
import logging
import math
import redis
import re
from copy import deepcopy
from corpus import (
    Corpus, Job, get_corpus, File,
    run_neo, ContentView, ContentTypeGroup, ContentDeletion,
    CorpusBackup, JobSite, GitRepo, CompletedTask
)
from huey.contrib.djhuey import db_task, db_periodic_task
from huey import crontab
from bson.objectid import ObjectId
from urllib.parse import quote
from elasticsearch_dsl.connections import get_connection
from elasticsearch.helpers import scan
from PIL import Image
from datetime import datetime, timedelta
from subprocess import call
from manager.utilities import (
    _contains,
    build_search_params_from_dict,
    order_content_schema,
    process_content_bundle,
    delimit_content_json,
    publish_message
)
from django.conf import settings
from django.utils.text import slugify
from django.template.loader import get_template
from django.template.context import Context
from zipfile import ZipFile
from django_drf_filepond.models import TemporaryUpload


REGISTRY = {
    "Bulk Launch Jobs": {
        "version": "0.0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "content_type": {
                    "value": "",
                    "type": "content_type",
                    "label": "Content Type",
                },
                "task_id": {
                    "value": "",
                    "type": "text",
                    "label": "Task ID"
                },
                "query": {
                    "value": "",
                    "type": "text",
                    "label": "Content Search Query JSON"
                },
                "job_params": {
                    "value": "",
                    "type": "text",
                    "label": "Bulk Job Params JSON"
                },
            }
        },
        "module": 'manager.tasks',
        "functions": ['bulk_launch_jobs']
    },
    "Bulk Edit Content": {
        "version": "0.1",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "content_type": {
                    "value": "",
                    "type": "content_type",
                    "label": "Content Type"
                },
                "content_ids": {
                    "value": "",
                    "type": "text",
                    "label": "Bulk Edit IDs"
                },
                "content_query": {
                    "value": "",
                    "type": "text",
                    "label": "Content Search Query JSON"
                },
                "content_bundle": {
                    "value": "",
                    "type": "dict",
                    "label": "Content Bundle"
                },
                "scholar_id": {
                    "value": "",
                    "type": "text",
                    "label": "Scholar ID"
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['bulk_edit_content']
    },
    "Save Content Type Schema": {
        "version": "0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "schema": {
                    "value": "",
                    "type": "JSON",
                    "label": "Content Type Schema"
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['save_content_type_schema']
    },
    "Adjust Content": {
        "version": "0.4",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "create_report": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "content_type": {
                    "value": "",
                    "type": "content_type",
                    "label": "Content Type",
                },
                "reindex": {
                    "value": False,
                    "type": "boolean",
                    "label": "Re-index?",
                },
                "relabel": {
                    "value": False,
                    "type": "boolean",
                    "label": "Re-label?",
                },
                "relink": {
                    "value": False,
                    "type": "boolean",
                    "label": "Re-link?",
                },
                "resave": {
                    "value": False,
                    "type": "boolean",
                    "label": "Re-save?",
                },
                "related_content_types": {
                    "value": "",
                    "type": "text",
                    "label": "Related Content Types",
                },
                "resume_at": {
                    "value": 0,
                    "type": "number",
                    "label": "Resume Adjustments at Percentage"
                }
            },
        },
        "module": 'manager.tasks',
        "functions": ['adjust_content']
    },
    "Delete Content Type": {
        "version": "0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "content_type": {
                    "value": "",
                    "type": "content_type",
                    "label": "Content Type"
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['delete_content_type']
    },
    "Delete Content Type Field": {
        "version": "0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "content_type": {
                    "value": "",
                    "type": "content_type",
                    "label": "Content Type"
                },
                "field_name": {
                    "value": "",
                    "type": "field",
                    "label": "Field Name"
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['delete_content_type_field']
    },
    "Delete Corpus": {
        "version": "0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {},
        "module": 'manager.tasks',
        "functions": ['delete_corpus']
    },
    "Merge Content": {
        "version": "0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "content_type": {
                    "value": "",
                    "type": "content_type",
                    "label": "Content Type"
                },
                "target_id": {
                    "value": "",
                    "type": "text",
                    "label": "ID of Target of Merge"
                },
                "merge_ids": {
                    "value": "",
                    "type": "text",
                    "label": "IDs of Content to Merge",
                    "note": "IDs separated by comma."
                },
                "delete_merged": {
                    "value": True,
                    "type": "boolean",
                    "label": "Delete Merged Content?"
                },
                "cascade_deletion": {
                    "value": True,
                    "type": "boolean",
                    "label": "Cascade Deletion?",
                    "note": "Deletes any isolated content connected to merged content."
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['merge_content']
    },
    "Convert Foreign Key Field to Cross Reference": {
        "version": "0.2",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "source_ct_field": {
                    "value": "",
                    "type": "content_type_field",
                    "label": "Foreign Key Field",
                    "note": "Choose the content type and field containing the foreign key you wish to convert."
                },
                "target_ct_field": {
                    "value": "",
                    "type": "content_type_field",
                    "label": "Field Referenced by Foreign Key",
                    "note": "Choose the content type and field to which the foreign key refers."
                },
                "new_field_name": {
                    "value": "",
                    "type": "pep8_text",
                    "label": "New Field Name for Cross Reference",
                },
                "new_field_label": {
                    "value": "",
                    "type": "text",
                    "label": "Label for New Field",
                },
                "delete_old_field": {
                    "value": True,
                    "type": "boolean",
                    "label": "Delete Old Foreign Key Field After Conversion?"
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['convert_foreign_key_to_xref']
    },
    "Pull Repo": {
        "version": "0.1",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "repo_name": {
                    "value": "",
                    "type": "text",
                    "label": "Repo Name",
                },
                "repo_content_type": {
                    "value": "Corpus"
                },
                "repo_content_id": {
                    "value": None
                },
                "repo_field": {
                    "value": ""
                },
                "repo_field_multi_index": {
                    "value": None
                },
                "repo_user": {
                    "value": "",
                    "type": "text",
                    "label": "Repo User",
                    "note": "Optional"
                },
                "repo_pwd": {
                    "value": "",
                    "type": "text",
                    "label": "Repo Password",
                    "note": "Optional"
                },
            },
        },
        "module": 'manager.tasks',
        "functions": ['pull_repo']
    },
    "Content View Lifecycle": {
        "version": "0.0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "cv_id": {
                    "value": "",
                    "type": "text",
                    "label": "Content View ID"
                },
                "stage": {
                    "value": "",
                    "type": "text",
                    "label": "Content View Lifecycle Stage"
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['content_view_lifecycle']
    },
    "Backup Corpus": {
        "version": "0.2",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "create_report": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "backup_name": {
                    "value": "",
                    "type": "pep8_text",
                    "label": "Backup Name",
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['backup_corpus']
    },
    "Export Corpus": {
        "version": "0.2",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "create_report": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "export_html": {
                    "value": True,
                    "type": "boolean",
                    "label": "Export static HTML representations of content?",
                    "note": "By unchecking this box, only JSON exports of your content will be created."
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['export_corpus']
    }
}


@db_task(priority=3)
def run_job(job_id):
    job = Job(job_id)

    if job:
        if job.jobsite.type == 'HUEY':
            try:
                if job.task.create_report:
                    corpus_job_reports_path = "{0}/job_reports".format(job.corpus.path)
                    if not os.path.exists(corpus_job_reports_path):
                        os.makedirs(corpus_job_reports_path, exist_ok=True)

                    report_path = "{0}/{1}.txt".format(corpus_job_reports_path, job.id)
                    job.report_path = report_path
                    job.save()

                    scholar_string = "None"
                    if job.scholar_id:
                        scholar_string = "{0} {1}".format(
                            job.scholar.fname,
                            job.scholar.lname if job.scholar.lname else ''
                        )

                    job.report('''##########################################################
Job ID:         {0}
Task Name:      {1}
Scholar:        {2}
Corpus ID:      {3}
Content Type:   {4}
Content ID:     {5}
Run Time:       {6}
##########################################################
                    '''.format(
                        job_id,
                        job.task.name,
                        scholar_string,
                        job.corpus_id,
                        job.content_type,
                        job.content_id,
                        datetime.now().ctime()
                    ), overwrite=True)

                task_module = importlib.import_module(job.jobsite.task_registry[job.task.name]['module'])
                task_function = getattr(task_module, job.jobsite.task_registry[job.task.name]['functions'][job.stage])
                task_function(job_id)
            except:
                print(traceback.format_exc())
                job.complete(status='error', error_msg="Error launching task: {0}".format(traceback.format_exc()))


@db_task(priority=3)
def bulk_launch_jobs(job_id):
    job = Job(job_id)
    job.set_status('running')
    if job:
        corpus = job.corpus
        content_type = job.get_param_value('content_type')
        task_id = job.get_param_value('task_id')
        search_query = json.loads(job.get_param_value('query'))
        search_params = build_search_params_from_dict(search_query)
        job_params = json.loads(job.get_param_value('job_params'))

        search_params['page_size'] = 100
        search_params['only'] = ['id']
        page = 1
        num_pages = 1

        while page <= num_pages:
            search_params['page'] = page
            results = corpus.search_content(content_type, **search_params)
            if results:
                if results['meta']['num_pages'] > num_pages:
                    num_pages = results['meta']['num_pages']

                for record in results['records']:
                    corpus.queue_local_job(
                        content_type=content_type,
                        content_id=record['id'],
                        task_id=task_id,
                        scholar_id=job.scholar_id,
                        parameters=job_params
                    )

            page += 1

    job.complete('complete')


@db_task(priority=3)
def bulk_edit_content(job_id):
    job = Job(job_id)
    job.set_status('running')
    if job:
        corpus = job.corpus
        content_type = job.get_param_value('content_type')
        content_ids = job.get_param_value('content_ids')
        content_query = job.get_param_value('content_query')
        content_bundle = job.get_param_value('content_bundle')
        scholar_id = job.get_param_value('scholar_id')

        if content_type in corpus.content_types and content_bundle:
            if content_ids:
                content_ids = content_ids.split(',')
                set_and_save_content(corpus, content_type, content_ids, content_bundle, scholar_id)
            elif content_query:
                search_query = json.loads(content_query)
                search_params = build_search_params_from_dict(search_query)

                search_params['page_size'] = 100
                search_params['only'] = ['id']
                page = 1
                num_pages = 1

                while page <= num_pages:
                    search_params['page'] = page
                    results = corpus.search_content(content_type, **search_params)
                    if results:
                        if results['meta']['num_pages'] > num_pages:
                            num_pages = results['meta']['num_pages']
                        if 'next_page_token' in results['meta']:
                            search_params['page-token'] = results['meta']['next_page_token']

                        content_ids = []
                        for record in results['records']:
                            content_ids.append(record['id'])

                        set_and_save_content(corpus, content_type, content_ids, content_bundle, scholar_id)

                    page += 1

    job.complete('complete')


def set_and_save_content(corpus, content_type, content_ids, content_bundle, scholar_id):
    for content_id in content_ids:
        content = corpus.get_content(content_type, content_id, single_result=True)
        if content:
            process_content_bundle(
                corpus,
                content_type,
                content,
                content_bundle,
                scholar_id,
                True
            )


@db_periodic_task(crontab(minute='*'), priority=4)
def check_jobs():
    # the bool below is for preventing race conditions when django app is replicated in a cluster
    proceed = False

    cache = redis.Redis(host='redis', decode_responses=True)
    now = int(datetime.now().timestamp())
    last_checked = cache.get('corpora_manager_last_job_check')

    if last_checked:
        if now - int(last_checked) >= 50:
            cache.set('corpora_manager_last_job_check', now)
            proceed = True
        else:
            print('jobs already checked.')
    else:
        cache.set('corpora_manager_last_job_check', now)
        proceed = True

    if proceed:
        jobs = Job.get_jobs(limit=settings.NUM_JOBS_PER_MINUTE)
        for job in jobs:
            if job.jobsite.name == 'Local':
                if job.status == 'running':
                    if job.percent_complete == 100 or (job.total_subprocesses_launched and (job.total_subprocesses_launched == job.total_subprocesses_completed)):
                        if len(job.jobsite.task_registry[job.task.name]['functions']) > (job.stage + 1):
                            job.clear_processes()
                            job.stage += 1
                            job.save()

                            task_module = importlib.import_module(job.jobsite.task_registry[job.task.name]['module'])
                            task_function = getattr(task_module, job.jobsite.task_registry[job.task.name]['functions'][job.stage])
                            task_function(job.id)
                        else:
                            job.complete(status='complete')

                    # clean up timed out (likely errored out) jobs
                    elif datetime.now().timestamp() - job.status_time.timestamp() > settings.JOB_TIMEOUT_SECS:
                        if job.report_path:
                            job.report("ERROR: Job timed out or experienced an unexpected failure.")
                        job.complete(status='error')

                elif job.status == 'queueing':
                    job.set_status('enqueued')
                    run_job(job.id)


@db_task(priority=10)
def save_content_type_schema(job_id):
    job = Job(job_id)
    job.set_status('running')
    schema = json.loads(job.get_param_value('schema'))

    for ct_schema in schema:
        queued_job_ids = job.corpus.save_content_type(ct_schema)
        for queued_job_id in queued_job_ids:
            run_job(queued_job_id)

    job.complete(status='complete')


@db_task(priority=5)
def adjust_content(job_id):
    job = Job(job_id)
    job.set_status('running')
    primary_content_type = job.get_param_value('content_type')
    reindex = job.get_param_value('reindex')
    relabel = job.get_param_value('relabel')
    resave = job.get_param_value('resave')
    relink = job.get_param_value('relink')
    related_content_types = job.get_param_value('related_content_types')
    resume_at = int(job.get_param_value('resume_at'))

    es_logger = logging.getLogger('elasticsearch')
    es_log_level = es_logger.getEffectiveLevel()
    es_logger.setLevel(logging.WARNING)

    content_types = related_content_types.split(',')
    content_types.insert(0, primary_content_type)
    content_types = [ct for ct in content_types if ct and ct in job.corpus.content_types]

    total_content_count = sum([job.corpus.get_content(ct, all=True).count() for ct in content_types])
    total_content_adjusted = 0
    completion_percentage = 0
    chunk_size = 500
    first_ct_adjusted = False
    error_instances = 0
    max_errors = 10

    if total_content_count > 0:
        for content_type in content_types:
            if error_instances >= max_errors:
                break

            content_count = job.corpus.get_content(content_type, all=True).count()
            if content_count > 0:
                if first_ct_adjusted:
                    reindex = True
                    relabel = False
                    resave = False
                    relink = False

                num_slices = math.ceil(content_count / chunk_size)
                for slice in range(0, num_slices):
                    start = slice * chunk_size
                    end = start + chunk_size

                    if completion_percentage >= resume_at:
                        errors = adjust_content_slice(
                            job.corpus,
                            content_type,
                            start,
                            end,
                            reindex,
                            relabel,
                            resave,
                            relink
                        )
                    else:
                        errors = []

                    if errors:
                        error_instances += 1
                        job.report("\n\n".join(errors))

                        if error_instances >= max_errors:
                            job.report("Too many errors encountered while adjusting content for {0}. Halting task!".format(content_type))
                            break

                    total_content_adjusted += chunk_size
                    completion_percentage = int((total_content_adjusted / total_content_count) * 100)
                    if completion_percentage >= resume_at:
                        job.set_status('running', percent_complete=completion_percentage)

            first_ct_adjusted = True

    es_logger.setLevel(es_log_level)
    job.complete(status='complete')


def adjust_content_slice(corpus, content_type, start, end, reindex, relabel, resave, relink, scrub_provenance=False):
    errors = []
    max_errors = 10
    contents = corpus.get_content(content_type, all=True).no_cache()
    contents = contents.batch_size(10)
    if isinstance(start, int) and isinstance(end, int):
        contents = contents[start:end]

    for content in contents:
        try:
            if scrub_provenance:
                content.provenance = []

            if relabel:
                content.label = ''

            if relabel or resave:
                content.save(do_indexing=reindex, do_linking=relink)
            else:
                if reindex:
                    content._do_indexing()

                if relink:
                    content._do_linking()

        except:
            err_msg = ""
            if hasattr(content, 'id'):
                err_msg += "Error adjusting content for {0} with ID {1}:\n".format(content_type, content.id)
            else:
                err_msg += "Error adjusting content of type {0} in slice starting at {0} and ending at {1}:\n".format(content_type, start, end)
            err_msg += traceback.format_exc()
            errors.append(err_msg)

        if len(errors) >= max_errors:
            errors.append("Max errors exceeded while adjusting content slice for {0} starting at {1} and ending at {2}. Halting!".format(content_type, start, end))
            break

    return errors


@db_task(priority=5)
def scrub_all_provenance():
    corpora = Corpus.objects()
    for corpus in corpora:
        corpus.provenance = []
        corpus.save()

        for content_type in corpus.content_types.keys():
            contents = corpus.get_content(content_type, {"provenance__exists": True, "provenance__not__size": 0}).no_cache()
            contents = contents.batch_size(10)
            for content in contents:
                content.provenance = []
                content.save()


@db_task(priority=5)
def delete_content_type(job_id):
    job = Job(job_id)
    job.set_status('running')
    content_type = job.configuration['parameters']['content_type']['value']
    if content_type in job.corpus.content_types:
        job.corpus.delete_content_type(content_type)

    job.complete(status='complete')


@db_task(priority=5)
def delete_content_type_field(job_id):
    job = Job(job_id)
    job.set_status('running')
    content_type = job.configuration['parameters']['content_type']['value']
    field_name = job.configuration['parameters']['field_name']['value']
    if content_type in job.corpus.content_types:
        job.corpus.delete_content_type_field(content_type, field_name)

    job.complete(status='complete')


@db_task(priority=5)
def delete_corpus(job_id):
    job = Job(job_id)
    job.set_status('running')
    job.corpus.delete()
    job.complete(status='complete')


@db_task(priority=5)
def merge_content(job_id):
    job = Job(job_id)
    corpus = job.corpus
    job.set_status('running')

    content_type = job.configuration['parameters']['content_type']['value']
    target_id = job.configuration['parameters']['target_id']['value']
    merge_ids = job.configuration['parameters']['merge_ids']['value']
    delete_merged = job.configuration['parameters']['delete_merged']['value']
    cascade_deletion = job.configuration['parameters']['cascade_deletion']['value']

    merged_values = 0
    merged_deletions = 0
    cascade_deletions = 0

    if corpus.path:
        merge_report_dir = "{0}/files/merge_reports".format(corpus.path)
        os.makedirs(merge_report_dir, exist_ok=True)
        merge_report_path = "{0}/{1}.txt".format(merge_report_dir, job_id)
        with open(merge_report_path, 'w') as report:
            report.write("Content Type: {0}\n".format(content_type))
            report.write("Target ID: {0}\n".format(target_id))
            report.write("Merge IDs: {0}\n".format(merge_ids))
            report.write("Delete Merged?: {0}\n".format(delete_merged))
            report.write("Cascade Deletion?: {0}\n".format(cascade_deletion))
            report.write("--------------------------------------\n\n")

            merge_ids = [merge_id for merge_id in merge_ids.split(',') if merge_id]

            if content_type in corpus.content_types and target_id and merge_ids:
                target_content = corpus.get_content(content_type, target_id)
                if target_content:
                    report.write("Target found.\n")

                    for merge_id in merge_ids:
                        report.write("\nAttempting to merge {0} into target...\n".format(merge_id))
                        no_problems_merging = True
                        merge_content = None

                        try:
                            # explore inbound connections
                            explored_content = corpus.explore_content(
                                content_type,
                                left_id=merge_id,
                                cardinality=2
                            )
                            if len(explored_content) == 1:
                                merge_content = explored_content[0]
                                report.write("Inbound connections queried...\n")

                                if hasattr(merge_content, '_exploration'):
                                    report.write("Inbound connections found...\n")
                                    for relationship in merge_content._exploration.keys():
                                        if relationship.startswith('has'):
                                            field_name = relationship[3:]
                                            for related_dict in merge_content._exploration[relationship]:
                                                related_ct = related_dict['content_type']
                                                related_id = related_dict['id']
                                                related_field = corpus.content_types[related_ct].get_field(field_name)
                                                report.write("Inspecting value of field '{0}' for {1} with ID {2}...\n".format(
                                                    field_name,
                                                    related_ct,
                                                    related_id
                                                ))

                                                if related_field and related_field.type == 'cross_reference' and related_field.cross_reference_type == content_type:
                                                    related_content = corpus.get_content(related_ct, related_id)

                                                    if related_content and not related_field.multiple and hasattr(related_content, field_name) and getattr(related_content, field_name).id == merge_content.id:
                                                        setattr(related_content, field_name, target_content.id)
                                                        related_content.save()
                                                        merged_values += 1
                                                        report.write("Successfully changed field value from merge ID {0} to target ID {1}!\n".format(merge_content.id, target_id))

                                                    elif related_content and related_field.multiple and hasattr(related_content, field_name):
                                                        new_reffs = []
                                                        for reffed_content in getattr(related_content, field_name):
                                                            if reffed_content.id == merge_content.id:
                                                                new_reffs.append(target_content.id)
                                                            else:
                                                                new_reffs.append(reffed_content.id)

                                                        setattr(related_content, field_name, new_reffs)
                                                        related_content.save()
                                                        merged_values += 1
                                                        report.write("Successfully changed field value from merge ID {0} to target ID {1}!\n".format(merge_content.id, target_id))
                        except:
                            no_problems_merging = False
                            report.write("ERROR MERGING:")
                            report.write(traceback.format_exc())

                        if merge_content and no_problems_merging and delete_merged:
                            report.write("Attempting to delete merged {0} with ID {1}...\n".format(content_type, merge_content.id))
                            merge_content_dict = corpus.search_content(content_type, page_size=1, fields_filter={'id': str(merge_content.id)})
                            if len(merge_content_dict['records']) == 1:
                                merge_content_dict = merge_content_dict['records'][0]
                                merge_content_archive_path = "{0}/{1}_{2}_merged_into_{3}.json".format(
                                    merge_report_dir,
                                    content_type,
                                    merge_content.id,
                                    target_content.id
                                )
                                with open(merge_content_archive_path, 'w') as archive_out:
                                    json.dump(merge_content_dict, archive_out, indent=4)

                            if cascade_deletion:
                                report.write("Attempting to cascade delete any singularly connected content...\n".format(content_type, merge_content.id))
                                cascaded_contents = []

                                for field in corpus.content_types[content_type].fields:
                                    if field.type == 'cross_reference' and getattr(merge_content, field.name):
                                        if not field.multiple:
                                            cascaded_contents.append(getattr(merge_content, field.name))
                                        else:
                                            for cascaded_content in getattr(merge_content, field.name):
                                                cascaded_contents.append(cascaded_content)

                                for cascaded_content in cascaded_contents:
                                    report.write("Investigating cascade deletion of {0} with ID {1}...\n".format(cascaded_content.content_type, cascaded_content.id))

                                    explored_content = corpus.explore_content(
                                        cascaded_content.content_type,
                                        left_id=cascaded_content.id,
                                        cardinality=0 # <- both in and outbound connections
                                    )

                                    if len(explored_content) == 1:
                                        cascaded_content = explored_content[0]
                                        eligible_for_deletion = True

                                        if hasattr(cascaded_content, '_exploration'):
                                            relationships = list(cascaded_content._exploration.keys())
                                            if len(relationships) <= 1:
                                                if relationships and len(cascaded_content._exploration[relationships[0]]) > 1:
                                                    eligible_for_deletion = False
                                            else:
                                                eligible_for_deletion = False

                                        if eligible_for_deletion:
                                            cascaded_content.delete()
                                            cascade_deletions += 1
                                            report.write("Successfully cascade deleted {0} with ID {1}!\n".format(cascaded_content.content_type, cascaded_content.id))
                                        else:
                                            report.write("{0} with ID {1} ineligible for cascade deletion.\n".format(cascaded_content.content_type, cascaded_content.id))

                            merge_content.delete()
                            merged_deletions += 1
                            report.write("Successfully deleted merged {0} with ID {1}!\n".format(content_type, merge_content.id))

            report.write("\n--------------------------------------\n")
            report.write("MERGE COMPLETED with following stats:\n")
            report.write("Merged values: {0}\n".format(merged_values))
            report.write("Merged deletions: {0}\n".format(merged_deletions))
            report.write("Cascade deletions: {0}\n".format(cascade_deletions))

    job.complete(status='complete')


@db_task(priority=5)
def convert_foreign_key_to_xref(job_id):
    job = Job(job_id)
    corpus = job.corpus
    job.set_status('running')

    source_ct_field = job.get_param_value('source_ct_field')
    target_ct_field = job.get_param_value('target_ct_field')
    new_field_name = job.get_param_value('new_field_name')
    new_field_label = job.get_param_value('new_field_label')
    delete_old_field = job.get_param_value('delete_old_field')

    if source_ct_field and target_ct_field and new_field_name:
        source_parts = source_ct_field.split('->')
        source_ct = source_parts[0]
        source_field = source_parts[1]

        target_parts = target_ct_field.split('->')
        target_ct = target_parts[0]
        target_field = target_parts[1]

        if source_ct in corpus.content_types and corpus.content_types[source_ct].get_field(source_field) and \
                target_ct in corpus.content_types and corpus.content_types[target_ct].get_field(target_field):

            if not corpus.content_types[source_ct].get_field(new_field_name):
                source_schema = corpus.content_types[source_ct].to_dict()
                source_schema['fields'].append({
                    'name': new_field_name,
                    'label': new_field_label,
                    'type': 'cross_reference',
                    'cross_reference_type': target_ct,
                    'multiple': False,
                    'in_lists': True,
                    'indexed': False,
                    'indexed_with': [],
                    'unique': False,
                    'unique_with': [],
                    'proxy_field': "",
                    'inherited': False,
                })
                adjustment_jobs = corpus.save_content_type(source_schema)
                for adjustment_job in adjustment_jobs:
                    run_job(adjustment_job)
                time.sleep(10 * len(adjustment_jobs))

                if corpus.content_types[source_ct].get_field(new_field_name):
                    all_targets_found = True

                    source_contents = corpus.get_content(source_ct, all=True)
                    for source_content in source_contents:
                        old_field_value = getattr(source_content, source_field)
                        if old_field_value or old_field_value == 0:
                            target_content = corpus.get_content(target_ct, {target_field: old_field_value})[0]
                            if target_content:
                                setattr(source_content, new_field_name, target_content.id)
                                source_content.save()
                            else:
                                all_targets_found = False

                    if all_targets_found and delete_old_field:
                        corpus.delete_content_type_field(source_ct, source_field)

    job.complete(status='complete')


@db_task(priority=5)
def pull_repo(job_id):
    job = Job(job_id)
    job.set_status('running')
    repo_name = job.get_param_value('repo_name')
    repo_content_type = job.get_param_value('repo_content_type')
    repo_content_id = job.get_param_value('repo_content_id')
    repo_field = job.get_param_value('repo_field')
    repo_field_multi_index = job.get_param_value('repo_field_multi_index')
    repo_user = job.get_param_value('repo_user')
    repo_pwd = job.get_param_value('repo_pwd')

    if repo_content_id is None:
        if repo_name in job.corpus.repos:
            try:
                job.corpus.repos[repo_name].pull(job.corpus, repo_user, repo_pwd)
            except:
                job.corpus.repos[repo_name].error = True
                job.corpus.save()
                print(traceback.format_exc())

    else:
        content = job.corpus.get_content(repo_content_type, repo_content_id)
        if content:
            if hasattr(content, repo_field):
                try:
                    if repo_field_multi_index is None:
                        getattr(content, repo_field).pull(content, repo_user, repo_pwd)
                    else:
                        getattr(content, repo_field)[repo_field_multi_index].pull(content, repo_user, repo_pwd)

                    content.save()
                except:
                    print(traceback.format_exc())

    job.complete(status='complete')


@db_task(priority=5)
def content_view_lifecycle(job_id):
    job = Job(job_id)
    cv_id = job.get_param_value('cv_id')
    cv_stage = job.get_param_value('stage')
    job.set_status('running')

    try:
        cv = ContentView.objects.get(id=cv_id)
        if cv_stage == 'populate':
            cv.populate()
        elif cv_stage == 'refresh':
            cv.clear()
            cv.populate()
        elif cv_stage == 'delete':
            cv.clear()
            cv.delete()

        job.complete(status='complete')
    except:
        print(traceback.format_exc())
        job.complete(status='error')


@db_periodic_task(crontab(minute=1, hour='*/12'), priority=4)
def audit_content_views():
    print('Auditing content views...')
    cvs = ContentView.objects(status='populated')

    for cv in cvs:
        print(cv.name)
        needs_refresh = False
        for relevant_ct in cv.relevant_cts:
            if relevant_ct in cv.corpus.content_types:
                latest_content = cv.corpus.get_content(relevant_ct, all=True).order_by('-last_updated').first()
                if latest_content:
                    if cv.status_date < latest_content.last_updated:
                        needs_refresh = True
                        break

        if needs_refresh:
            print("NEEDS REFRESH")
            cv.clear()
            cv.populate()

    cvs = ContentView.objects(status='needs_refresh')
    for cv in cvs:
        cv.clear()
        cv.populate()


@db_periodic_task(crontab(minute=1, hour='*'), priority=4)
def content_deletion_cleanup():
    corpora = {}
    reindex_cts = []
    deletions = ContentDeletion.objects()
    for deletion in deletions:
        deletion_handled = True

        if deletion.uri:

            del_corpus_id = deletion.corpus_id
            del_content_type = deletion.content_type
            del_content_id = deletion.content_id
            refs_deleted = 0

            if del_corpus_id not in corpora:
                corpora[del_corpus_id] = {
                    'instance': get_corpus(del_corpus_id),
                    'ct_ref_fields': {}
                }

            if corpora[del_corpus_id]['instance']:
                if del_content_type not in corpora[del_corpus_id]['ct_ref_fields']:
                    corpora[del_corpus_id]['ct_ref_fields'][del_content_type] = corpora[del_corpus_id]['instance'].get_referencing_content_type_fields(del_content_type)

                for reffing_ct in corpora[del_corpus_id]['ct_ref_fields'][del_content_type].keys():
                    for reffing_field in corpora[del_corpus_id]['ct_ref_fields'][del_content_type][reffing_ct]:
                        criteria = {reffing_field.name: del_content_id}
                        if reffing_field.multiple:
                            criteria = {"{0}__contains".format(reffing_field.name): del_content_id}

                        reffing_contents = corpora[del_corpus_id]['instance'].get_content(reffing_ct, criteria).no_cache()
                        reffing_contents = reffing_contents.batch_size(100)
                        for reffing_content in reffing_contents:
                            new_value = None
                            if reffing_field.multiple:
                                new_value = getattr(reffing_content, reffing_field.name)
                                new_value = [ref for ref in new_value if not str(ref.id) == del_content_id]
                            setattr(reffing_content, reffing_field.name, new_value)

                            try:
                                reffing_content.save(do_indexing=False, do_linking=False)
                                refs_deleted += 1

                                reindex_ct = f"{del_corpus_id}_{reffing_ct}"
                                if reindex_ct not in reindex_cts:
                                    reindex_cts.append(reindex_ct)
                            except:
                                caught_error = traceback.format_exc()
                                if "Tried to save duplicate unique keys" in caught_error:
                                    reffing_content.delete()
                                    refs_deleted += 1
                                else:
                                    print(caught_error)
                                    deletion_handled = False

                print('Removed {0} references to deleted content {1}'.format(refs_deleted, deletion.uri))

        if deletion_handled:
            if deletion.path and os.path.exists(deletion.path):
                shutil.rmtree(deletion.path)

            deletion.delete()

    for reindex_ct in reindex_cts:
        reindex_ct_parts = reindex_ct.split('_')
        if reindex_ct_parts[0] in corpora:
            corpora[reindex_ct_parts[0]]['instance'].queue_local_job(task_name="Adjust Content", parameters={
                'content_type': reindex_ct_parts[1],
                'reindex': True,
                'relabel': True,
                'resave': False,
                'related_content_types': ''
            })

    # sweep for "expired" temporary uploads
    expired_uploads = TemporaryUpload.objects.filter(uploaded__lte=datetime.now()-timedelta(days=1))
    for upload in expired_uploads:
        upload.delete()


@db_task(priority=3)
def backup_corpus(job_id):
    job = Job(job_id)
    corpus = job.corpus
    backup_name = job.get_param_value('backup_name')
    if not backup_name:
        backup_name = datetime.now().isoformat().split('T')[0].replace('-', '_')

    backup_data_files = []
    backup_valid = True
    job.set_status('running')

    try:
        job.report("Backing up corpus with ID {0}".format(job.corpus_id))
        backup_directory = "/corpora/backups/{0}_{1}".format(job.corpus_id, backup_name)
        backup_tarfile = "/corpora/backups/{0}_{1}.tar.gz".format(job.corpus_id, backup_name)
        backup = CorpusBackup.objects(corpus_id=job.corpus_id, name=backup_name)

        # Setup backup object
        if backup.count():
            backup = backup[0]
            job.report("Backup already exists--overwriting...")
        else:
            backup = CorpusBackup()

        backup.corpus_id = job.corpus_id
        backup.corpus_name = corpus.name
        backup.corpus_description = corpus.description
        backup.name = backup_name

        if os.path.exists(backup_tarfile):
            job.report("Removing existing backup tarfile...")
            os.remove(backup_tarfile)

        if os.path.exists(backup_directory):
            job.report("Removing existing backup directory...")
            shutil.rmtree(backup_directory)
            time.sleep(5)

        os.makedirs(backup_directory, exist_ok=True)

        # Dump jobsite JSON
        local_jobsite = JobSite.objects(name='Local')[0]
        jobsite_json_path = backup_directory + '/jobsite.json'
        with open(jobsite_json_path, 'w', encoding='utf-8') as jobsite_json_out:
            jobsite_json_out.write(local_jobsite.to_json())
        backup_data_files.append(jobsite_json_path)
        job.report("Jobsite JSON created :)")

        # Dump corpus JSON
        corpus_json_path = backup_directory + '/corpus.json'
        with open(corpus_json_path, 'w', encoding='utf-8') as corpus_json_out:
            json.dump(corpus.to_dict(include_views=True), corpus_json_out, indent=4)
        backup_data_files.append(corpus_json_path)
        job.report("Corpus JSON created :)")

        mongodb_uri = make_mongo_uri()

        # Create MongoDB dump files for each content type collection
        for ct_name, ct in corpus.content_types.items():
            collection_name = "corpus_{0}_{1}".format(corpus.id, ct.name)
            collection_backup_file = backup_directory + '/' + collection_name

            # Ensure we have data in these collections
            if corpus.get_content(ct_name, all=True).count() > 0:

                # Build mongodump command
                command = [
                    'mongodump',
                    '--uri="{0}"'.format(mongodb_uri),
                    '--collection={0}'.format(collection_name),
                    '--archive={0}'.format(collection_backup_file),
                ]

                # Execute command and check return code
                if call(command) == 0:
                    backup_data_files.append(collection_backup_file)
                    job.report("Collection {0} backed up :)".format(collection_name))
                else:
                    job.report("Error backing up collection {0}! Halting backup.".format(collection_name))
                    job.complete(status='error')
                    return None

            else:
                job.report("No records found for {0} collection; skipping.".format(collection_name))

        # Create the tarfile
        with tarfile.open(backup_tarfile, "w:gz") as tar:
            # Add exported corpus.json and MongoDB Collection dumps
            for data_file in backup_data_files:
                tar.add(data_file, arcname=os.path.basename(data_file))

            # Add corpus directory structure
            tar.add(corpus.path, arcname=os.path.basename(corpus.path))

        if os.path.exists(backup_directory):
            job.report("Cleaning up backup files...")
            shutil.rmtree(backup_directory)

        job.report("\nBackup file {0} successfully created!".format(backup_tarfile))

        backup.created = datetime.now()
        backup.path = backup_tarfile
        backup.status = "created"
        backup.save()
        job.complete(status='complete')
    except:
        print(traceback.format_exc())
        job.complete(status='error')


@db_task(priority=3)
def restore_corpus(backup_id):
    backup = CorpusBackup.objects(id=backup_id)
    backup_directory = None

    if backup.count() > 0:
        backup = backup[0]
        print("Attempting to restore corpus from backup file {0}".format(backup.path))

        try:
            if backup.path.endswith('.tar.gz') and os.path.exists(backup.path):
                with tarfile.open(backup.path, 'r:gz') as tar:
                    corpus_json = tar.extractfile('corpus.json').read()
                    jobsite_json = tar.extractfile('jobsite.json').read()

                    if corpus_json and jobsite_json:
                        # Determine if this backup file came from another instance of Corpora
                        foreign_import = False
                        jobsite_dict = json.loads(jobsite_json)
                        jobsite_id = jobsite_dict['_id']['$oid']
                        try:
                            JobSite.objects(id=jobsite_id)[0]
                        except:
                            foreign_import = True

                        corpus_dict = json.loads(corpus_json)
                        if _contains(corpus_dict, ['id', 'name', 'description', 'open_access', 'content_types']):
                            existing_corpus = get_corpus(corpus_dict['id'])

                            if existing_corpus:
                                print("Corpus with ID {0} already exists! Halting restore.".format(corpus_dict['id']))
                                backup.status = 'created'
                                backup.save()
                                return None
                            else:
                                corpus = Corpus()
                                corpus.id = ObjectId(corpus_dict['id'])
                                corpus.name = corpus_dict['name']
                                corpus.description = corpus_dict['description']
                                corpus.open_access = corpus_dict['open_access']
                                corpus.kvp = corpus_dict['kvp']

                                for file_key, file_info in corpus_dict['files'].items():
                                    f = File.from_dict(file_info)
                                    if f:
                                        corpus.files[file_key] = f

                                for repo_name, repo_info in corpus_dict['repos'].items():
                                    r = GitRepo.from_dict(repo_info)
                                    if r:
                                        corpus.repos[repo_name] = r

                                # todo: test content type group restore
                                for ctg_info in corpus_dict['content_type_groups']:
                                    ctg = ContentTypeGroup()
                                    ctg.from_dict(ctg_info)
                                    corpus.content_type_groups.append(ctg)

                                # todo: backup and restore content views

                                if not foreign_import:
                                    for prov_info in corpus_dict['provenance']:
                                        prov = CompletedTask.from_dict(prov_info)
                                        if prov:
                                            corpus.provenance.append(prov)

                                corpus.save()

                                backup_directory = '/corpora/backups/' + os.path.basename(backup.path).split('.')[0]

                                if os.path.exists(backup_directory):
                                    shutil.rmtree(backup_directory)
                                    time.sleep(2)

                                os.makedirs(backup_directory)

                                mongodb_uri = make_mongo_uri()

                                content_schema = []
                                for ct_name, ct in corpus_dict['content_types'].items():
                                    content_schema.append(ct)

                                ordered_schema = order_content_schema(content_schema)
                                for ct in ordered_schema:
                                    ct_name = ct['name']
                                    corpus.save_content_type(ct)
                                    collection = "corpus_{0}_{1}".format(corpus.id, ct_name)
                                    collection_dump_file = backup_directory + '/' + collection

                                    try:
                                        collection_dump_file_info = tar.getmember(collection)
                                        tar.extract(collection_dump_file_info, path=backup_directory)

                                        # Build mongorestore command
                                        command = [
                                            'mongorestore',
                                            '--uri="{0}"'.format(mongodb_uri),
                                            '--archive={0}'.format(collection_dump_file),
                                        ]

                                        # Execute command and check return code
                                        if call(command) == 0:
                                            print("Collection {0} successfully restored :)".format(collection))
                                            if foreign_import:
                                                db = corpus._get_db()
                                                db[collection].update_many({}, {'$set': {'provenance': []}})

                                            adjust_content_slice(corpus, ct_name, None, None, True, True, True, True, foreign_import)
                                        else:
                                            print("Error restoring collection {0}! Halting restore.".format(collection))
                                            run_job(corpus.queue_local_job(task_name="Delete Corpus", parameters={}))
                                            shutil.rmtree(backup_directory)
                                            backup.status = 'created'
                                            backup.save()
                                            return None

                                    except KeyError:
                                        print('No collection found for {0}'.format(ct_name))

                                if os.path.exists(backup_directory):
                                    shutil.rmtree(backup_directory)
                                tar.extractall(path=corpus.path, members=filter_tarfile(tar, str(corpus.id)))


        except:
            if backup_directory and os.path.exists(backup_directory):
                shutil.rmtree(backup_directory)
            print(traceback.format_exc())

        backup.status = "created"
        backup.save()

    else:
        print("Error retrieving backup object for restore!")


@db_task(priority=3)
def export_corpus(job_id):
    from django.template.autoreload import reset_loaders
    reset_loaders()

    job = Job(job_id)
    corpus = job.corpus
    export_html = job.get_param_value('export_html')
    export_path = f"{corpus.path}/export"
    export_tar_file = f"{corpus.path}/export.tar.gz"
    total_content_count = 0

    job.set_status('running')

    # clean up any existing exports
    if os.path.exists(export_path):
        job.report("Deleting existing export directory...")
        shutil.rmtree(export_path)
    if os.path.exists(export_tar_file):
        job.report("Deleting existing export tar file...")
        os.remove(export_tar_file)

    job.set_status('running', percent_complete=5)

    #######################################
    ### MAKE JSON DATA DUMPS OF CONTENT ###
    #######################################
    job.report("Commencing JSON export...")

    json_path = f"{export_path}/json"
    schema = []

    os.makedirs(json_path, exist_ok=True)

    for ct_name in corpus.content_types.keys():
        schema.append(corpus.content_types[ct_name].to_dict())

        ct_json_file = f"{json_path}/{ct_name}.json"
        with open(ct_json_file, 'w', encoding='utf-8') as ct_json_out:
            contents = corpus.get_content(ct_name, all=True)
            contents = contents.order_by('id')
            contents = contents.no_cache()
            contents = contents.batch_size(10)

            content_count = contents.count()
            schema[-1]['total_content'] = content_count
            total_content_count += content_count

            chunk_size = 1000
            chunk_byte_sizes = []
            chunks = math.ceil(content_count / chunk_size)

            for chunk in range(0, chunks):
                start = chunk * chunk_size
                end = start + chunk_size

                content_slice = contents[start:end]
                content_json = delimit_content_json(content_slice)

                if chunks > 1:
                    if chunk == 0:
                        content_json = '[' + content_json + ', '
                    elif chunk == chunks - 1:
                        content_json = content_json + ']'
                    else:
                        content_json = content_json + ', '
                else:
                    content_json = '[' + content_json + ']'

                chunk_byte_sizes.append(len(content_json.encode('utf-8')) / content_slice.count())
                ct_json_out.write(content_json)

            if chunks and chunk_byte_sizes:
                schema[-1]['average_byte_size'] = math.ceil(sum(chunk_byte_sizes) / chunks)
            else:
                schema[-1]['average_byte_size'] = 0

    if schema:
        with open(f"{json_path}/schema.json", 'w', encoding='utf-8') as schema_out:
            json.dump(schema, schema_out, indent=4)

    percent_complete = 100
    if export_html:
        percent_complete = 25

    job.set_status('running', percent_complete=percent_complete)

    #######################################
    ###   MAKE HTML PAGES FOR CONTENT   ###
    #######################################
    if export_html:
        job.report("Commencing HTML export (this may take quite a long time, depending on how much content is in your corpus)...")

        static_files = set()
        static_dirs = set()
        corpora_path_pattern = re.compile(r'\/corpora\/[^\/]*')
        total_content_exported = 0

        def get_static_file_path(file_path):
            return os.path.join(settings.STATIC_ROOT, file_path)

        for ct_name in corpus.content_types.keys():
            ct_path = f"{export_path}/{ct_name}"
            contents = corpus.get_content(ct_name, all=True)
            contents = contents.no_cache()
            contents = contents.batch_size(10)

            inclusions, javascript_functions, css_styles = corpus.content_types[ct_name].get_render_requirements('view')
            export_template = get_template('content_export.html')

            for lang in inclusions.keys():
                if lang == 'directories':
                    for directory in inclusions[lang]:
                        static_dirs.add(directory)
                else:
                    for static_file in inclusions[lang]:
                        static_files.add(static_file)

            default_css = None
            if 'DefaultCSS' in corpus.content_types[ct_name].templates:
                default_css = corpus.content_types[ct_name].templates['DefaultCSS'].template

            for content in contents:
                breakout_dir = str(content.id)[-6:-2]
                exported_content_path = f"{ct_path}/{breakout_dir}/{content.id}"
                os.makedirs(exported_content_path, exist_ok=True)

                if content.path and os.path.exists(content.path):
                    shutil.copytree(content.path, f"{exported_content_path}", dirs_exist_ok=True)

                    for field in corpus.content_types[ct_name].fields:
                        if field.type == 'file':
                            if getattr(content, field.name, None):
                                if field.multiple:
                                    for file_index in range(0, len(getattr(content, field.name))):
                                        full_file_path = getattr(content, field.name)[file_index].path
                                        if full_file_path:
                                            setattr(
                                                getattr(content, field.name)[file_index],
                                                'relative_path',
                                                corpora_path_pattern.sub('', full_file_path)
                                            )
                                else:
                                    full_file_path = getattr(content, field.name).path
                                    if full_file_path:
                                        setattr(
                                            getattr(content, field.name),
                                            'relative_path',
                                            corpora_path_pattern.sub('', full_file_path)
                                        )

                corpus.content_types[ct_name].set_field_values_from_content(content)
                html_path = f"{exported_content_path}/index.html"
                html = export_template.render({
                    'content_label': content.label,
                    'content_type': corpus.content_types[ct_name],
                    'content_type_names': list(corpus.content_types.keys()),
                    'content_id': str(content.id),
                    'content_uri': content.uri,
                    'breakout_dir': breakout_dir,
                    'inclusions': inclusions,
                    'javascript_functions': javascript_functions,
                    'css_styles': css_styles,
                    'default_css': default_css
                })
                with open(html_path, 'w', encoding='utf-8') as html_out:
                    html_out.write(html)

                total_content_exported += 1
                if total_content_exported % 500 == 0:
                    html_export_percent_complete = (total_content_exported / total_content_count) * 100
                    percent_complete = math.floor(((html_export_percent_complete / 100) * 25) + 25)
                    job.set_status('running', percent_complete=percent_complete)


        # create the static dependencies (.js/.css, etc) directory
        static_files_path = f"{export_path}/static"
        os.makedirs(static_files_path, exist_ok=True)

        # copy over any global dependencies
        dependencies_path = get_static_file_path('export_dependencies')
        if os.path.exists(dependencies_path):
            shutil.copytree(dependencies_path, static_files_path, dirs_exist_ok=True)

        for static_file in static_files:
            static_file_path = get_static_file_path(static_file)
            copied_path = f"{static_files_path}/{static_file}"

            os.makedirs(os.path.dirname(copied_path), exist_ok=True)
            shutil.copy(static_file_path, copied_path)

        for static_dir in static_dirs:
            shutil.copytree(get_static_file_path(static_dir), f"{static_files_path}/{static_dir}", dirs_exist_ok=True)

        job.set_status('running', percent_complete=50)

        ###########################################
        ###   BUILD OUT TABULAR JSON AND PAGES  ###
        ###########################################
        job.report("Commencing tabular export...")

        export_template = get_template('content_table_export.html')
        average_record_sizes = {}
        total_records_exported = 0

        for ct_name in corpus.content_types.keys():
            tabular_json_file = f"{export_path}/json/{ct_name}_table.json"

            tabular_results = scan(
                client=get_connection(),
                index=f"corpus-{corpus.id}-{ct_name}".lower(),
                query={"query": {"match_all": {}}},
                scroll='5m',
                size=1000,
                request_timeout=60
            )

            record_sizes = []
            chunk_sizes = []
            num_records = 0

            with open(tabular_json_file, 'w', encoding='utf-8') as table_json_out:
                table_json_out.write('[\n')

                first_result = True
                for tabular_result in tabular_results:
                    tabular_result['_source']['id'] = tabular_result['_id']

                    if first_result:
                        first_result = False
                    else:
                        table_json_out.write(',\n')

                    json_record = json.dumps(tabular_result['_source'])
                    record_sizes.append(len(json_record.encode('utf-8')))
                    table_json_out.write(json_record)
                    num_records += 1

                    if record_sizes and num_records % 1000 == 0:
                        chunk_sizes.append(sum(record_sizes) / len(record_sizes))
                        record_sizes = []
                        total_records_exported += num_records
                        tabular_export_percent_complete = (total_records_exported / total_content_count) * 100
                        percent_complete = math.floor(((tabular_export_percent_complete / 100) * 25) + 50)
                        job.set_status('running', percent_complete=percent_complete)


                table_json_out.write('\n]')

            if record_sizes:
                chunk_sizes.append(sum(record_sizes) / len(record_sizes))

            if chunk_sizes:
                average_record_sizes[ct_name] = math.ceil(sum(chunk_sizes) / len(chunk_sizes))
            else:
                average_record_sizes[ct_name] = 0

            with open(f"{export_path}/{ct_name}.html", 'w', encoding='utf-8') as table_out:
                table_out.write(export_template.render({'content_type': corpus.content_types[ct_name]}))

        if average_record_sizes:
            schema = []
            schema_path = f"{export_path}/json/schema.json"

            if os.path.exists(schema_path):
                with open(schema_path, 'r', encoding='utf-8') as schema_in:
                    schema = json.load(schema_in)

                if schema:
                    for ct_index in range(0, len(schema)):
                        if schema[ct_index]['name'] in average_record_sizes:
                            schema[ct_index]['average_tabular_byte_size'] = average_record_sizes[schema[ct_index]['name']]

                with open(schema_path, 'w', encoding='utf-8') as schema_out:
                    json.dump(schema, schema_out, indent=4)

        job.set_status('running', percent_complete=75)

        with open(f"{export_path}/index.html", 'w', encoding='utf-8') as index_out:
            index_template = get_template('index_export.html')
            index_html = index_template.render({'corpus': corpus})
            index_out.write(index_html)

    if os.path.exists(export_path):
        job.report("Creating compressed tar file for download (this may take a long time)...")

        with tarfile.open(export_tar_file, "w:gz") as tar:
            tar.add(export_path, arcname='export')

        job.set_status('running', percent_complete=85)

        if os.path.exists(export_tar_file):
            shutil.rmtree(export_path)

    corpora_url = 'https://' if settings.USE_SSL else 'http://'
    corpora_url += settings.ALLOWED_HOSTS[0]
    job.report(f"Export complete! Download here: {corpora_url}/export/download/{corpus.id}/")
    job.complete(status='complete')


def make_mongo_uri():
    uri_invalid_chars = ":/?#[]@"
    escaped_pwd = settings.MONGO_PWD
    for invalid_char in uri_invalid_chars:
        escaped_pwd = escaped_pwd.replace(invalid_char, quote(invalid_char))

    return "mongodb://{user}:{pwd}@{host}:27017/{db}?authSource={auth_source}".format(
        user=settings.MONGO_USER,
        pwd=escaped_pwd,
        host=settings.MONGO_HOST,
        db=settings.MONGO_DB,
        auth_source=settings.MONGO_AUTH_SOURCE
    )


def filter_tarfile(tar, subdir):
    subdir = subdir + '/'
    subdir_length = len(subdir)
    for member in tar.getmembers():
        if member.path.startswith(subdir):
            member.path = member.path[subdir_length:]
            yield member
