from subprocess import call
from django.utils.text import slugify
from huey.contrib.djhuey import db_task
from manager.utilities import setup_document_directory
from corpus import *

REGISTRY = {
    "OCR Document with Tesseract 4": {
        "version": "0",
        "jobsite_type": "HUEY",
        "configuration": {
            "parameters": {
                "collection": {
                    "value": "",
                    "type": "page_file_collection",
                    "label": "Page Image Collection",
                    "note": "Be sure to select a collection consisting of images."
                }
            },
        },
        "module": 'plugins.tesseract.tasks',
        "functions": ['ocr_document_with_tesseract']
     }
}


@db_task(priority=2)
def ocr_document_with_tesseract(corpus_id, job_id):
    corpus = get_corpus(corpus_id)
    if corpus:
        job = corpus.get_job(job_id)
        if job:
            setup_document_directory(corpus_id, str(job.document.id))
            page_file_collections = job.document.page_file_collections
            page_file_collection_key = job.configuration['parameters']['collection']['value']
            page_files = page_file_collections[page_file_collection_key]['files']
            num_pages = len(page_files)
            pages_per_worker = 5
            pages_allocated = 0

            while pages_allocated < num_pages:
                starting_page = pages_allocated
                ending_page = starting_page + pages_per_worker
                huey_task = ocr_pages_with_tesseract(corpus_id, job_id, starting_page, ending_page)
                job.processes.append(huey_task.id)
                pages_allocated = ending_page + 1

            job.status = 'running'
            corpus.save_job(job)


@db_task(priority=1, context=True)
def ocr_pages_with_tesseract(corpus_id, job_id, starting_page, ending_page, task=None):
    corpus = get_corpus(corpus_id)
    if corpus:
        job = corpus.get_job(job_id)
        if job:
            page_file_collections = job.document.page_file_collections
            page_file_collection_key = job.configuration['parameters']['collection']['value']
            page_files = page_file_collections[page_file_collection_key]['files'][starting_page:ending_page + 1]

            for page_file in page_files:
                page_file_path = page_file['path']
                os.makedirs("{0}/pages/{1}".format(job.document.path, page_file['page']), exist_ok=True)

                if os.path.exists(page_file_path):
                    # base path for different outputs
                    page_file_results = "{0}/pages/{1}/{2}_Tesseract4_{3}".format(
                        job.document.path,
                        page_file['page'],
                        slugify(page_file_collection_key),
                        page_file['page']
                    )

                    command = [
                        "tesseract",
                        page_file_path,
                        page_file_results,
                        "-l", "eng",
                        "hocr", "txt"
                    ]

                    if call(command) == 0:
                        txt_file_obj = process_corpus_file(
                            page_file_results + '.txt',
                            desc='Plain Text',
                            prov_type='Tesseract OCR Job',
                            prov_id=str(job_id),
                        )
                        if txt_file_obj:
                            job.document.save_page_file(page_file['page'], txt_file_obj)

                        hocr_file_obj = process_corpus_file(
                            page_file_results + '.hocr',
                            desc='HOCR',
                            prov_type='Tesseract OCR Job',
                            prov_id=str(job_id),
                        )
                        if hocr_file_obj:
                            job.document.save_page_file(page_file['page'], hocr_file_obj)

            if task:
                corpus.complete_job_process(job_id, task.id)
