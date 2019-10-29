from corpus import *
from huey.contrib.djhuey import db_task, db_periodic_task
from huey import crontab
from bson.objectid import ObjectId
from django.conf import settings
from PIL import Image
from datetime import datetime
from subprocess import call
from PyPDF2 import PdfFileReader
from .utilities import setup_document_directory
from django.utils.text import slugify
import os
import importlib
import time
import traceback
import pymysql
from zipfile import ZipFile


REGISTRY = {
    "Zip Page File Collection": {
        "version": "0",
        "jobsite_type": "HUEY",
        "configuration": {
            "parameters": {
                "collection": {
                    "value": "",
                    "type": "page_file_collection",
                    "label": "Page File Collection",
                }
            },
        },
        "module": 'manager.tasks',
        "functions": ['zip_up_page_file_collection']
    },
    "Import Document Pages from PDF": {
        "version": "0",
        "jobsite_type": "HUEY",
        "configuration": {
            "parameters": {
                "pdf_file": {
                    "value": "",
                },
                "image_dpi": {
                    "value": "",
                },
                "split_images": {
                    "value": "",
                }
            },
        },
        "module": 'manager.tasks',
        "functions": ['extract_pdf_pages', 'complete_pdf_page_extraction']
    }
}


@db_task(priority=3)
def run_job(corpus_id, job_id):
    corpus = Corpus.objects(id=corpus_id)[0]
    job = corpus.get_job(job_id)

    if job:
        if job.job_site.type == 'HUEY':
            try:
                task_module = importlib.import_module(job.job_site.task_registry[job.task.name]['module'])
                task_function = getattr(task_module, job.job_site.task_registry[job.task.name]['functions'][job.stage])
                task_function(str(corpus.id), job_id)
            except:
                job.error = "Error firing task: {0}".format(traceback.format_exc())
                corpus.save_job(job)


@db_periodic_task(crontab(minute='*'), priority=4)
def check_jobs():
    corpora = Corpus.objects(jobs__status='running')
    for corpus in corpora:
        for job in corpus.jobs:
            if job.job_site.name == 'Local' and job.status == 'running':
                if len(job.processes) == len(job.processes_completed):
                    if len(job.job_site.task_registry[job.task.name]['functions']) > (job.stage + 1):
                        job.stage += 1
                        job.processes = []
                        job.processes_completed = []
                        corpus.save_job(job)

                        task_module = importlib.import_module(job.job_site.task_registry[job.task.name]['module'])
                        task_function = getattr(task_module, job.job_site.task_registry[job.task.name]['functions'][job.stage])
                        task_function(str(corpus.id), str(job.id))
                    else:
                        corpus.complete_job(job)


@db_task(priority=2)
def check_document(corpus_id, document_id):
    document = Document.objects(corpus=ObjectId(corpus_id), id=ObjectId(document_id))[0]

    if 'emop_work_id' in document.kvp and len(document.pages) > 0:
        for x in range(len(document.pages)):
            found_primary_witness = False

            for y in range(len(document.pages[x].files)):
                if document.pages[x].files[y].primary_witness:
                    found_primary_witness = True
                    if os.path.exists(document.pages[x].files[y].path) and not document.pages[x].files[y].width:
                        img = Image.open(document.pages[x].files[y].path)
                        document.pages[x].files[y].width, document.pages[x].files[y].height = img.size

            if not found_primary_witness:
                if os.path.exists(document.path):
                    image_files = os.listdir(document.path)
                    if 'ecco_no' in document.kvp:
                        for image_file in image_files:
                            if image_file.endswith('.TIF'):
                                ref_no = int(image_file.replace(str(document.kvp['ecco_no']), '').replace('.TIF', '')[:-1])
                                if document.pages[x].ref_no == ref_no:
                                    file = process_corpus_file(
                                        "{0}/{1}".format(document.path, image_file),
                                        desc="TIF Image",
                                        prov_type="Import script",
                                        prov_id="eMOP",
                                        primary=True
                                    )
                                    if file:
                                        document.pages[x].files.append(file)

        if 'emop_ocr_imported' not in document.kvp:
            tick = time.time()
            task_id = ObjectId("5c7852a5305b0f005039abb7")
            jobsite_id = ObjectId("5c8fa6cf39c9590040e11f29")
            scholar_id = ObjectId("5c65ae64e7d697004f6176f7")
            batch_info = {
                1: "ECCO w/o GT (SC8b-R7-D2b)",
                2: "ECCO with GT (SC8b-R7-D2b)",
                3: "EEBO with GT (SC8b-R8-D2b)",
                4: "EEBO w/o GT (SC8b-R8-D2b)"
            }

            job = None
            batch_id = -1

            db = pymysql.connect(
                host=settings.EMOP['host'],
                db=settings.EMOP['db'],
                user=settings.EMOP['user'],
                password=settings.EMOP['password'],
                cursorclass=pymysql.cursors.DictCursor
            )

            cursor = db.cursor()
            cursor.execute('''
                select * from pages, page_results
                where pg_work_id = work_id
                    and pg_page_id = page_id
                    and pg_work_id = {0}
                order by batch_id, pg_ref_number
            '''.format(document.kvp['emop_work_id']))

            emop_pages = cursor.fetchall()

            for emop_page in emop_pages:
                for pg_index in range(len(document.pages)):
                    if emop_page['pg_page_id'] == document.pages[pg_index].kvp['emop_page_id']:

                        if batch_id != emop_page['batch_id']:
                            job = None
                            batch_id = emop_page['batch_id']

                        if not job:
                            job = Job()
                            job.document = document
                            job.task = task_id
                            job.scholar = scholar_id
                            job.job_site = jobsite_id
                            job.status = 'complete'
                            job.configuration['notes'] = batch_info[emop_page['batch_id']]

                        # Add XML OCR results
                        if emop_page['corr_ocr_xml_path']:
                            xml_file_obj = process_corpus_file(
                                emop_page['corr_ocr_xml_path'],
                                desc='HOCR',
                                prov_type='eMOP OCR Job',
                                prov_id=str(job.id),
                            )
                            if xml_file_obj:
                                job.document.save_page_file(document.pages[pg_index].ref_no, xml_file_obj)

                        # Add text OCR results
                        if emop_page['corr_ocr_text_path']:
                            text_file_obj = process_corpus_file(
                                emop_page['corr_ocr_text_path'],
                                desc='Plain Text',
                                prov_type='eMOP OCR Job',
                                prov_id=str(job.id),
                            )
                            if text_file_obj:
                                job.document.save_page_file(document.pages[pg_index].ref_no, text_file_obj)

                        # Add TCP ground truth
                        if emop_page['pg_ground_truth_file']:
                            gt_file_obj = process_corpus_file(
                                emop_page['pg_ground_truth_file'],
                                desc='Ground Truth',
                                prov_type='Import script',
                                prov_id="eMOP",
                            )
                            if gt_file_obj:
                                job.document.save_page_file(document.pages[pg_index].ref_no, gt_file_obj)
                        break

            document.kvp['emop_ocr_imported'] = True
            document.save()
            tock = time.time() - tick
            print("Collecting eMOP OCR results took {0}".format(tock))

    document.kvp['corpora_document_checked'] = datetime.now()
    document.save()


###############################
#   FILE EXPORT JOBS
###############################

@db_task(priority=4, context=True)
def zip_up_page_file_collection(corpus_id, job_id, task=None):
    corpus = get_corpus(corpus_id)
    if corpus:
        job = corpus.get_job(job_id)
        if job and task:
            job.processes.append(task.id)
            job.status = 'running'
            corpus.save_job(job)

            page_file_collections = job.document.page_file_collections
            page_file_collection_key = job.configuration['parameters']['collection']['value']
            files_to_add = page_file_collections[page_file_collection_key]['files']
            zip_file_path = "{0}/files/{1}.zip".format(
                job.document.path,
                slugify(page_file_collection_key)
            )

            with ZipFile(zip_file_path, 'w') as zip_file:
                for file in files_to_add:
                    zip_file.write(
                        file['path'],
                        arcname="/{0}/{1}".format(
                            slugify(page_file_collection_key),
                            os.path.basename(file['path'])
                        )
                    )

            job.document.save_file(process_corpus_file(
                zip_file_path,
                desc="Exported .zip File",
                prov_type="Zip Page File Collection Job",
                prov_id=str(job_id)
            ))
            corpus.complete_job_process(job_id, task.id)


###############################
#   PDF PAGE EXTRACTION JOBS
###############################

@db_task(priority=2)
def extract_pdf_pages(corpus_id, job_id):
    corpus = Corpus.objects(id=corpus_id)[0]
    job = corpus.get_job(job_id)

    if job:
        setup_document_directory(corpus_id, str(job.document.id))
        pdf_file_path = job.configuration['parameters']['pdf_file']['value']
        image_dpi = job.configuration['parameters']['image_dpi']['value']
        split_images = job.configuration['parameters']['split_images']['value'] == 'Yes'

        if os.path.exists(pdf_file_path):
            with open(pdf_file_path, 'rb') as pdf_in:
                pdf_obj = PdfFileReader(pdf_in)
                num_pages = pdf_obj.getNumPages()

            if num_pages > 0:
                # Determine whether pages should be primary witness:
                primary_witness = True
                if job.document.page_file_collections:
                    for collection in job.document.page_file_collections.keys():
                        if collection.startswith('Primary') and 'Image' in collection:
                            primary_witness = False

                for page_num in range(0, num_pages):
                    huey_task = extract_pdf_page(corpus_id, job_id, pdf_file_path, page_num, image_dpi, split_images, primary_witness)
                    job.processes.append(huey_task.id)

                job.status = 'running'
                corpus.save_job(job)


@db_task(priority=1, context=True)
def extract_pdf_page(corpus_id, job_id, pdf_file_path, page_num, image_dpi, split_images, primary_witness, task=None):
    # Query database for corpus, job objects
    corpus = get_corpus(corpus_id)
    if corpus:
        job = corpus.get_job(job_id)
        if job:

            # Make file label by stripping off extension
            file_label = os.path.basename(pdf_file_path).split('.')[0]

            # Build page suffixes (page_b_suffix only needed if splitting image)
            page_suffix = str(page_num + 1)
            if split_images:
                page_suffix = str(((page_num + 1) * 2) - 1)
                page_b_suffix = str((page_num + 1) * 2)

            destination_path = "{0}/pages/{1}".format(job.document.path, page_suffix)
            if not os.path.exists(destination_path):
                os.makedirs(destination_path, exist_ok=True)

            if split_images:
                destination_b_path = "{0}/pages/{1}".format(job.document.path, page_b_suffix)
                if not os.path.exists(destination_b_path):
                    os.makedirs(destination_b_path, exist_ok=True)

            command = [
                "convert",
                "-density", image_dpi,
                pdf_file_path + "[" + str(page_num) + "]",
                "-flatten"
            ]

            if split_images:
                command.append("-crop")
                command.append("50%x100%")
                command.append("+repage")

            page_filename = "{0}_{1}.png".format(file_label, page_suffix)
            page_filepath = "{0}/{1}".format(destination_path, page_filename)
            command.append(page_filepath)
            call(command)

            if split_images:
                page_a_output_path = "{0}/{1}_{2}-{3}.png".format(destination_path, file_label, page_suffix, str(page_num))
                page_b_output_path = "{0}/{1}_{2}-{3}.png".format(destination_path, file_label, page_suffix, str(page_num + 1))
                page_b_filename = "{0}_{1}.png".format(file_label, page_b_suffix)
                page_b_filepath = "{0}/{1}".format(destination_b_path, page_b_filename)

                if os.path.exists(page_a_output_path) and os.path.exists(page_b_output_path):
                    os.rename(page_a_output_path, page_filepath)
                    os.rename(page_b_output_path, page_b_filepath)

                    # Make page_b file
                    page_b_fileobj = process_corpus_file(
                        page_b_filepath,
                        "PNG Page Image",
                        "PDF Page Extraction",
                        job.scholar.username,
                        primary_witness
                    )

                    job.document.reload()
                    existing_page = job.document.get_page(int(page_b_suffix))
                    if existing_page:
                        job.document.save_page_file(existing_page.ref_no, page_b_fileobj)
                    else:
                        page_b_obj = Page()
                        page_b_obj.ref_no = int(page_b_suffix)
                        page_b_obj.files.append(page_b_fileobj)
                        job.document.save_page(page_b_obj)

            if os.path.exists(page_filepath):
                # Make page file
                page_fileobj = process_corpus_file(
                    page_filepath,
                    "PNG Page Image",
                    "PDF Page Extraction",
                    job.scholar.username,
                    primary_witness
                )

                job.document.reload()
                existing_page = job.document.get_page(int(page_suffix))
                if existing_page:
                    job.document.save_page_file(existing_page.ref_no, page_fileobj)
                else:
                    page_obj = Page()
                    page_obj.ref_no = int(page_suffix)
                    page_obj.files.append(page_fileobj)
                    job.document.save_page(page_obj)

            if task:
                corpus.complete_job_process(job_id, task.id)


@db_task(priority=2)
def complete_pdf_page_extraction(corpus_id, job_id):
    corpus = get_corpus(corpus_id)
    if corpus:
        job = corpus.get_job(job_id)
        if job:
            job.document.sort_pages()
            corpus.complete_job(job)
