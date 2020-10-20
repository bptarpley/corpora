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
    }
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
