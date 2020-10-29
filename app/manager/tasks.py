import os
import json
import importlib
import time
import traceback
import pymysql
import logging
import math
import redis
from copy import deepcopy
from corpus import Corpus, Job, get_corpus, File
from huey.contrib.djhuey import db_task, db_periodic_task
from huey import crontab
from bson.objectid import ObjectId
from django.conf import settings
from PIL import Image
from datetime import datetime
from subprocess import call
from PyPDF2 import PdfFileReader
from PyPDF2.pdf import ContentStream
from PyPDF2.generic import TextStringObject, u_, b_

from manager.utilities import _contains
from django.utils.text import slugify
from zipfile import ZipFile

REGISTRY = {
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
}


@db_task(priority=3)
def run_job(job_id):
    job = Job(job_id)

    if job:
        if job.jobsite.type == 'HUEY':
            try:
                task_module = importlib.import_module(job.jobsite.task_registry[job.task.name]['module'])
                task_function = getattr(task_module, job.jobsite.task_registry[job.task.name]['functions'][job.stage])
                task_function(job_id)
            except:
                job.complete(status='error', error_msg="Error launching task: {0}".format(traceback.format_exc()))


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

    content_types_adjusted = 0
    for content_type in content_types:
        content_count = job.corpus.get_content(content_type, all=True).count()

        if content_types_adjusted > 0:
            reindex = True
            relabel = False
            resave = False
            relink = False

        num_slices = math.ceil(content_count / 500)
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