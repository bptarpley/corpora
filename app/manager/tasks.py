import os
import json
import importlib
import time
import traceback
import pymysql
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
        "version": "0",
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
                "resave": {
                    "value": False,
                    "type": "boolean",
                    "label": "Re-save?",
                }
            },
        },
        "module": 'manager.tasks',
        "functions": ['adjust_content']
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
    content_type = job.configuration['parameters']['content_type']['value']
    reindex = job.configuration['parameters']['reindex']['value']
    relabel = job.configuration['parameters']['relabel']['value']
    resave = job.configuration['parameters']['resave']['value']
    contents = job.corpus.get_content(content_type, all=True)
    for content in contents:
        if relabel:
            content.label = ''

        if relabel or resave:
            content.save(do_indexing=reindex)
        elif reindex:
            content._do_indexing()

    job.complete(status='complete')
