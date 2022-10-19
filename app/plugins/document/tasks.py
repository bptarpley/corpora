import os
import json
import traceback
import fitz
import shutil
from PIL import Image
from copy import deepcopy
from datetime import datetime
from huey.contrib.djhuey import db_task
from natsort import natsorted
from elasticsearch_dsl.connections import get_connection
from django.utils.text import slugify
from django.conf import settings
from manager.utilities import _contains
from zipfile import ZipFile
from corpus import get_corpus, Job, File, run_neo
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
        "version": "0.3",
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
        "functions": ['extract_pdf_pages']
    },
    "Import Document Pages from Images": {
        "version": "0.2",
        "jobsite_type": "HUEY",
        "content_type": "Document",
        "track_provenance": True,
        "configuration": {
            "parameters": {
                "import_files_json": {
                    "value": "",
                },
                "images_type": {
                    "value": "file"
                },
                "split_images": {
                    "value": "No",
                },
                "primary_witness": {
                    "value": "No"
                },
            },
        },
        "module": 'plugins.document.tasks',
        "functions": ['import_page_images']
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
    job.set_status('running')

    pdf_file_path = job.configuration['parameters']['pdf_file']['value']
    image_dpi = job.configuration['parameters']['image_dpi']['value']
    split_images = job.configuration['parameters']['split_images']['value'] == 'Yes'
    extract_text = job.configuration['parameters']['extract_text']['value'] == 'Yes'
    primary_witness = job.configuration['parameters']['primary_witness']['value'] == 'Yes'
    page_file_label = os.path.basename(pdf_file_path).split('.')[0]

    if os.path.exists(pdf_file_path):
        if primary_witness:
            unset_primary(job.content, 'image')
            if extract_text:
                unset_primary(job.content, 'text')

        pdf_obj = fitz.open(pdf_file_path)
        num_pages = pdf_obj.page_count
        if split_images:
            num_pages = num_pages * 2

        for page_num in range(0, num_pages):
            ref_no = str(page_num + 1)
            job.content.pages[ref_no] = Page()
            job.content.pages[ref_no].ref_no = ref_no

        ref_no = 1
        for pdf_page in pdf_obj:
            pix = pdf_page.get_pixmap(matrix=fitz.Matrix(2, 2))
            threshold = pix.width / 2

            if split_images:
                mode = "RGBA" if pix.alpha else "RGB"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

                img_a = img.crop((0, 0, threshold, pix.height))
                process_page_file(
                    job.content,
                    str(ref_no),
                    page_file_label,
                    str(job.id),
                    primary_witness,
                    image=img_a
                )

                img_b = img.crop((threshold, 0, pix.width, pix.height))
                process_page_file(
                    job.content,
                    str(ref_no + 1),
                    page_file_label,
                    str(job.id),
                    primary_witness,
                    image=img_b
                )
            else:
                process_page_file(
                    job.content,
                    str(ref_no),
                    page_file_label,
                    str(job.id),
                    primary_witness,
                    image=pix
                )

            if extract_text:
                page_dict = pdf_page.get_text("dict")
                threshold = page_dict['width'] / 2
                text_a = []
                text_b = []

                for block in page_dict['blocks']:
                    if 'lines' in block:
                        for line in block['lines']:
                            if 'spans' in line:
                                for span in line['spans']:
                                    if 'text' in span and 'bbox' in span:
                                        if split_images and 'bbox' in span:
                                            x = span['bbox'][0]
                                            if x >= threshold:
                                                text_b.append(span['text'])
                                            else:
                                                text_a.append(span['text'])
                                        elif not split_images:
                                            text_a.append(span['text'])

                process_page_file(
                    job.content,
                    str(ref_no),
                    page_file_label,
                    str(job.id),
                    primary_witness,
                    text=" ".join(text_a)
                )

                if split_images:
                    process_page_file(
                        job.content,
                        str(ref_no + 1),
                        page_file_label,
                        str(job.id),
                        primary_witness,
                        text=" ".join(text_b)
                    )

            if split_images:
                ref_no += 2
            else:
                ref_no += 1

            job.set_status('running', percent_complete=int((ref_no / num_pages) * 100))
        job.content.save()
    job.complete(status='complete')


@db_task(priority=2)
def import_page_images(job_id):
    job = Job(job_id)
    job.set_status('running')

    import_files = json.loads(job.get_param_value('import_files_json'))
    images_type = job.get_param_value('images_type')
    split_images = job.get_param_value('split_images') == 'Yes'
    primary_witness = job.get_param_value('primary_witness') == 'Yes'

    unzip_path = None
    if images_type == 'zip' and len(import_files) == 1 and import_files[0].lower().endswith('.zip') and os.path.exists(import_files[0]):
        unzip_dir_name = "{job_id}_unzipped_image_import".format(job_id=job_id)
        unzip_path = os.path.dirname(import_files[0]) + '/' + unzip_dir_name

        if os.path.exists(unzip_path):
            shutil.rmtree(unzip_path)

        with ZipFile(import_files[0], 'r') as zip_in:
            zip_in.extractall(unzip_path)

        if os.path.exists(unzip_path):
            import_files = [unzip_path + '/' + img for img in os.listdir(unzip_path) if os.path.splitext(img)[1].replace('.', '').lower() in settings.VALID_IMAGE_EXTENSIONS]

    if import_files:
        if primary_witness:
            unset_primary(job.content, 'image')

        page_file_label = slugify(job.content.title.strip())
        num_pages = len(import_files)
        if split_images:
            num_pages = num_pages * 2

        for page_num in range(0, num_pages):
            ref_no = str(page_num + 1)
            job.content.pages[ref_no] = Page()
            job.content.pages[ref_no].ref_no = ref_no

        if images_type in ['file', 'zip']:
            import_files = natsorted(import_files)

        ref_no = 1

        for import_file in import_files:
            if images_type in ['file', 'zip']:
                if os.path.exists(import_file):
                    full_image = Image.open(import_file)

                    if split_images:
                        width, height = full_image.size
                        threshold = width / 2

                        img_a = full_image.crop((0, 0, threshold, height))
                        process_page_file(
                            job.content,
                            str(ref_no),
                            page_file_label,
                            str(job.id),
                            primary_witness,
                            image=img_a,
                            prov_type="Page Image Import Job"
                        )

                        img_b = full_image.crop((threshold, 0, width, height))
                        process_page_file(
                            job.content,
                            str(ref_no + 1),
                            page_file_label,
                            str(job.id),
                            primary_witness,
                            image=img_b,
                            prov_type="Page Image Import Job"
                        )

                    else:
                        process_page_file(
                            job.content,
                            str(ref_no),
                            page_file_label,
                            str(job.id),
                            primary_witness,
                            image=full_image,
                            prov_type="Page Image Import Job"
                        )

                    os.remove(import_file)

            elif images_type == 'iiif':
                iiif_file = File.process(
                    import_file,
                    desc="IIIF Image",
                    prov_type="Page Image Import Job",
                    prov_id=str(job.id),
                    primary=primary_witness,
                    external_iiif=True
                )
                if iiif_file:
                    if split_images:
                        original_width = iiif_file.width
                        threshold = int(original_width / 2)

                        iiif_file.iiif_info['fixed_region'] = {
                            'x': 0,
                            'y': 0,
                            'w': threshold,
                            'h': iiif_file.height
                        }
                        iiif_file.width = threshold
                        job.content.pages[str(ref_no)].files[iiif_file.key] = iiif_file

                        iiif_file_b = File()
                        iiif_file_b.path = iiif_file.path
                        iiif_file_b.primary_witness = iiif_file.primary_witness
                        iiif_file_b.basename = iiif_file.basename
                        iiif_file_b.extension = iiif_file.extension
                        iiif_file_b.byte_size = iiif_file.byte_size
                        iiif_file_b.description = iiif_file.description
                        iiif_file_b.provenance_type = iiif_file.provenance_type
                        iiif_file_b.provenance_id = iiif_file.provenance_id
                        iiif_file_b.height = iiif_file.height
                        iiif_file_b.iiif_info = deepcopy(iiif_file.iiif_info)

                        iiif_file_b.iiif_info['fixed_region'] = {
                            'x': threshold,
                            'y': 0,
                            'w': original_width - threshold,
                            'h': iiif_file_b.height
                        }
                        iiif_file_b.width = original_width - threshold
                        job.content.pages[str(ref_no + 1)].files[iiif_file_b.key] = iiif_file_b

                    else:
                        job.content.pages[str(ref_no)].files[iiif_file.key] = iiif_file

            job.set_status('running', percent_complete=int((ref_no / num_pages) * 100))
            ref_no += 1
            if split_images:
                ref_no += 1

        job.content.save()

    if unzip_path and os.path.exists(unzip_path):
        shutil.rmtree(unzip_path)

    job.complete(status='complete')


def unset_primary(doc, file_type):
    page_keys = list(doc.pages.keys())
    for page_key in page_keys:
        file_keys = list(doc.pages[page_key].files.keys())
        for file_key in file_keys:
            if doc.pages[page_key].files[file_key].primary_witness and file_type.lower() in doc.pages[page_key].files[file_key].description.lower():
                doc.pages[page_key].files[file_key].primary_witness = False


def process_page_file(doc, ref_no, label, job_id, primary_witness, image=None, text=None, prov_type="PDF Page Extraction Job"):
    extension = None
    description = None

    if image:
        extension = "png"
        description = "PNG Image"
    if text:
        extension = "txt"
        description = "Plain Text"

    if extension and description:
        page_path = doc.pages[ref_no]._make_path(doc.path)
        path = "{page_path}/{file_label}_{ref_no}.{extension}".format(
            page_path=page_path,
            file_label=label,
            ref_no=ref_no,
            extension=extension
        )
        label_version = 1
        while os.path.exists(path):
            label += str(label_version)
            label_version += 1
            path = "{page_path}/{file_label}_{ref_no}.{extension}".format(
                page_path=page_path,
                file_label=label,
                ref_no=ref_no,
                extension=extension
            )

        if image:
            image.save(path)
        elif text:
            with open(path, 'w', encoding='utf-8') as txt_out:
                txt_out.write(text)

        file_obj = File.process(
            path,
            desc=description,
            prov_type=prov_type,
            prov_id=job_id,
            primary=primary_witness
        )
        doc.pages[ref_no].files[file_obj.key] = file_obj


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

    for slug in page_file_collections.keys():
        cypher = '''
            MATCH (d:Document { uri: $doc_uri })
            MERGE (d) -[:hasPageFileCollection]-> (pfc:_PageFileCollection { uri: $pfc_uri })
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
        run_neo(cypher, params)

    job.complete("complete")
