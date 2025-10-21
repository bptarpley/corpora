import os
import json
from django.conf import settings
from django.shortcuts import render, HttpResponse, redirect
from django.http import Http404
from django.template import Template, Context
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
from .content import PageSet
from manager.utilities import _get_context, get_scholar_corpus, _contains, _clean, scholar_has_privilege
from manager.tasks import run_job
from manager.views import view_content
from natsort import natsorted
from rest_framework.decorators import api_view
from bs4 import BeautifulSoup
from django_drf_filepond.models import TemporaryUpload
from corpus import (
    Job, JobSite, Task,
    File
)


@login_required
def document(request, corpus_id, document_id):
    if 'popup' in request.GET:
        return view_content(request, corpus_id, 'Document', document_id)

    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])

    if corpus:
        if scholar_has_privilege('Contributor', role) and request.method == 'POST':

            # HANDLE TRANSCRIPTION FORM
            if _contains(request.POST, ['trans-project',
                                        'trans-name',
                                        'trans-pageset',
                                        'trans-image-pfc',
                                        'trans-ocr-pfc',
                                        'trans-level',
                                        'trans-plain-text']):

                trans_project_id = _clean(request.POST, 'trans-project')
                trans_plain_text = _clean(request.POST, 'trans-plain-text')

                if scholar_has_privilege('Editor', role) and trans_project_id == 'new':
                    document = corpus.get_content('Document', document_id)

                    # handle plain text transcription lines
                    if trans_plain_text == 'none':
                        trans_plain_text = None
                    transcription_lines = []
                    if trans_plain_text:
                        pt_file_path = document.files[trans_plain_text].path
                        if os.path.exists(pt_file_path):
                            with open(pt_file_path, 'r', encoding='utf-8') as pt_in:
                                pt_lines = pt_in.readlines()
                                transcription_lines = [pt_line.strip() for pt_line in pt_lines]

                    trans_project = corpus.get_content('TranscriptionProject')
                    trans_project.name = _clean(request.POST, 'trans-name')
                    trans_project.document = document.id
                    trans_project.pageset = _clean(request.POST, 'trans-pageset')
                    trans_project.image_pfc = _clean(request.POST, 'trans-image-pfc')
                    trans_project.ocr_pfc = _clean(request.POST, 'trans-ocr-pfc')
                    trans_project.transcription_level = _clean(request.POST, 'trans-level')
                    trans_project.transcription_text = transcription_lines
                    trans_project.transcription_cursor = 0
                    trans_project.allow_markup = 'trans-markup' in request.POST
                    trans_project.save()
                    trans_project_id = str(trans_project.id)

                return redirect("/corpus/{0}/Document/{1}/transcribe/{2}/".format(
                    corpus_id,
                    document_id,
                    trans_project_id
                ))

            if scholar_has_privilege('Editor', role):
                document = corpus.get_content('Document', document_id)

                # HANDLE IMPORT PAGES FORM SUBMISSION
                if _contains(request.POST, ['import-pages-type', 'import-pages-files']):
                    import_type = _clean(request.POST, 'import-pages-type')
                    import_source = _clean(request.POST, 'import-pages-pdf-source')
                    existing_file_key = _clean(request.POST, 'import-pages-pdf-existing-file', None)
                    import_files = json.loads(request.POST['import-pages-files'])

                    image_split = _clean(request.POST, 'import-pages-split')
                    primary_witness = _clean(request.POST, 'import-pages-primary')

                    if import_type == 'iiif' and 'import-pages-iiif-ids' in request.POST:
                        iiif_ids = _clean(request.POST, 'import-pages-iiif-ids')
                        iiif_ids = [iiif_id.strip() for iiif_id in iiif_ids.split('\n')]

                        # queue and run job
                        job_id = corpus.queue_local_job(
                            content_type='Document',
                            content_id=document_id,
                            task_name='Import Document Pages from Images',
                            scholar_id=response['scholar'].id,
                            parameters={
                                'import_files_json': json.dumps(iiif_ids),
                                'split_images': image_split,
                                'primary_witness': primary_witness,
                                'images_type': 'iiif'
                            }
                        )
                        run_job(job_id)

                        response['messages'].append('Pages imported via IIIF')

                    elif import_source == 'upload':
                        if import_files:

                            if import_type == 'pdf':
                                image_dpi = _clean(request.POST, 'import-pages-image-dpi')
                                extract_text = _clean(request.POST, 'import-pages-extract-text')

                                pdf_file_path = process_document_file_upload(document, import_files[0], response['scholar']['username'])

                                if pdf_file_path and '.pdf' in pdf_file_path.lower():

                                    # Get Local JobSite, PDF Import Task, and setup Job
                                    job_id = corpus.queue_local_job(
                                        content_type='Document',
                                        content_id=document_id,
                                        task_name='Import Document Pages from PDF',
                                        scholar_id=response['scholar'].id,
                                        parameters={
                                            'pdf_file': pdf_file_path,
                                            'image_dpi': image_dpi,
                                            'split_images': image_split,
                                            'extract_text': extract_text,
                                            'primary_witness': primary_witness
                                        }
                                    )
                                    run_job(job_id)

                            elif import_type in ['images', 'zip']:
                                # build job params
                                job_params = {
                                    'import_files_json': request.POST['import-pages-files'],
                                    'split_images': image_split,
                                    'primary_witness': primary_witness,
                                    'images_type': 'file'
                                }
                                if import_type == 'zip':
                                    job_params['images_type'] = 'zip'

                                # queue and run job
                                job_id = corpus.queue_local_job(
                                    content_type='Document',
                                    content_id=document_id,
                                    task_name='Import Document Pages from Images',
                                    scholar_id=response['scholar'].id,
                                    parameters=job_params
                                )
                                run_job(job_id)
                        else:
                            response['errors'].append("Error locating files to import.")

                    elif import_source == 'existing' and existing_file_key:
                        image_dpi = _clean(request.POST, 'import-pages-image-dpi')
                        extract_text = _clean(request.POST, 'import-pages-extract-text')

                        # Get Local JobSite, PDF Import Task, and setup Job
                        job_id = corpus.queue_local_job(
                            content_type='Document',
                            content_id=document_id,
                            task_name='Import Document Pages from PDF',
                            scholar_id=response['scholar'].id,
                            parameters={
                                'pdf_file': document.files[existing_file_key].path,
                                'image_dpi': image_dpi,
                                'split_images': image_split,
                                'extract_text': extract_text,
                                'primary_witness': primary_witness
                            }
                        )
                        run_job(job_id)

                # HANDLE IMPORT DOCUMENT FILES FORM SUBMISSION
                elif 'import-document-files' in request.POST:
                    import_files = json.loads(request.POST['import-document-files'])

                    for import_file in import_files:
                        if not process_document_file_upload(document, import_file, response['scholar']['username']):
                            response['errors'].append("A file with this name already exists for this document.")

                # HANDLE JOB RETRIES
                elif _contains(request.POST, ['retry-job-id']):
                    retry_job_id = _clean(request.POST, 'retry-job-id')
                    for completed_task in document.provenance:
                        if completed_task.job_id == retry_job_id:
                            job = Job.setup_retry_for_completed_task(corpus_id, 'Document', document_id, completed_task)
                            document.modify(pull__provenance=completed_task)
                            run_job(job.id)

                # HANDLE PAGESET CREATION
                elif _contains(request.POST, ['pageset-name', 'pageset-start', 'pageset-end']):
                    ps_label = _clean(request.POST, 'pageset-name')
                    ps_key = slugify(ps_label).replace('__', '_')
                    ps_start = _clean(request.POST, 'pageset-start')
                    ps_end = _clean(request.POST, 'pageset-end')

                    if ps_key not in document.page_sets:
                        if ps_start in document.pages and ps_end in document.pages:
                            page_ref_nos = natsorted(document.pages.keys())
                            ps = PageSet()
                            ps.label = ps_label
                            start_found = False
                            for ref_no in page_ref_nos:
                                if ref_no == ps_start:
                                    start_found = True
                                if start_found:
                                    ps.ref_nos.append(ref_no)
                                    if ref_no == ps_end:
                                        break
                            document.modify(**{'set__page_sets__{0}'.format(ps_key): ps})
                        else:
                            response['errors'].append("Start and end pages must be existing page numbers!")
                    else:
                        response['errors'].append("A page set with that name already exists!")

                # HANDLE TASK FORM SUBMISSION
                elif _contains(request.POST, ['jobsite', 'task']):
                    jobsite = JobSite.objects(id=_clean(request.POST, 'jobsite'))[0]
                    task = Task.objects(id=_clean(request.POST, 'task'))[0]
                    task_parameters = [key for key in task.configuration['parameters'].keys()]
                    if _contains(request.POST, task_parameters):
                        job = Job()
                        job.corpus = corpus.id
                        job.content_type = 'Document'
                        job.content_id = document_id
                        job.task_id = str(task.id)
                        job.scholar = response['scholar'].id
                        job.jobsite = jobsite.id
                        job.configuration = task.configuration
                        for parameter in task_parameters:
                            job.configuration['parameters'][parameter]['value'] = _clean(request.POST, parameter)
                        job.save()
                        run_job(job.id)
                        response['messages'].append("Job successfully submitted.")
                    else:
                        response['errors'].append("Please provide values for all task parameters.")

                # HANDLE FILE CONSOLIDATION SUBMISSION
                elif _contains(request.POST, ['consolidate-files', 'collection']):
                    collection_key = _clean(request.POST, 'collection')
                    consolidated_file = "{0}/files/{1}_consolidated.txt".format(
                        document.path,
                        slugify(collection_key)
                    )

                    consolidated_text = ''
                    for ref_no, file in document.page_file_collections[collection_key]['page_files']:
                        if os.path.exists(file['path']):
                            with open(file['path'], 'r', encoding="utf-8") as fin:
                                consolidated_text += fin.read() + '\n'

                    with open(consolidated_file, 'w', encoding='utf-8') as fout:
                        fout.write(consolidated_text)

                    document.save_file(File.process(
                        consolidated_file,
                        "Plain Text File",
                        "User Created",
                        response['scholar']['username'],
                        False
                    ))

                    response['messages'].append("Consolidated file created.")
    else:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")


    return render(
        request,
        'document.html',
        {
            'page_title': 'Document',
            'corpus_id': corpus_id,
            'role': role,
            'document_id': document_id,
            'response': response,
        }
    )


def process_document_file_upload(document, upload_id, username):
    if not document.path:
        document._ct.has_file_field = True
        document._make_path()
        document.save()

    temp_upload = TemporaryUpload.objects.get(upload_id=upload_id)
    temp_upload_path = temp_upload.file.path
    import_file_path = f"{document.path}/files/{temp_upload.upload_name.replace(' ', '_').replace('%20', '_')}"

    if not os.path.exists(import_file_path):
        os.rename(temp_upload_path, import_file_path)

        extension = import_file_path.split('.')[-1]
        document.save_file(File.process(
            import_file_path,
            extension.upper() + " File",
            "User Import",
            username,
            False
        ))

        temp_upload.delete()
        return import_file_path
    return False


@login_required
def tei_skeleton(request, corpus_id, document_id):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])

    if corpus:
        document = corpus.get_content('Document', document_id)
        template_string = ""
        template_path = "{0}/plugins/document/templates/tei_skeleton.xml".format(settings.BASE_DIR)
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as template_in:
                template_string = template_in.read()

        if 'pageset' in request.GET:
            pageset = _clean(request.GET, 'pageset')
            if pageset in document.page_sets:
                document.kvp['_default_pageset'] = pageset

        template = Template(template_string)
        template_context = Context({
            'document': document
        })
        return HttpResponse(
            template.render(template_context),
            content_type="application/xml"
        )
    else:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")


@login_required
def transcribe(request, corpus_id, document_id, project_id, ref_no=None):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])

    if corpus and scholar_has_privilege('Contributor', role):
        document = corpus.get_content('Document', document_id)
        project = corpus.get_content('TranscriptionProject', project_id)
        pageset = None
        image_pfc = None
        image_file = None
        new_image_rotation = None
        ocr_pfc = None
        ocr_file = None
        transcription = None
        new_transcription = False
        region_metadata = ['ID']
        markup = {
            'i': 'fas fa-italic'
        }
        page_regions = []

        if document and project:
            if request.method == 'POST' and 'ref-no' in request.POST:
                ref_no = request.POST['ref-no']

                transcription = corpus.get_content('Transcription', {
                    'project': project.id,
                    'page_refno': ref_no
                }, single_result=True)

                if 'data' in request.POST:
                    trans_data = json.loads(request.POST['data'])
                    transcription.data = json.dumps(trans_data)
                    transcription.save()

                    if 'transcription_cursor' in request.POST:
                        project.transcription_cursor = request.POST['transcription_cursor']
                        project.save()

                    return HttpResponse(status=201)

                if 'rotate-page' in request.POST:
                    new_image_rotation = int(request.POST['rotate-page'])

                if 'reset-page' in request.POST:
                    transcription.delete()

                if 'complete-page' in request.POST:
                    transcription.complete = True
                    transcription.save()
                    return redirect('{0}/transcribe/{1}/'.format(document.uri, project_id))

            if project.pageset != 'all' and project.pageset in document.page_sets:
                pageset = project.pageset

            if project.image_pfc:
                image_pfc = document.get_page_file_collection(project.image_pfc, pageset)

            if project.ocr_pfc:
                ocr_pfc = document.get_page_file_collection(project.ocr_pfc, pageset)

            if not ref_no:
                transcriptions = corpus.get_content(
                    'Transcription',
                    {'project': project.id},
                    only=['page_refno', 'complete']
                )
                if transcriptions:
                    # find the ref_no for the first uncompleted page
                    for ordered_ref_no, page in document.ordered_pages(pageset):
                        trans_found = False
                        for trans in transcriptions:
                            if trans.page_refno == ordered_ref_no and trans.complete:
                                trans_found = True
                                break
                        if not trans_found:
                            break

                    # make sure we entered the for-loop and capture the last ordered_ref_no
                    if 'ordered_ref_no' in locals():
                        ref_no = ordered_ref_no

                # if we still don't have a ref_no, just set it to the first
                if not ref_no:
                    if pageset:
                        ref_no = document.page_sets[pageset].ref_nos[0]
                    else:
                        ref_no = "1"

            if ref_no and ref_no in document.ordered_pages(pageset).ordered_ref_nos:
                if image_pfc and ref_no in image_pfc['page_files']:
                    image_file = image_pfc['page_files'][ref_no]

                    # handle image rotation if necessary
                    if new_image_rotation is not None:
                        if ref_no in document.pages:
                            if image_file['key'] in document.pages[ref_no].files:
                                modified_file = document.pages[ref_no].files[image_file['key']]
                                if modified_file.iiif_info:
                                    modified_file.iiif_info['fixed_rotation'] = new_image_rotation
                                    document.save_page_file(ref_no, modified_file)
                                    return HttpResponse(status=201)
                        raise Http404("Unable to save image rotation.")

                    transcription = corpus.get_content('Transcription', {
                        'project': project.id,
                        'page_refno': ref_no
                    }, single_result=True)

                    if not transcription:
                        new_transcription = True
                        transcription = corpus.get_content('Transcription')
                        transcription.project = project.id
                        transcription.page_refno = ref_no
                        transcription.data = ''
                        transcription.complete = False
                        transcription.save()
                else:
                    raise Http404("This document page has no relevant image.")

            if transcription:
                if ocr_pfc and ref_no in ocr_pfc['page_files']:
                    ocr_file_obj = ocr_pfc['page_files'][ref_no]
                    if ocr_file_obj and 'path' in ocr_file_obj:
                        ocr_file = ocr_file_obj['path']

                if transcription.data:
                    page_regions = json.loads(transcription.data)
                elif new_transcription:
                    if ocr_file and os.path.exists(ocr_file):
                        ocr_type = 'HOCR'
                        if ocr_file.lower().endswith('.json'):
                            ocr_type = 'GCV'

                        page_regions = get_page_regions(image_file, ocr_file, ocr_type, project.transcription_level)

                    if page_regions:
                        transcription.data = json.dumps(page_regions)
                        transcription.save()

        if image_file and transcription:
            return render(
                request,
                'transcribe.html',
                {
                    'response': response,
                    'project': project,
                    'project_pages': document.ordered_pages(pageset).ordered_ref_nos,
                    'image_file': json.dumps(image_file),
                    'page_regions': json.dumps(page_regions),
                    'corpus': corpus,
                    'document': document,
                    'ocr_file': ocr_file,
                    'ref_no': ref_no,
                    'region_metadata': region_metadata,
                    'markup': markup,
                    'popup': True
                }
            )
        else:
            raise Http404("Corpus does not exist, or you are not authorized to view it.")
    else:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")


@login_required
def draw_page_regions(request, corpus_id, document_id, ref_no):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])

    if corpus and (response['scholar'].is_admin or role == 'Editor'):
        document = corpus.get_content('Document', document_id)
        image_file = None
        page_regions = []
        ocr_file = request.GET.get('ocrfile', None)

        if document and ref_no in document.pages:
            page = document.pages[ref_no]
            if page:
                if ocr_file and os.path.exists(ocr_file):
                    if ocr_file.lower().endswith('.json'):
                        page_regions = get_page_regions(ocr_file, 'GCV')
                    elif ocr_file.lower().endswith('.hocr'):
                        page_regions = get_page_regions(ocr_file, 'HOCR')

                for file_key, file in page.files.items():
                    if 'Image' in file.description and file.primary_witness:
                        image_file = file
                    elif not page_regions and 'GCV TextAnnotation Object' in file.description:
                        ocr_file = file.path
                        page_regions = get_page_regions(file.path, 'GCV')
                    elif not page_regions and 'HOCR' in file.description:
                        ocr_file = file.path
                        page_regions = get_page_regions(file.path, 'HOCR')

        image_dict = image_file.to_dict(parent_uri="/corpus/{0}/Document/{1}/page/{2}".format(
            corpus_id,
            document_id,
            ref_no
        ))

        return render(
            request,
            'draw_regions.html',
            {
                'response': response,
                'image_file': image_dict,
                'page_regions': page_regions,
                'corpus': corpus,
                'document': document,
                'ocr_file': ocr_file,
                'ref_no': ref_no
            }
        )
    else:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")


@api_view(['GET'])
def api_document_page_file_collections(request, corpus_id, document_id, pfc_slug=None):
    response = _get_context(request)
    page_file_collections = get_document_page_file_collections(response['scholar'], corpus_id, document_id, pfc_slug)
    for slug in page_file_collections.keys():
        page_file_collections[slug]['page_files'] = page_file_collections[slug]['page_files'].page_dict

    return HttpResponse(
        json.dumps(page_file_collections),
        content_type='application/json'
    )


@api_view(['GET'])
def api_page_region_content(request, corpus_id, document_id, ref_no, x, y, width, height):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])
    if corpus:
        document = corpus.get_content('Document', document_id)
        content = ""
        ocr_file = request.GET.get('ocrfile', None)

        if document and ref_no in document.pages:
            page = document.pages[ref_no]
            if page:
                if ocr_file and os.path.exists(ocr_file):
                    if ocr_file.lower().endswith('.json'):
                        content = get_page_region_content(ocr_file, 'GCV', x, y, width, height)
                    elif ocr_file.lower().endswith('.hocr'):
                        content = get_page_region_content(ocr_file, 'HOCR', x, y, width, height)

        return HttpResponse(
            json.dumps(content),
            content_type='application/json'
        )
    else:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")


@login_required
def get_document_iiif_manifest(request, corpus_id, document_id, collection=None, pageset=None):
    response = _get_context(request)
    iiif_template_path = "{0}/templates/iiif_manifest.json".format(settings.BASE_DIR)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])
    if corpus:
        document = corpus.get_content('Document', document_id)
        pfcs = get_document_page_file_collections(response['scholar'], corpus_id, document_id, collection)
        canvas_width = request.GET.get('width', '1000')
        canvas_height = request.GET.get('height', '800')
        component = request.GET.get('component', None)
        if not collection:
            for pfc_slug, pfc in pfcs.items():
                if _contains(pfc['label'].lower(), ['primary', 'image']):
                    collection = pfc_slug

        if document and collection in pfcs and os.path.exists(iiif_template_path):
            host = "http{0}://{1}".format('s' if settings.USE_SSL else '', settings.ALLOWED_HOSTS[0])

            with open(iiif_template_path, 'r') as iiif_in:
                iiif_template = iiif_in.read()

            template = Template(iiif_template)
            template_context = Context({
                'host': host,
                'document': document
            })
            return HttpResponse(
                template.render(template_context),
                content_type='application/json'
            )
    else:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")


def get_document_page_file_collections(scholar, corpus_id, document_id, pfc_slug=None):
    page_file_collections = {}
    corpus, role = get_scholar_corpus(corpus_id, scholar, only=['id'])
    document = corpus.get_content('Document', document_id)

    if corpus and document:
        if pfc_slug:
            pfc = document.get_page_file_collection(pfc_slug)
            if pfc:
                page_file_collections[pfc_slug] = pfc
        else:
            page_file_collections = document.page_file_collections
    return page_file_collections


def get_page_regions(image_file, ocr_file, ocr_type, granularity='line'):
    print('getting page regions...')
    regions = []
    size_adjustment_percentage = None

    if 'iiif_info' in image_file and _contains(image_file['iiif_info'], ['width', 'height']):
        image_width = image_file['iiif_info']['width']
        if image_width > 3000:
            size_adjustment_percentage = 3000 / image_width

    if os.path.exists(ocr_file):
        if ocr_type == 'GCV':
            gcv = None
            with open(ocr_file, 'r', encoding='utf-8') as gcv_in:
                gcv = json.load(gcv_in)

            if gcv:
                for page in gcv['pages']:
                    for block in page['blocks']:
                        for paragraph in block['paragraphs']:
                            x_vertices = []
                            y_vertices = []
                            content = ''

                            for word in paragraph['words']:
                                for symbol in word['symbols']:
                                    x_vertices += [vertice['x'] for vertice in symbol['boundingBox']['vertices']]
                                    y_vertices += [vertice['y'] for vertice in symbol['boundingBox']['vertices']]

                                    content += symbol['text']

                                    if 'property' in symbol and 'detectedBreak' in symbol['property'] and 'type' in symbol['property']['detectedBreak']:
                                        detected_break = symbol['property']['detectedBreak']['type']

                                        if detected_break == 'SPACE':
                                            content += ' '
                                        elif detected_break in ['HYPHEN', 'EOL_SURE_SPACE', 'LINE_BREAK']:
                                            if detected_break == 'HYPHEN':
                                                content += '-'

                                            if granularity == 'line':
                                                regions.append(make_gcv_region(x_vertices, y_vertices, content))
                                                x_vertices = []
                                                y_vertices = []
                                                content = ''
                                            else:
                                                content += '\n'

                                    if granularity != 'line':
                                        regions.append(make_gcv_region(x_vertices, y_vertices, content))

        elif ocr_type == 'HOCR':
            with open(ocr_file, 'rb') as hocr_in:
                hocr_obj = BeautifulSoup(hocr_in.read(), 'html.parser')

            blocks = []
            if granularity == 'line':
                blocks = hocr_obj.find_all("span", class_="ocr_line")
            else:
                blocks = hocr_obj.find_all("p", class_="ocr_par")

            for block in blocks:
                title_attr = block.attrs['title']
                bbox_string = title_attr

                if ';' in title_attr:
                    title_parts = title_attr.split(';')
                    for title_part in title_parts:
                        if 'bbox' in title_part:
                            bbox_string = title_part
                            break

                bbox_parts = bbox_string.split()
                content = ''
                words = block.find_all("span", class_="ocrx_word")
                for word in words:
                    content += word.text + ' '
                content = content.strip()

                if content:
                    region = {
                        'x': int(bbox_parts[1]),
                        'y': int(bbox_parts[2]),
                        'width': int(bbox_parts[3]) - int(bbox_parts[1]),
                        'height': int(bbox_parts[4]) - int(bbox_parts[2]),
                        'ocr_content': content.strip()
                    }

                    if size_adjustment_percentage is not None:
                        print('adjusting region...')
                        region['x'] = region['x'] / size_adjustment_percentage
                        region['y'] = region['y'] / size_adjustment_percentage
                        region['width'] = region['width'] / size_adjustment_percentage
                        region['height'] = region['height'] / size_adjustment_percentage

                    regions.append(region)

    return regions


def get_page_region_content(ocr_file, ocr_type, x, y, width, height):
    content = ""
    pixel_margin = 5

    if os.path.exists(ocr_file):
        if ocr_type == 'GCV':
            gcv = None
            with open(ocr_file, 'r', encoding='utf-8') as gcv_in:
                gcv = json.load(gcv_in)

            if gcv:
                for page in gcv['pages']:
                    for block in page['blocks']:
                        for paragraph in block['paragraphs']:
                            for word in paragraph['words']:
                                for symbol in word['symbols']:
                                    lowest_x = min([vertice['x'] for vertice in symbol['boundingBox']['vertices']])
                                    lowest_y = min([vertice['y'] for vertice in symbol['boundingBox']['vertices']])
                                    highest_x = max([vertice['x'] for vertice in symbol['boundingBox']['vertices']])
                                    highest_y = max([vertice['y'] for vertice in symbol['boundingBox']['vertices']])

                                    if lowest_x >= x and \
                                            lowest_y >= y and \
                                            highest_x <= (x + width) and \
                                            highest_y <= (y + height):

                                        content += symbol['text']

                                        if 'property' in symbol and 'detectedBreak' in symbol['property'] and 'type' in symbol['property']['detectedBreak']:
                                            detected_break = symbol['property']['detectedBreak']['type']

                                            if detected_break == 'SPACE':
                                                content += ' '
                                            elif detected_break in ['EOL_SURE_SPACE', 'LINE_BREAK']:
                                                content += '\n'
                                            elif detected_break == 'HYPHEN':
                                                content += '-\n'
        elif ocr_type == 'HOCR':
            with open(ocr_file, 'rb') as hocr_in:
                hocr_obj = BeautifulSoup(hocr_in.read(), 'html.parser')
            words = hocr_obj.find_all("span", class_="ocrx_word")
            for word in words:
                bbox_parts = word.attrs['title'].replace(';', '').split()
                if int(bbox_parts[1]) >= x - pixel_margin and \
                        int(bbox_parts[2]) >= y - pixel_margin and \
                        int(bbox_parts[3]) <= (x + width + pixel_margin) and \
                        int(bbox_parts[4]) <= (y + height + pixel_margin):
                    content += word.text + ' '
    return content.strip()


def make_gcv_region(x_vertices, y_vertices, content):
    lowest_x = min(x_vertices)
    lowest_y = min(y_vertices)
    highest_x = max(x_vertices)
    highest_y = max(y_vertices)

    return {
        'x': lowest_x,
        'y': lowest_y,
        'height': highest_y - lowest_y,
        'width': highest_x - lowest_x,
        'ocr_content': content.strip()
    }
