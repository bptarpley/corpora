from subprocess import call
from django.utils.text import slugify
from huey.contrib.djhuey import db_task
from corpus import *

REGISTRY = {
    "OCR Document with Tesseract 4": {
        "version": "0.3",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Document",
        "configuration": {
            "parameters": {
                "collection": {
                    "value": "",
                    "type": "page_file_collection",
                    "label": "Page Image Collection",
                    "note": "Be sure to select a collection consisting of images."
                },
                "primary_witness": {
                    "label": "Make Primary Witness?",
                    "type": "choice",
                    "choices": [
                        "Yes",
                        "No"
                    ],
                    "value": "Yes",
                    "note": "If you have not yet OCR'd this document, or if you'd like to replace existing OCR results as the primary witness for this document, this should remain set to 'Yes.'"
                }
            },
        },
        "module": 'plugins.tesseract.tasks',
        "functions": ['ocr_document_with_tesseract', 'complete_ocr_document_with_tesseract']
     }
}


@db_task(priority=2)
def ocr_document_with_tesseract(job_id):
    job = Job(job_id)
    job.set_status('running')

    try:
        page_file_collection_key = job.get_param_value('collection')
        print(page_file_collection_key)
        page_files = job.content.page_file_collections[page_file_collection_key]['page_files']
        primary_witness = job.configuration['parameters']['primary_witness']['value'] == 'Yes'
        num_pages = len(page_files.ordered_ref_nos)
        pages_per_worker = 5
        pages_allocated = 0

        if primary_witness:
            unset_primary(job.content, 'plain text')
            unset_primary(job.content, 'hocr')
            job.content.save()

        while pages_allocated < num_pages:
            starting_page = pages_allocated
            ending_page = starting_page + pages_per_worker
            huey_task = ocr_pages_with_tesseract(job_id, starting_page, ending_page, primary_witness)
            job.add_process(huey_task.id)
            pages_allocated = ending_page + 1

    except:
        error = traceback.format_exc()
        print(error)
        job.complete('error', error_msg=error)


@db_task(priority=1, context=True)
def ocr_pages_with_tesseract(job_id, starting_page, ending_page, primary_witness, task=None):
    job = Job(job_id)
    page_file_collection_key = job.get_param_value('collection')
    page_files = job.content.page_file_collections[page_file_collection_key]['page_files']
    assigned_pages = page_files.ordered_ref_nos[starting_page:ending_page + 1]

    for ref_no, file in page_files:
        if ref_no in assigned_pages:
            os.makedirs("{0}/pages/{1}".format(job.content.path, ref_no), exist_ok=True)

            if os.path.exists(file['path']):
                # base path for different outputs
                page_file_results = "{0}/pages/{1}/{2}_Tesseract4_{3}".format(
                    job.content.path,
                    ref_no,
                    page_file_collection_key,
                    ref_no
                )

                command = [
                    "tesseract",
                    file['path'],
                    page_file_results,
                    "-l", "eng",
                    "--psm", "1",
                    "hocr", "txt"
                ]

                if call(command) == 0:
                    txt_file_obj = File.process(
                        page_file_results + '.txt',
                        desc='Plain Text',
                        prov_type='Tesseract OCR Job',
                        prov_id=str(job_id),
                        primary=primary_witness
                    )
                    if txt_file_obj:
                        job.content.save_page_file(ref_no, txt_file_obj)

                    hocr_file_obj = File.process(
                        page_file_results + '.hocr',
                        desc='HOCR',
                        prov_type='Tesseract OCR Job',
                        prov_id=str(job_id),
                        primary=primary_witness
                    )
                    if hocr_file_obj:
                        job.content.save_page_file(ref_no, hocr_file_obj)

    if task:
        job.complete_process(task.id)


@db_task(priority=2)
def complete_ocr_document_with_tesseract(job_id):
    job = Job(job_id)
    job.content.save(index_pages=True)
    job.complete(status='complete')


def unset_primary(doc, file_type):
    page_keys = list(doc.pages.keys())
    for page_key in page_keys:
        file_keys = list(doc.pages[page_key].files.keys())
        for file_key in file_keys:
            if doc.pages[page_key].files[file_key].primary_witness and file_type.lower() in doc.pages[page_key].files[file_key].description.lower():
                doc.pages[page_key].files[file_key].primary_witness = False