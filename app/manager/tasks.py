import os
import shutil
import json
import importlib
import time
import traceback
import pymysql
import logging
import math
import redis
from copy import deepcopy
from corpus import Corpus, Job, get_corpus, File, run_neo, ContentView
from huey.contrib.djhuey import db_task, db_periodic_task
from huey import crontab
from bson.objectid import ObjectId
from django.conf import settings
from elasticsearch_dsl.connections import get_connection
from PIL import Image
from datetime import datetime
from subprocess import call
from PyPDF2 import PdfFileReader
from PyPDF2.pdf import ContentStream
from PyPDF2.generic import TextStringObject, u_, b_

from manager.utilities import _contains, build_search_params_from_dict
from django.utils.text import slugify
from zipfile import ZipFile

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
                "content_data": {
                    "value": "",
                    "type": "dict",
                    "label": "Content Data"
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
        "version": "0.2",
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
                "reindex": {
                    "value": False,
                    "type": "boolean",
                    "label": "Re-label?",
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
                    "label": "Comma separated content types",
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
    "Content Deletion Cleanup": {
        "version": "0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "content_path": {
                    "value": "",
                    "type": "text",
                    "label": "Content Path"
                }
            }
        },
        "module": 'manager.tasks',
        "functions": ['content_deletion_cleanup']
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
    "Pull Corpus Repo": {
        "version": "0.0",
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
                        "{0} {1}".format(
                            job.scholar.fname,
                            job.scholar.lname if job.scholar.lname else ''
                        ),
                        job.corpus_id,
                        job.content_type,
                        job.content_id,
                        datetime.now().ctime()
                    ), overwrite=True)

                task_module = importlib.import_module(job.jobsite.task_registry[job.task.name]['module'])
                task_function = getattr(task_module, job.jobsite.task_registry[job.task.name]['functions'][job.stage])
                task_function(job_id)
            except:
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
                job_ids = []
                if results['meta']['num_pages'] > num_pages:
                    num_pages = results['meta']['num_pages']

                for record in results['records']:
                    job_ids.append(
                        corpus.queue_local_job(
                            content_type=content_type,
                            content_id=record['id'],
                            task_id=task_id,
                            scholar_id=job.scholar_id,
                            parameters=job_params
                        )
                    )

                for j_id in job_ids:
                    run_job(j_id)
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
        content_data = job.get_param_value('content_data')

        if content_type in corpus.content_types:
            attrs = {}
            excluded_field_types = ['file', 'repo', 'embedded']
            ct = corpus.content_types[content_type]
            for field in ct.fields:
                if field.type not in excluded_field_types and not field.unique and field.name in content_data:
                    attrs[field.name] = content_data[field.name]

            if attrs:
                if content_ids:
                    content_ids = content_ids.split(',')
                    set_and_save_content(corpus, content_type, content_ids, attrs)
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

                            content_ids = []
                            for record in results['records']:
                                content_ids.append(record['id'])

                            set_and_save_content(corpus, content_type, content_ids, attrs)

                        page += 1

    job.complete('complete')


def set_and_save_content(corpus, content_type, content_ids, attrs):
    for content_id in content_ids:
        content = corpus.get_content(content_type, content_id, single_result=True)
        if content:
            for attr in attrs.keys():
                setattr(content, attr, attrs[attr])
                content.save()


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
        jobs = Job.get_jobs()
        for job in jobs:
            if job.jobsite.name == 'Local':
                if job.status == 'running':
                    if job.percent_complete == 100:
                        if len(job.jobsite.task_registry[job.task.name]['functions']) > (job.stage + 1):
                            job.clear_processes()
                            job.stage += 1
                            job.save()

                            task_module = importlib.import_module(job.jobsite.task_registry[job.task.name]['module'])
                            task_function = getattr(task_module, job.jobsite.task_registry[job.task.name]['functions'][job.stage])
                            task_function(job.id)
                        else:
                            job.complete(status='complete')
                elif job.status == 'queueing':
                    run_job(job.id)


@db_task(priority=1)
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
    primary_content_type = job.configuration['parameters']['content_type']['value']
    reindex = job.configuration['parameters']['reindex']['value']
    relabel = job.configuration['parameters']['relabel']['value']
    resave = job.configuration['parameters']['resave']['value']
    relink = job.configuration['parameters']['relink']['value']
    related_content_types = job.configuration['parameters']['related_content_types']['value']

    es_logger = logging.getLogger('elasticsearch')
    es_log_level = es_logger.getEffectiveLevel()
    es_logger.setLevel(logging.WARNING)

    content_types = related_content_types.split(',')
    content_types.insert(0, primary_content_type)
    content_types = [ct for ct in content_types if ct]

    completion_percentage = 0
    ct_completion_percentage = 100 / len(content_types)
    content_types_adjusted = 0
    for content_type in content_types:
        content_count = job.corpus.get_content(content_type, all=True).count()
        if content_count > 0:
            if content_types_adjusted > 0:
                reindex = True
                relabel = False
                resave = False
                relink = False

            num_slices = math.ceil(content_count / 500)
            slice_completion_percentage = ct_completion_percentage / num_slices
            for slice in range(0, num_slices):
                start = slice * 500
                end = start + 500

                adjust_content_slice(
                    job.corpus,
                    content_type,
                    start,
                    end,
                    reindex,
                    relabel,
                    resave,
                    relink
                )

                completion_percentage += slice_completion_percentage
                completion_percentage = int(completion_percentage)
                job.set_status('running', percent_complete=completion_percentage)

        content_types_adjusted += 1

    es_logger.setLevel(es_log_level)
    job.complete(status='complete')


def adjust_content_slice(corpus, content_type, start, end, reindex, relabel, resave, relink):
    contents = corpus.get_content(content_type, all=True)
    contents = contents.batch_size(10)
    contents = contents[start:end]
    for content in contents:
        if relabel:
            content.label = ''

        if relabel or resave:
            content.save(do_indexing=reindex, do_linking=relink)
        else:
            if reindex:
                content._do_indexing()

            if relink:
                content._do_linking()


@db_task(priority=5)
def delete_content_type(job_id):
    job = Job(job_id)
    job.set_status('running')
    content_type = job.configuration['parameters']['content_type']['value']
    if content_type in job.corpus.content_types:
        job.corpus.delete_content_type(content_type)

    job.complete(status='complete')


@db_task(priority=5)
def content_deletion_cleanup(job_id):
    job = Job(job_id)
    job.set_status('running')
    cleanup_path = job.get_param_value('content_path')
    if os.path.exists(cleanup_path):
        shutil.rmtree(cleanup_path)

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
                                                print(related_dict)
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
        print(source_ct_field)
        source_parts = source_ct_field.split('->')
        print(source_parts)
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
    if repo_name in job.corpus.repos:
        try:
            job.corpus.repos[repo_name].pull(job.corpus)
        except:
            job.corpus.repos[repo_name].error = True
            job.corpus.save()
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


@db_periodic_task(crontab(minute=1, hour='*'), priority=4)
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
            cv.populate()

