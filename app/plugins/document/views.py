import re
from django.shortcuts import render, HttpResponse, redirect
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
from corpus import *
from .content import Document, PageSet, reset_page_extraction
from manager.utilities import _get_context, get_scholar_corpus, _contains, _clean
from manager.tasks import run_job
from natsort import natsorted
from rest_framework.decorators import api_view
from google.cloud import vision
from bs4 import BeautifulSoup


@login_required
def document(request, corpus_id, document_id):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])

    if corpus:
        if (response['scholar'].is_admin or role == 'Editor') and request.method == 'POST':
            document = corpus.get_content('Document', document_id)

            # HANDLE FILE UPLOADS
            if 'filepond' in request.FILES:
                filename = re.sub(r'[^a-zA-Z0-9\\.\\-]', '_', request.FILES['filepond'].name)
                upload_path = "{0}/temporary_uploads".format(document.path)
                file_path = "{0}/{1}".format(upload_path, filename)

                if not os.path.exists(upload_path):
                    os.makedirs(upload_path)

                with open(file_path, 'wb+') as destination:
                    for chunk in request.FILES['filepond'].chunks():
                        destination.write(chunk)

                return HttpResponse(ObjectId(), content_type='text/plain')

            # HANDLE IMPORT PAGES FORM SUBMISSION
            elif _contains(request.POST, ['import-pages-type', 'import-pages-files']):
                files_to_process = []
                import_type = _clean(request.POST, 'import-pages-type')
                import_files = json.loads(request.POST['import-pages-files'])

                upload_path = "{0}/temporary_uploads".format(document.path)
                for import_file in import_files:
                    import_file_path = "{0}/{1}".format(upload_path, import_file)
                    if os.path.exists(import_file_path):
                        files_to_process.append(import_file_path)

                if files_to_process:
                    if import_type == 'pdf':
                        image_dpi = _clean(request.POST, 'import-pages-image-dpi')
                        image_split = _clean(request.POST, 'import-pages-split')
                        primary_witness = _clean(request.POST, 'import-pages-primary')
                        extract_text = _clean(request.POST, 'import-pages-extract-text')

                        if '.pdf' in files_to_process[0].lower():
                            pdf_file_path = files_to_process[0]
                            pdf_file_basename = os.path.basename(pdf_file_path)

                            doc_files_path = "{0}/files".format(document.path)
                            new_pdf_path = "{0}/{1}".format(doc_files_path, pdf_file_basename)

                            os.rename(pdf_file_path, new_pdf_path)
                            pdf_file_path = new_pdf_path
                            document.save_file(File.process(
                                pdf_file_path,
                                "PDF File",
                                "User Import",
                                response['scholar']['username'],
                                False
                            ))

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
                else:
                    response['errors'].append("Error locating files to import.")

            # HANDLE IMPORT DOCUMENT FILES FORM SUBMISSION
            elif 'import-document-files' in request.POST:
                import_files = json.loads(request.POST['import-document-files'])

                upload_path = document.path + '/files'
                for import_file in import_files:
                    import_file_path = "{0}{1}".format(upload_path, import_file)
                    if os.path.exists(import_file_path):
                        extension = import_file.split('.')[-1]
                        document.save_file(File.process(
                            import_file_path,
                            extension.upper() + " File",
                            "User Import",
                            response['scholar']['username'],
                            False
                        ))

            # HANDLE JOB RETRIES
            elif _contains(request.POST, ['retry-job-id']):
                retry_job_id = _clean(request.POST, 'retry-job-id')
                for completed_task in document.completed_tasks:
                    if completed_task.job_id == retry_job_id:
                        job = Job.setup_retry_for_completed_task(corpus_id, document_id, completed_task)
                        document.modify(pull__completed_tasks=completed_task)
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
                    job.corpus_id = corpus_id
                    job.content_type = 'Document'
                    job.content_id = document_id
                    job.task_id = str(task.id)
                    job.scholar_id = str(response['scholar'].id)
                    job.jobsite_id = str(jobsite.id)
                    job.status = "preparing"
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
            'corpus_id': corpus_id,
            'role': role,
            'document_id': document_id,
            'response': response,
        }
    )


@login_required
def edit_xml(request, corpus_id, document_id):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])
    xml_file = None

    if corpus and role in ['Editor', 'Admin']:
        if 'path' in request.GET:
            path = _clean(request.GET, 'path')
            if path.startswith('/corpora') and '../' not in path and path.lower().split('.')[-1] in ['xml', 'rdf', 'hocr']:
                xml_file = "/get-file?path={0}".format(path)

        elif 'use_tei_skeleton' in request.GET:
            xml_file = "/corpus/{0}/Document/{1}/tei-skeleton".format(corpus_id, document_id)

        elif 'pageset' in request.GET:
            pageset = _clean(request.GET, 'pageset')
            xml_file = "/corpus/{0}/Document/{1}/tei-skeleton?pageset={2}".format(corpus_id, document_id, pageset)

        return render(
            request,
            'edit_xml.html',
            {
                'response': response,
                'xml_file': xml_file,
            }
        )
    else:
        raise Http404("You are not authorized to view this page.")


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
                    if ocr_file.lower().endswith('.object'):
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

        return render(
            request,
            'draw_regions.html',
            {
                'response': response,
                'image_file': image_file.to_dict(parent_uri="/corpus/{0}/Document/{1}/page/{2}".format(
                    corpus_id,
                    document_id,
                    ref_no
                )),
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
                    if ocr_file.lower().endswith('.object'):
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
                content_type=template_format.mime_type
            )
    else:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")


def get_document_page_file_collections(scholar, corpus_id, document_id, pfc_slug=None):
    page_file_collections = {}
    corpus, role = get_scholar_corpus(corpus_id, scholar, only=['id'])
    if corpus:
        if pfc_slug:
            pfc = Document.get_page_file_collection(corpus_id, document_id, pfc_slug)
            if pfc:
                page_file_collections[pfc_slug] = pfc
        else:
            document = corpus.get_content('Document', document_id)
            if document:
                page_file_collections = document.page_file_collections
    return page_file_collections


def get_page_regions(ocr_file, ocr_type):
    regions = []

    if os.path.exists(ocr_file):
        if ocr_type == 'GCV':
            gcv_obj = vision.types.TextAnnotation()
            with open(ocr_file, 'rb') as gcv_in:
                gcv_obj.ParseFromString(gcv_in.read())

            page = gcv_obj.pages[0]
            for block in page.blocks:
                lowest_x = min([vertice.x for vertice in block.bounding_box.vertices])
                lowest_y = min([vertice.y for vertice in block.bounding_box.vertices])
                highest_x = max([vertice.x for vertice in block.bounding_box.vertices])
                highest_y = max([vertice.y for vertice in block.bounding_box.vertices])

                regions.append({
                    'x': lowest_x,
                    'y': lowest_y,
                    'height': highest_y - lowest_y,
                    'width': highest_x - lowest_x
                })
        elif ocr_type == 'HOCR':
            with open(ocr_file, 'rb') as hocr_in:
                hocr_obj = BeautifulSoup(hocr_in.read(), 'html.parser')
            blocks = hocr_obj.find_all("div", class_="ocr_carea")
            for block in blocks:
                bbox_parts = block.attrs['title'].split()
                regions.append({
                    'x': int(bbox_parts[1]),
                    'y': int(bbox_parts[2]),
                    'width': int(bbox_parts[3]) - int(bbox_parts[1]),
                    'height': int(bbox_parts[4]) - int(bbox_parts[2])
                })

    return regions


def get_page_region_content(ocr_file, ocr_type, x, y, width, height):
    content = ""

    if os.path.exists(ocr_file):
        if ocr_type == 'GCV':
            gcv_obj = vision.types.TextAnnotation()
            breaks = vision.enums.TextAnnotation.DetectedBreak.BreakType
            with open(ocr_file, 'rb') as gcv_in:
                gcv_obj.ParseFromString(gcv_in.read())

                for page in gcv_obj.pages:
                    for block in page.blocks:
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                for symbol in word.symbols:
                                    lowest_x = min([vertice.x for vertice in symbol.bounding_box.vertices])
                                    lowest_y = min([vertice.y for vertice in symbol.bounding_box.vertices])
                                    highest_x = max([vertice.x for vertice in symbol.bounding_box.vertices])
                                    highest_y = max([vertice.y for vertice in symbol.bounding_box.vertices])

                                    if lowest_x >= x and \
                                            lowest_y >= y and \
                                            highest_x <= (x + width) and \
                                            highest_y <= (y + height):

                                        content += symbol.text
                                        if symbol.property.detected_break.type == breaks.SPACE:
                                            content += ' '
                                        elif symbol.property.detected_break.type == breaks.EOL_SURE_SPACE:
                                            content += '\n'
                                        elif symbol.property.detected_break.type == breaks.LINE_BREAK:
                                            content += '\n'
                                        elif symbol.property.detected_break.type == breaks.HYPHEN:
                                            content += '-\n'
        elif ocr_type == 'HOCR':
            with open(ocr_file, 'rb') as hocr_in:
                hocr_obj = BeautifulSoup(hocr_in.read(), 'html.parser')
            words = hocr_obj.find_all("span", class_="ocrx_word")
            for word in words:
                bbox_parts = word.attrs['title'].replace(';', '').split()
                if int(bbox_parts[1]) >= x and \
                        int(bbox_parts[2]) >= y and \
                        int(bbox_parts[3]) <= (x + width) and \
                        int(bbox_parts[4]) <= (y + height):
                    content += word.text + ' '
    return content.strip()