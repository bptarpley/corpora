import os
import json
import traceback
from subprocess import call
from copy import deepcopy
from datetime import datetime
from huey.contrib.djhuey import db_task
from natsort import natsorted
from PyPDF2 import PdfFileReader
from PyPDF2.pdf import ContentStream
from PyPDF2.generic import TextStringObject, u_, b_
from elasticsearch_dsl.connections import get_connection
from django.conf import settings
from django.utils.text import slugify
from manager.utilities import _contains
from zipfile import ZipFile
from corpus import get_corpus, Job, File
from .content import Page


REGISTRY = {
    "Zip Page File Collection": {
        "version": "0",
        "jobsite_type": "HUEY",
        "content_type": "Document",
        "track_provenance": True,
        "configuration": {
            "parameters": {
                "collection": {
                    "value": "",
                    "type": "page_file_collection",
                    "label": "Page File Collection",
                }
            },
        },
        "module": 'plugins.document.tasks',
        "functions": ['zip_up_page_file_collection']
    },
    "Import Document Pages from PDF": {
        "version": "0.2",
        "jobsite_type": "HUEY",
        "content_type": "Document",
        "track_provenance": True,
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
        "module": 'plugins.document.tasks',
        "functions": ['extract_pdf_pages', 'complete_pdf_page_extraction']
    },
    "Cache Page File Collections": {
        "version": "0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Document",
        "configuration": {
            "parameters": {
                "page_file_collections": {
                    "value": None
                }
            },
        },
        "module": 'plugins.document.tasks',
        "functions": ['cache_page_file_collections']
    },
}


@db_task(priority=0)
def rebuild_corpus_index(corpus_id):
    corpus = get_corpus(corpus_id)
    if corpus:
        corpus.rebuild_index()


###############################
#   FILE EXPORT JOBS
###############################

@db_task(priority=4)
def zip_up_page_file_collection(job_id):
    job = Job(job_id)
    job.set_status('running')
    page_file_collections = job.content.page_file_collections
    page_file_collection_key = job.configuration['parameters']['collection']['value']

    files_to_add = []
    for ref_no, file in page_file_collections[page_file_collection_key]['page_files']:
        files_to_add.append(file)

    zip_file_path = "{0}/files/{1}.zip".format(
        job.content.path,
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

    job.content.save_file(File.process(
        zip_file_path,
        desc="Exported .zip File",
        prov_type="Zip Page File Collection Job",
        prov_id=str(job_id)
    ))
    job.complete(status='complete')


###############################
#   DOCUMENT IMP/EXPORT JOBS
###############################
@db_task(priority=2)
def import_document(corpus_id, document_json_path):
    valid = True

    if os.path.exists(document_json_path):
        with open(document_json_path, 'r') as doc_in:
            import_doc = json.load(doc_in)
        if import_doc and _contains(import_doc, [
            '_id',
            'title',
            'author',
            'pub_date'
        ]):
            corpus = get_corpus(corpus_id)
            doc = corpus.get_content('Document')
            doc.title = import_doc['title']
            doc.author = import_doc['author']
            doc.pub_date = import_doc['pub_date']
            doc.kvp = deepcopy(import_doc['kvp'])

            for key in list(doc.kvp.keys()):
                if key.startswith('_') or key in ["corpora_document_checked", "emop_ocr_imported"]:
                    doc.kvp.pop(key)

            for key in doc.kvp.keys():
                if key == "full_title":
                    doc.title = doc.kvp[key]
                elif hasattr(doc, key):
                    setattr(doc, key, doc.kvp[key])
                else:
                    print("ERROR: unable to account for this kvp key on doc w/ original id {0}: {1}".format(import_doc['_id']['$oid'], key))
                    valid = False

            if valid:
                doc.kvp = {}

                if 'jobs' in import_doc:
                    doc.emop_ocr_jobs = ""
                    for job in import_doc['jobs']:
                        if 'configuration' in job and 'notes' in job['configuration']:
                            doc.emop_ocr_jobs += job['configuration']['notes'] + ", "
                    if doc.emop_ocr_jobs:
                        doc.emop_ocr_jobs = doc.emop_ocr_jobs[:-2]

                for file in import_doc['files']:
                    f = File()
                    f.primary_witness = file['primary_facsimile']
                    f.path = file['path']
                    f.basename = file['basename']
                    f.extension = file['extension']
                    f.byte_size = file['byte_size']
                    f.description = file['description']
                    f.provenance_type = file['provenance_type']
                    f.provenance_id = file['provenance_id']

                    file_key = File.generate_key(f.path)
                    doc.files[file_key] = f

                for page in import_doc['pages']:
                    p = Page()
                    p.ref_no = str(page['ref_no'])
                    p.kvp = page['kvp']

                    for file in page['files']:
                        f = File()
                        f.primary_witness = file['primary_facsimile']
                        f.path = file['path']
                        f.basename = file['basename']
                        f.extension = file['extension']
                        f.byte_size = file['byte_size']
                        f.description = file['description']
                        f.provenance_type = file['provenance_type']
                        f.provenance_id = file['provenance_id']

                        file_key = File.generate_key(f.path)
                        p.files[file_key] = f

                    doc.pages[p.ref_no] = p

                try:
                    doc.save()
                except:
                    print(traceback.format_exc())
                    print("ORIGINAL DOC ID: {0}".format(import_doc['_id']['$oid']))
                    print("DOC KVP:")
                    print(json.dumps(doc.kvp, indent=4))


###############################
#   PDF PAGE EXTRACTION JOBS
###############################
@db_task(priority=2)
def extract_pdf_pages(job_id):
    job = Job(job_id)
    pdf_file_path = job.configuration['parameters']['pdf_file']['value']
    image_dpi = job.configuration['parameters']['image_dpi']['value']
    split_images = job.configuration['parameters']['split_images']['value'] == 'Yes'
    extract_text = job.configuration['parameters']['extract_text']['value'] == 'Yes'
    primary_witness = job.configuration['parameters']['primary_witness']['value'] == 'Yes'

    if os.path.exists(pdf_file_path):
        with open(pdf_file_path, 'rb') as pdf_in:
            pdf_obj = PdfFileReader(pdf_in)
            num_pages = pdf_obj.getNumPages()

        if num_pages > 0:
            if extract_text and not split_images:
                pages_created = False
                for page_num in range(0, num_pages):
                    ref_no = str(page_num + 1)
                    if ref_no not in job.content.pages:
                        page = Page()
                        page.ref_no = ref_no
                        job.content.pages[ref_no] = page
                        page_path = "{0}/pages/{1}".format(job.content.path, ref_no)
                        if not os.path.exists(page_path):
                            os.makedirs(page_path, exist_ok=True)
                        pages_created = True
                if pages_created:
                    job.content.save(perform_linking=True)

                huey_task = extract_embedded_pdf_text(job_id, pdf_file_path, primary_witness)
                job.add_process(huey_task.id)

            # Determine whether to remove primary witness designation from existing images
            # TODO: FIX THIS ONCE NEW PFC SYSTEM IS COMPLETE
            '''
            if primary_witness:
                doc_changed = False
                for ref_no in job.content.pages.keys():
                    for file_key in job.content.pages[ref_no].files.keys():
                        file = job.content.pages[ref_no].files[file_key]
                        # In case this is a retry, check to make sure existing files aren't from previous job attempt
                        if file.extension in settings.VALID_IMAGE_EXTENSIONS \
                                and file.primary_witness \
                                and not (file.provenance_type == 'PDF Page Extraction Job' and file.provenance_id == str(job.id)):
                            job.content.pages[ref_no].files[file_key].primary_witness = False
                            doc_changed = True
                if doc_changed:
                    job.content.save()
            '''

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

    destination_path = "{0}/pages/{1}".format(job.content.path, page_suffix)
    if not os.path.exists(destination_path):
        os.makedirs(destination_path, exist_ok=True)

    if split_images:
        destination_b_path = "{0}/pages/{1}".format(job.content.path, page_b_suffix)
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
            page_b_output_path = "{0}/{1}_{2}-{3}.png".format(destination_path, file_label, page_suffix,
                                                              str(page_num + 1))
            page_b_filename = "{0}_{1}.png".format(file_label, page_b_suffix)
            page_b_filepath = "{0}/{1}".format(destination_b_path, page_b_filename)

            if os.path.exists(page_a_output_path) and os.path.exists(page_b_output_path):
                os.rename(page_a_output_path, page_filepath)
                os.rename(page_b_output_path, page_b_filepath)

                # Make page_b file
                page_b_fileobj = File.process(
                    page_b_filepath,
                    desc="PNG Page Image",
                    prov_type="PDF Page Extraction Job",
                    prov_id=str(job.id),
                    primary=primary_witness
                )

                job.content.reload()
                if page_b_suffix in job.content.pages:
                    job.content.save_page_file(page_b_suffix, page_b_fileobj)
                else:
                    page_b_obj = Page()
                    page_b_obj.ref_no = page_b_suffix
                    job.content.save_page(page_b_obj)
                    job.content.save_page_file(page_b_suffix, page_b_fileobj)

    if os.path.exists(page_filepath):
        register_file = True
        file_key = File.generate_key(page_filepath)

        if page_suffix in job.content.pages:
            if file_key in job.content.pages[page_suffix].files:
                register_file = False

        if register_file:
            # Make page file
            page_fileobj = File.process(
                page_filepath,
                desc="PNG Page Image",
                prov_type="PDF Page Extraction Job",
                prov_id=str(job.id),
                primary=primary_witness
            )

            job.content.reload()
            if not page_suffix in job.content.pages:
                job.content.save_page(Page(ref_no=page_suffix))

            job.content.save_page_file(page_suffix, page_fileobj)

    if task:
        job.complete_process(task.id)


@db_task(priority=1, context=True)
def extract_embedded_pdf_text(job_id, pdf_file_path, primary_witness, task=None):
    job = Job(job_id)

    if os.path.exists(pdf_file_path):
        text_file_label = os.path.basename(pdf_file_path).split('.')[0]
        with open(pdf_file_path, 'rb') as pdf_in:
            pdf_obj = PdfFileReader(pdf_in)
            for ref_no, page in job.content.ordered_pages:
                pdf_page_num = int(ref_no) - 1
                pdf_page_text = _extract_pdf_page_text(pdf_obj.getPage(pdf_page_num))
                if pdf_page_text:
                    text_file_path = "{0}/pages/{1}/{2}_{3}.txt".format(job.content.path, ref_no, text_file_label,
                                                                        ref_no)
                    with open(text_file_path, 'w', encoding="utf-8") as text_out:
                        text_out.write(pdf_page_text)

                    text_file_obj = File.process(
                        text_file_path,
                        desc='Plain Text',
                        prov_type='PDF Page Extraction Job',
                        prov_id=str(job.id),
                        primary=primary_witness
                    )
                    if text_file_obj:
                        job.content.save_page_file(ref_no, text_file_obj)

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


@db_task(priority=1)
def complete_pdf_page_extraction(job_id):
    job = Job(job_id)
    job.content.save(index_pages=True, perform_linking=True)
    job.complete(status='complete')


@db_task(priority=0)
def index_document_pages(corpus_id, document_id, pages={}):
    body = { 'pages': [] }
    ref_nos = natsorted(list(pages.keys()))
    for ref_no in ref_nos:
        for file in pages[ref_no]['files']:
            if file['extension'] == 'txt' and file['primary_witness'] and os.path.exists(file['path']):
                contents = ""

                try:
                    with open(file['path'], 'r', encoding='utf-8') as file_in:
                        contents = file_in.read()
                except:
                    print("Error reading file {0} for indexing document {1}:".format(file['path'], document_id))
                    print(traceback.format_exc())

                body['pages'].append({
                    'ref_no': ref_no,
                    'contents': contents
                })

    get_connection().update(
        index='corpus-{0}-documents'.format(corpus_id),
        id=document_id,
        body={ 'doc': body },
    )
    # TODO: trigger upstream indexing of document if it belongs to a CorpusSet; use to_dict() to pass to task


@db_task(priority=0)
def cache_page_file_collections(job_id):
    job = Job(job_id)
    job.set_status('running')
    page_file_collections = job.configuration['parameters']['page_file_collections']['value']
    
    with settings.NEO4J.session() as neo:
        cypher = ""
        params = {}
        try:
            for slug in page_file_collections.keys():
                cypher = '''
                    MATCH (d:Document { uri: $doc_uri })
                    MERGE (d) -[:hasPageFileCollection]-> (pfc:PageFileCollection { uri: $pfc_uri })
                    SET pfc.created = $pfc_created
                    SET pfc.slug = $pfc_slug
                    SET pfc.label = $pfc_label
                    SET pfc.page_file_dict_json = $pfc_page_file_dict_json
                '''
                params = {
                    'doc_uri': "/corpus/{0}/Document/{1}".format(job.corpus_id, job.content_id),
                    'pfc_uri': "/corpus/{0}/Document/{1}/page-file-collection/{2}".format(job.corpus_id, job.content_id, slug),
                    'pfc_created': int(datetime.now().timestamp()),
                    'pfc_slug': slug,
                    'pfc_label': page_file_collections[slug]['label'],
                    'pfc_page_file_dict_json': json.dumps(page_file_collections[slug]['page_files'])
                }
                neo.run(cypher, **params)
        except:
            print("Error running Neo4J cypher!")
            print("Cypher: {0}".format(cypher))
            print("Params: {0}".format(json.dumps(params, indent=4)))
            print(traceback.format_exc())
        finally:
            neo.close()

    job.complete("complete")
