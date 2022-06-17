from subprocess import call
from django.utils.text import slugify
from huey.contrib.djhuey import db_task
from timeit import default_timer as timer
from corpus import *

REGISTRY = {
    "OCR Document with Tesseract 4": {
        "version": "0.5",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "create_report": True,
        "content_type": "Document",
        "configuration": {
            "parameters": {
                "collection": {
                    "value": "",
                    "type": "page_file_collection",
                    "label": "Page Image Collection",
                    "note": "Be sure to select a collection consisting of images."
                },
                "pageset": {
                    "value": "",
                    "type": "document_pageset",
                    "label": "Page Set",
                    "note": 'Choose "All Pages" to OCR every page, or select a page set to OCR a subset of pages.'
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
        pageset_key = job.get_param_value('pageset')
        page_files = job.content.page_file_collections[page_file_collection_key]['page_files']
        primary_witness = job.configuration['parameters']['primary_witness']['value'] == 'Yes'

        ref_nos = []
        if pageset_key == "none":
            ref_nos = page_files.ordered_ref_nos
        elif pageset_key in job.content.page_sets:
            ref_nos = [ref_no for ref_no in page_files.ordered_ref_nos if ref_no in job.content.page_sets[pageset_key].ref_nos]

        num_pages = len(ref_nos)

        if num_pages > 0:
            job.report("Attempting to OCR {0} pages for page file collection {1}.".format(num_pages, page_file_collection_key))
            if pageset_key != "none":
                job.report("Limiting pages to those found in page set {0}.".format(job.content.page_sets[pageset_key].label))

            if primary_witness:
                unset_primary(job.content, 'plain text')
                unset_primary(job.content, 'hocr')
                job.content.save()

            for ref_no in ref_nos:
                huey_task = ocr_page_with_tesseract(job_id, ref_no, primary_witness)
                job.add_process(huey_task.id)
        else:
            job.report("No valid pages found to OCR!")

    except:
        error = traceback.format_exc()
        print(error)
        job.complete('error', error_msg=error)


@db_task(priority=1, context=True)
def ocr_page_with_tesseract(job_id, assigned_ref_no, primary_witness, task=None):
    job = Job(job_id)
    page_file_collection_key = job.get_param_value('collection')
    page_files = job.content.page_file_collections[page_file_collection_key]['page_files']
    time_start = timer()

    for ref_no, file in page_files:
        if ref_no == assigned_ref_no:
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
                    "--psm", "6",
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
            break

    if task:
        time_stop = timer()
        job.report("Tesseract OCR'd page {0} in {1} seconds.".format(assigned_ref_no, time_stop - time_start))
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