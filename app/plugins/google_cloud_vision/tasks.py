import io
from django.utils.text import slugify
from huey.contrib.djhuey import db_task
from manager.utilities import setup_document_directory
from google.cloud import vision
from corpus import *


REGISTRY = {
    "OCR Document with Google Cloud Vision": {
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
        "module": 'plugins.google_cloud_vision.tasks',
        "functions": ['ocr_document_with_google_cloud_vision']
     }
}


@db_task(priority=2)
def ocr_document_with_google_cloud_vision(corpus_id, job_id):
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
                huey_task = ocr_pages_with_google_cloud_vision(corpus_id, job_id, starting_page, ending_page)
                job.processes.append(huey_task.id)
                pages_allocated = ending_page + 1

            job.status = 'running'
            corpus.save_job(job)


@db_task(priority=1, context=True)
def ocr_pages_with_google_cloud_vision(corpus_id, job_id, starting_page, ending_page, task=None):
    file_size_limit = 9500000

    corpus = get_corpus(corpus_id)
    if corpus:
        job = corpus.get_job(job_id)
        if job:
            client = vision.ImageAnnotatorClient()

            page_file_collections = job.document.page_file_collections
            page_file_collection_key = job.configuration['parameters']['collection']['value']
            page_files = page_file_collections[page_file_collection_key]['files'][starting_page:ending_page + 1]

            for page_file in page_files:
                page_file_path = page_file['path']
                os.makedirs("{0}/pages/{1}".format(job.document.path, page_file['page']), exist_ok=True)

                if os.path.exists(page_file_path):
                    file_size = page_file['byte_size']
                    if file_size > file_size_limit:
                        extension = '.' + page_file_path.split('.')[-1]
                        small_image_path = "{0}/pages/{1}/{2}".format(
                            job.document.path,
                            page_file['page'],
                            os.path.basename(page_file_path).replace(extension, "_downsized" + extension),
                        )
                        small_width = 3000
                        img = Image.open(page_file_path)
                        width_percent = (small_width / float(img.size[0]))
                        small_height = int((float(img.size[1]) * float(width_percent)))
                        img.thumbnail((small_width, small_height), Image.ANTIALIAS)
                        img.save(small_image_path)
                        if os.path.exists(small_image_path):
                            page_file_path = small_image_path

                    with io.open(page_file_path, 'rb') as page_contents:
                        content = page_contents.read()

                    if content:
                        image = vision.types.Image(content=content)
                        ocr = client.document_text_detection(image=image).full_text_annotation

                        # base path for different outputs
                        page_file_results = "{0}/pages/{1}/{2}_GCV_{3}".format(
                            job.document.path,
                            page_file['page'],
                            slugify(page_file_collection_key),
                            page_file['page']
                        )

                        with open(page_file_results + '.txt', 'w', encoding="utf-8") as text_out:
                            text_out.write(ocr.text)

                        breaks = vision.enums.TextAnnotation.DetectedBreak.BreakType
                        html = "<html><head></head><body>"
                        for page in ocr.pages:
                            html += "<div>"
                            for block in page.blocks:
                                html += "<div>"
                                for paragraph in block.paragraphs:
                                    html += "<p>"
                                    for word in paragraph.words:
                                        for symbol in word.symbols:
                                            html += symbol.text
                                            if symbol.property.detected_break.type == breaks.SPACE:
                                                html += ' '
                                            elif symbol.property.detected_break.type == breaks.EOL_SURE_SPACE:
                                                html += '<br />'
                                            elif symbol.property.detected_break.type == breaks.LINE_BREAK:
                                                html += '<br />'
                                            elif symbol.property.detected_break.type == breaks.HYPHEN:
                                                html += '-<br />'
                                    html += "</p>"
                                html += "</div>"
                            html += "</div>"
                        html += "</body></html>"

                        with open(page_file_results + '.html', 'w', encoding="utf-8") as html_out:
                            html_out.write(html)

                        with open(page_file_results + '.object', 'wb') as obj_out:
                            obj_out.write(ocr.SerializeToString())

                        txt_file_obj = process_corpus_file(
                            page_file_results + '.txt',
                            desc='Plain Text',
                            prov_type='Google Cloud Vision OCR Job',
                            prov_id=str(job_id),
                        )
                        if txt_file_obj:
                            job.document.save_page_file(page_file['page'], txt_file_obj)

                        html_file_obj = process_corpus_file(
                            page_file_results + '.html',
                            desc='HTML',
                            prov_type='Google Cloud Vision OCR Job',
                            prov_id=str(job_id),
                        )
                        if txt_file_obj:
                            job.document.save_page_file(page_file['page'], html_file_obj)

                        gcv_file_obj = process_corpus_file(
                            page_file_results + '.object',
                            desc='GCV TextAnnotation Object',
                            prov_type='Google Cloud Vision OCR Job',
                            prov_id=str(job_id),
                        )
                        if gcv_file_obj:
                            job.document.save_page_file(page_file['page'], gcv_file_obj)

            if task:
                corpus.complete_job_process(job_id, task.id)