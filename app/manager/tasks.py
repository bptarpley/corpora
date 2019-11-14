import os
import importlib
import time
import traceback
import pymysql
from corpus import Corpus, Document, Page, Job, process_corpus_file, get_corpus
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

from manager.utilities import setup_document_directory, get_field_value_from_path
from django.utils.text import slugify
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
        "version": "0.1",
        "jobsite_type": "HUEY",
        "configuration": {
            "parameters": {
                "pdf_file": {
                    "value": "",
                },
                "image_dpi": {
                    "value": "300",
                },
                "split_images": {
                    "value": "No",
                },
                "extract_text": {
                    "value": "Yes"
                },
                "primary_witness": {
                    "value": "No"
                },
            },
        },
        "module": 'manager.tasks',
        "functions": ['extract_pdf_pages']
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
        if job.jobsite.name == 'Local' and job.status == 'running':
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


@db_task(priority=2)
def check_document(corpus_id, document_id):
    document = Document.objects(corpus=ObjectId(corpus_id), id=ObjectId(document_id))[0]
    document_changed = False

    if 'emop_work_id' in document.kvp and document.pages:
        for ref_no in document.pages.keys():
            found_primary_witness = False

            for y in range(len(document.pages[ref_no].files)):
                if document.pages[ref_no].files[y].primary_witness:
                    found_primary_witness = True
                    if os.path.exists(document.pages[ref_no].files[y].path) and not document.pages[ref_no].files[y].width:
                        img = Image.open(document.pages[ref_no].files[y].path)
                        document.pages[ref_no].files[y].width, document.pages[ref_no].files[y].height = img.size
                        document_changed = True

            if not found_primary_witness:
                if os.path.exists(document.path):
                    image_files = os.listdir(document.path)
                    if 'ecco_no' in document.kvp:
                        for image_file in image_files:
                            if image_file.endswith('.TIF'):
                                image_ref_no = int(image_file.replace(str(document.kvp['ecco_no']), '').replace('.TIF', '')[:-1])
                                if ref_no == image_ref_no:
                                    file = process_corpus_file(
                                        "{0}/{1}".format(document.path, image_file),
                                        desc="TIF Image",
                                        prov_type="Import script",
                                        prov_id="eMOP",
                                        primary=True
                                    )
                                    if file:
                                        document.pages[ref_no].files.append(file)
                                        document_changed = True

        if '_emop_ocr_imported' not in document.kvp:
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
                for ref_no in document.pages.keys():
                    if emop_page['pg_page_id'] == document.pages[ref_no].kvp['emop_page_id']:

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
                            document.modify(push__jobs=job)

                        # Add XML OCR results
                        if emop_page['corr_ocr_xml_path']:
                            xml_file_obj = process_corpus_file(
                                emop_page['corr_ocr_xml_path'],
                                desc='HOCR',
                                prov_type='eMOP OCR Job',
                                prov_id=str(job.id),
                                primary=True
                            )
                            if xml_file_obj:
                                document.save_page_file(ref_no, xml_file_obj)

                        # Add text OCR results
                        if emop_page['corr_ocr_text_path']:
                            text_file_obj = process_corpus_file(
                                emop_page['corr_ocr_text_path'],
                                desc='Plain Text',
                                prov_type='eMOP OCR Job',
                                prov_id=str(job.id),
                                primary=not emop_page['pg_ground_truth_file']
                            )
                            if text_file_obj:
                                document.save_page_file(ref_no, text_file_obj)

                        # Add TCP ground truth
                        if emop_page['pg_ground_truth_file']:
                            gt_file_obj = process_corpus_file(
                                emop_page['pg_ground_truth_file'],
                                desc='Ground Truth',
                                prov_type='Import script',
                                prov_id="eMOP",
                                primary=True
                            )
                            if gt_file_obj:
                                document.save_page_file(ref_no, gt_file_obj)
                        document_changed = True
                        break

            document.modify(set__kvp___emop_ocr_imported=True)
            tock = time.time() - tick
            print("Collecting eMOP OCR results took {0}".format(tock))

    document.modify(set__kvp___document_checked=datetime.now())
    if document_changed:
        document.save(index_pages=True)


###############################
#   FILE EXPORT JOBS
###############################

@db_task(priority=4)
def zip_up_page_file_collection(job_id):
    job = Job(job_id)
    job.set_status('running')
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
    job.complete(status='complete')


###############################
#   PDF PAGE EXTRACTION JOBS
###############################
@db_task(priority=2)
def extract_pdf_pages(job_id):
    job = Job(job_id)
    setup_document_directory(job.corpus_id, job.document_id)
    pdf_file_path = job.configuration['parameters']['pdf_file']['value']
    image_dpi = job.configuration['parameters']['image_dpi']['value']
    split_images = job.configuration['parameters']['split_images']['value'] == 'Yes'
    extract_text = job.configuration['parameters']['extract_text']['value'] == 'Yes'
    primary_witness = job.configuration['parameters']['primary_witness']['value'] == 'Yes'

    if os.path.exists(pdf_file_path):
        pdf_page_text = []
        with open(pdf_file_path, 'rb') as pdf_in:
            pdf_obj = PdfFileReader(pdf_in)
            num_pages = pdf_obj.getNumPages()
            if extract_text and not split_images:
                for page_num in range(0, num_pages):
                    pdf_page_text.append(_extract_pdf_page_text(pdf_obj.getPage(page_num)))

        if num_pages > 0:
            # Store any extracted text
            if extract_text and len(pdf_page_text) == num_pages:
                text_file_label = os.path.basename(pdf_file_path).split('.')[0]
                for page_num in range(0, num_pages):
                    ref_no = str(page_num + 1)
                    page = None

                    if ref_no not in job.document.pages:
                        page = Page()
                        page.ref_no = ref_no
                        job.document.save_page(page)
                    else:
                        page = job.document.pages[ref_no]

                    if page:
                        page_path = "{0}/pages/{1}".format(job.document.path, ref_no)
                        if not os.path.exists(page_path):
                            os.makedirs(page_path, exist_ok=True)

                        text_file_path = "{0}/{1}_{2}.txt".format(page_path, text_file_label, ref_no)
                        with open(text_file_path, 'w', encoding="utf-8") as text_out:
                            text_out.write(pdf_page_text[page_num])

                        text_file_obj = process_corpus_file(
                            text_file_path,
                            desc='Plain Text',
                            prov_type='PDF Page Extraction Job',
                            prov_id=str(job.id),
                            primary=primary_witness
                        )
                        if text_file_obj:
                            job.document.save_page_file(ref_no, text_file_obj)
                job.document.save(index_pages=True)

            # Determine whether to remove primary witness designation from existing images
            if primary_witness:
                doc_changed = False
                for ref_no in job.document.pages.keys():
                    for file_index in range(0, len(job.document.pages[ref_no].files)):
                        file = job.document.pages[ref_no].files[file_index]
                        # In case this is a retry, check to make sure existing files aren't from previous job attempt
                        if file.extension in settings.VALID_IMAGE_EXTENSIONS \
                                and file.primary_witness \
                                and not (file.provenance_type == 'PDF Page Extraction Job' and file.provenance_id == str(job.id)):
                            job.document.pages[ref_no].files[file_index].primary_witness = False
                            doc_changed = True
                if doc_changed:
                    job.document.save()

            for page_num in range(0, num_pages):
                huey_task = extract_pdf_page(job_id, pdf_file_path, page_num, image_dpi, split_images, primary_witness)
                job.add_process(huey_task.id)

            job.set_status('running')


@db_task(priority=1, context=True)
def extract_pdf_page(job_id, pdf_file_path, page_num, image_dpi, split_images, primary_witness, task=None):
    job = Job(job_id)

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

    if not os.path.exists(page_filepath) or split_images:
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
                    desc="PNG Page Image",
                    prov_type="PDF Page Extraction Job",
                    prov_id=str(job.id),
                    primary=primary_witness
                )

                job.document.reload()
                if page_b_suffix in job.document.pages:
                    job.document.save_page_file(page_b_suffix, page_b_fileobj)
                else:
                    page_b_obj = Page()
                    page_b_obj.ref_no = page_b_suffix
                    page_b_obj.files.append(page_b_fileobj)
                    job.document.save_page(page_b_obj)

    if os.path.exists(page_filepath):
        register_file = True
        if page_suffix in job.document.pages:
            for file in job.document.pages[page_suffix].files:
                if file.path == page_filepath:
                    register_file = False
                    break

        if register_file:
            # Make page file
            page_fileobj = process_corpus_file(
                page_filepath,
                desc="PNG Page Image",
                prov_type="PDF Page Extraction Job",
                prov_id=str(job.id),
                primary=primary_witness
            )

            job.document.reload()
            if page_suffix in job.document.pages:
                job.document.save_page_file(page_suffix, page_fileobj)
            else:
                page_obj = Page()
                page_obj.ref_no = page_suffix
                page_obj.files.append(page_fileobj)
                job.document.save_page(page_obj)

    if task:
        job.complete_process(task.id)


# Modified from https://github.com/mstamy2/PyPDF2/blob/master/PyPDF2/pdf.py#L2647
def _extract_pdf_page_text(pdf_page):
    """
    Locate all text drawing commands, in the order they are provided in the
    content stream, and extract the text.  This works well for some PDF
    files, but poorly for others, depending on the generator used.  This will
    be refined in the future.  Do not rely on the order of text coming out of
    this function, as it will change if this function is made more
    sophisticated.
    :return: a unicode string object.
    """
    text = u_("")
    content = pdf_page["/Contents"].getObject()
    if not isinstance(content, ContentStream):
        content = ContentStream(content, pdf_page.pdf)
    # Note: we check all strings are TextStringObjects.  ByteStringObjects
    # are strings where the byte->string encoding was unknown, so adding
    # them to the text here would be gibberish.
    for operands, operator in content.operations:
        if operator == b_("Tj"):
            _text = operands[0]
            if isinstance(_text, TextStringObject):
                text += " " + _text
                text += "\n"
        elif operator == b_("T*"):
            text += "\n"
        elif operator == b_("'"):
            text += "\n"
            _text = operands[0]
            if isinstance(_text, TextStringObject):
                text += " " + _text
        elif operator == b_('"'):
            _text = operands[2]
            if isinstance(_text, TextStringObject):
                text += "\n"
                text += " " + _text
        elif operator == b_("TJ"):
            for i in operands[0]:
                if isinstance(i, TextStringObject):
                    text += " " + i
            text += "\n"
    return text