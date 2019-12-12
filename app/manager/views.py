import logging
import json
import mimetypes
from django.shortcuts import render, redirect, HttpResponse
from django.http import Http404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.template import Template, Context
from html import unescape
from math import ceil
from corpus import *
from cms import ContentType, TemplateFormat, DEFAULT_TEMPLATE_FORMATS
from .tasks import *
from .utilities import _get_context, _clean, _contains, get_corpus_search_results, \
    get_scholar_corpora, get_scholar_corpus, get_document, \
    get_jobsites, get_tasks, get_document_page_file_collections, \
    reset_page_extraction, get_page_regions, get_page_region_content, get_file
from rest_framework.decorators import api_view 
from rest_framework.authtoken.models import Token


@login_required
def corpora(request):
    response = _get_context(request)

    if response['scholar'].is_admin and request.method == 'POST' and 'new-corpus-name' in request.POST:
        c_name = unescape(_clean(request.POST, 'new-corpus-name'))
        c_desc = unescape(_clean(request.POST, 'new-corpus-desc'))
        c_open = unescape(_clean(request.POST, 'new-corpus-open'))

        c = Corpus()
        c.name = c_name
        c.description = c_desc
        c.open_access = True if c_open else False
        c.save()
        sleep(4)

    return render(
        request,
        'index.html',
        {
            'response': response
        }
    )


@login_required
def corpus(request, corpus_id):
    response = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, response['scholar'])
    if corpus:
        if request.method == 'POST' and _contains(request.POST, [
            'new-document-title',
            'new-document-author',
            'new-document-pubdate',
            'new-document-work',
            'new-document-manifestation'
        ]):
            try:
                new_doc = Document()
                new_doc.corpus = corpus
                new_doc.title = unescape(_clean(request.POST, 'new-document-title'))
                new_doc.author = unescape(_clean(request.POST, 'new-document-author'))
                new_doc.pub_date = _clean(request.POST, 'new-document-pubdate')
                new_doc.work = unescape(_clean(request.POST, 'new-document-work'))
                new_doc.manifestation = unescape(_clean(request.POST, 'new-document-manifestation'))
                new_doc.save()
            except:
                print(traceback.format_exc())
                response['errors'].append("Unable to save document!")

        elif request.method == 'POST' and 'settings' in request.POST:
            try:
                settings = json.loads(request.POST['settings'])
            except:
                response['errors'].append("Unable to parse field settings!")
                logging.error(traceback.format_exc())
                settings = []

            if not response['errors'] and settings:
                existing_settings = deepcopy(corpus.field_settings)
                index_rebuild_required = False

                # determine whether change requires rebuild of Elasticsearch index...
                for field in settings.keys():
                    if field in existing_settings:
                        if existing_settings[field]['display'] != settings[field]['display'] or \
                                existing_settings[field]['search'] != settings[field]['search'] or \
                                existing_settings[field]['sort'] != settings[field]['sort'] or \
                                (settings[field]['display'] or settings[field]['search'] or settings[field]['sort']) and (existing_settings[field].get('type', 'keyword') != settings[field].get('type', 'keyword')):
                            index_rebuild_required = True
                            break
                    else:
                        index_rebuild_required = True
                        break

                corpus.modify(set__field_settings=settings)

                if index_rebuild_required:
                    response['messages'].append("The search index for your corpus is being rebuilt. Depending on the size of your corpus, this may take awhile, and until this process completes, searching/sorting/filtering your corpus may not work properly.")
                    rebuild_corpus_index(corpus_id)

                return redirect('/corpus/{0}/?&msg=Document field settings saved.'.format(str(corpus_id)))

        # HANDLE CONTENT_TYPE/FIELD ACTIONS THAT REQUIRE CONFIRMATION
        elif request.method == 'POST' and _contains(request.POST, [
            'content_type',
            'field',
            'action'
        ]):
            action_content_type = _clean(request.POST, 'content_type')
            action_field_name = _clean(request.POST, 'field')
            action = _clean(request.POST, 'action')

            if action_content_type:
                content_type = ContentType.objects(corpus=corpus_id, name=action_content_type)[0]

                # content type actions
                if not action_field_name:
                    if action == 'delete':
                        content_type.delete()

                # field actions
                else:
                    if action == 'delete':
                        content_type.delete_field(action_field_name)
                    elif action.startswith('shift_'):
                        field_index = -1
                        new_field_index = -1
                        for index in range(0, len(content_type.fields)):
                            if content_type.fields[index].name == action_field_name:
                                field_index = index

                        if field_index > -1:
                            if action.endswith("_up") and field_index > 0:
                                new_field_index = field_index - 1
                            elif action.endswith("_down") and field_index < len(content_type.fields) - 1:
                                new_field_index = field_index + 1

                        if field_index > -1 and new_field_index > -1:
                            swap_field = content_type.fields[new_field_index]
                            content_type.fields[new_field_index] = content_type.fields[field_index]
                            content_type.fields[field_index] = swap_field
                            content_type.save()

        # HANDLE THE CREATION OF NEW TEMPLATE FORMATS
        elif request.method == 'POST' and _contains(request.POST, ['new-format-label', 'new-format-extension']):
            new_format_label = _clean(request.POST, 'new-format-label')
            new_format_extension = _clean(request.POST, 'new-format-extension')

            if new_format_label \
                    and new_format_extension \
                    and new_format_extension not in [default['extension'] for default in DEFAULT_TEMPLATE_FORMATS]:
                new_format = TemplateFormat()
                new_format.corpus = corpus
                new_format.label = new_format_label
                new_format.extension = new_format_extension
                new_format.ace_editor_mode = 'django'
                new_format.save()

    return render(
        request,
        'corpus.html',
        {
            'corpus_id': corpus_id,
            'response': response,
        }
    )


@login_required
def document(request, corpus_id, document_id):
    response = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, response['scholar'])
    local_jobsite = JobSite.objects(name='Local')[0]
    document = get_document(response['scholar'], corpus_id, document_id)
    core_fields = [
        'title',
        'author',
        'pub_date',
        'work',
        'manifestation',
        'path'
    ]

    # HANDLE FILE UPLOADS
    if 'filepond' in request.FILES:
        filename = re.sub(r'[^a-zA-Z0-9\\.\\-]', '_', request.FILES['filepond'].name)
        print(filename)
        upload_path = "{0}/temporary_uploads".format(document.path)
        file_path = "{0}/{1}".format(upload_path, filename)

        if not os.path.exists(upload_path):
            os.makedirs(upload_path)

        with open(file_path, 'wb+') as destination:
            for chunk in request.FILES['filepond'].chunks():
                destination.write(chunk)

        return HttpResponse(ObjectId(), content_type='text/plain')

    # HANDLE IMPORT PAGES FORM SUBMISSION
    elif request.method == 'POST' and _contains(request.POST, ['import-pages-type', 'import-pages-files']):
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
                    document.save_file(process_corpus_file(
                        pdf_file_path,
                        "PDF File",
                        "User Import",
                        response['scholar']['username'],
                        False
                    ))

                    # Get Local JobSite, PDF Import Task, and setup Job
                    local_jobsite = JobSite.objects(name='Local')[0]
                    import_task_id = local_jobsite.task_registry['Import Document Pages from PDF']['task_id']
                    import_task = Task.objects(id=import_task_id)[0]

                    import_job = Job()
                    import_job.corpus_id = corpus_id
                    import_job.document_id = document_id
                    import_job.task_id = str(import_task.id)
                    import_job.scholar_id = str(response['scholar'].id)
                    import_job.jobsite_id = str(local_jobsite.id)
                    import_job.status = "preparing"
                    import_job.configuration = import_task.configuration
                    import_job.configuration['parameters']['pdf_file']['value'] = pdf_file_path
                    import_job.configuration['parameters']['image_dpi']['value'] = image_dpi
                    import_job.configuration['parameters']['split_images']['value'] = image_split
                    import_job.configuration['parameters']['extract_text']['value'] = extract_text
                    import_job.configuration['parameters']['primary_witness']['value'] = primary_witness
                    import_job.save()
                    run_job(import_job.id)

        else:
            response['errors'].append("Error locating files to import.")

    # HANDLE JOB RETRIES
    elif request.method == 'POST' and _contains(request.POST, ['retry-job-id']):
        retry_job_id = _clean(request.POST, 'retry-job-id')
        for completed_task in document.completed_tasks:
            if completed_task.job_id == retry_job_id:
                job = Job.setup_retry_for_completed_task(corpus_id, document_id, completed_task)
                document.modify(pull__completed_tasks=completed_task)
                run_job(job.id)

    # HANDLE PAGESET CREATION
    elif request.method == 'POST' and _contains(request.POST, ['pageset-name', 'pageset-start', 'pageset-end']):
        ps_name = slugify(_clean(request.POST, 'pageset-name')).replace('__', '_')
        ps_start = _clean(request.POST, 'pageset-start')
        ps_end = _clean(request.POST, 'pageset-end')

        if ps_name not in document.page_sets:
            if ps_start in document.pages and ps_end in document.pages:
                page_ref_nos = natsorted(document.pages.keys())
                ps = PageSet()
                start_found = False
                for ref_no in page_ref_nos:
                    if ref_no == ps_start:
                        start_found = True
                    if start_found:
                        ps.ref_nos.append(ref_no)
                        if ref_no == ps_end:
                            break
                document.modify(**{'set__page_sets__{0}'.format(ps_name): ps})
            else:
                response['errors'].append("Start and end pages must be existing page numbers!")
        else:
            response['errors'].append("A page set with that name already exists!")

    # HANDLE RESET PAGES BUTTON
    elif request.method == 'GET' and 'reset-pages' in request.GET:
        if response['scholar'].is_admin:
            reset_page_extraction(corpus_id, document_id)
            return redirect('/corpus/{0}/document/{1}/'.format(corpus_id, document_id))

    # HANDLE TASK FORM SUBMISSION
    elif request.method == 'POST' and _contains(request.POST, ['jobsite', 'task']):
        # Get Local JobSite, PDF Import Task, and setup Job
        jobsite = JobSite.objects(id=_clean(request.POST, 'jobsite'))[0]
        task = Task.objects(id=_clean(request.POST, 'task'))[0]
        task_parameters = [key for key in task.configuration['parameters'].keys()]
        if _contains(request.POST, task_parameters):
            job = Job()
            job.corpus_id = corpus_id
            job.document_id = document_id
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

    elif request.method == 'POST' and _contains(request.POST, ['consolidate-files', 'collection']):
        collection_key = _clean(request.POST, 'collection')
        consolidated_file = "{0}/files/{1}_consolidated.txt".format(
            document.path,
            slugify(collection_key)
        )

        consolidated_text = ''
        for file in document.page_file_collections[collection_key]['files']:
            if os.path.exists(file['path']):
                with open(file['path'], 'r', encoding="utf-8") as fin:
                    consolidated_text += fin.read() + '\n'

        with open(consolidated_file, 'w', encoding='utf-8') as fout:
            fout.write(consolidated_text)

        document.save_file(process_corpus_file(
            consolidated_file,
            "Plain Text File",
            "User Created",
            response['scholar']['username'],
            False
        ))

        response['messages'].append("Consolidated file created.")

    else:
        # if 'corpora_document_checked' not in document.kvp:
        check_document(corpus_id, document_id)

        # elif request.method == 'POST' and 'check' in request.POST:
        #    check_document(corpus_id, document_id)
        #    response['messages'].append('Document check submitted.')

    return render(
        request,
        'document.html',
        {
            'corpus': corpus,
            'document': document,
            'core_fields': core_fields,
            'response': response,
            'local_jobsite': str(local_jobsite.id)
        }
    )


@login_required
def edit_xml(request, corpus_id, document_id):
    response = _get_context(request)
    xml_file = None

    if 'path' in request.GET:
        path = _clean(request.GET, 'path')
        if path.startswith('/corpora') and '../' not in path and path.lower().split('.')[-1] in ['xml', 'rdf', 'hocr']:
            xml_file = "/get-file?path={0}".format(path)

    elif 'use_tei_skeleton' in request.GET:
        xml_file = "/corpus/{0}/document/{1}/tei-skeleton".format(corpus_id, document_id)

    elif 'pageset' in request.GET:
        pageset = _clean(request.GET, 'pageset')
        xml_file = "/corpus/{0}/document/{1}/tei-skeleton?pageset={2}".format(corpus_id, document_id, pageset)

    return render(
        request,
        'edit_xml.html',
        {
            'response': response,
            'xml_file': xml_file,
        }
    )


@login_required
def tei_skeleton(request, corpus_id, document_id):
    response = _get_context(request)
    document = get_document(response['scholar'], corpus_id, document_id)
    template_string = ""
    template_path = "{0}/templates/tei_skeleton.xml".format(settings.BASE_DIR)
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


@login_required
def draw_page_regions(request, corpus_id, document_id, ref_no):
    response = _get_context(request)
    document = get_document(response['scholar'], corpus_id, document_id)
    image_path = ""
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
                    image_path = file.path
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
            'image_path': image_path,
            'page_regions': page_regions,
            'corpus_id': corpus_id,
            'document_id': document_id,
            'ocr_file': ocr_file,
            'ref_no': ref_no
        }
    )


def scholar(request):
    response = _get_context(request)
    register = False

    if settings.USE_SSL and not response['url'].startswith('https'):
        secure_url = response['url'].replace('http://', 'https://')
        return redirect(secure_url)

    if not response['scholar'] and 'register' in request.GET:
        register = True

    if response['scholar'] and 'logout' in request.GET:
        logout(request)
        return redirect('/scholar?msg=You have successfully logged out.')

    if response['scholar'] and 'gen_token' in request.GET:
        token, created = Token.objects.get_or_create(user=request.user)
        response['scholar'].auth_token = token.key
        response['scholar'].save()
        response = _get_context(request)

    if request.method == 'POST' and _contains(request.POST, ['username', 'password', 'password2', 'fname', 'lname', 'email']):
        username = _clean(request.POST, 'username')
        password = _clean(request.POST, 'password')
        password2 = _clean(request.POST, 'password2')
        fname = _clean(request.POST, 'fname')
        lname = _clean(request.POST, 'lname')
        email = _clean(request.POST, 'email')

        if password and password == password2:
            if not response['scholar']:
                user = User.objects.create_user(
                    username,
                    email,
                    password
                )
                user.first_name = fname
                user.last_name = lname
                user.save()

                response['scholar'] = Scholar()
                response['scholar'].username = username
                response['scholar'].fname = fname
                response['scholar'].lname = lname
                response['scholar'].email = email

                token, created = Token.objects.get_or_create(user=user)
                response['scholar'].auth_token = token.key
                response['scholar'].save()

                return redirect("/scholar?msg=You have successfully registered. Please login below.")
            else:
                response['scholar'].fname = fname
                response['scholar'].lname = lname
                response['scholar'].email = email
                response['scholar'].save()

                user = User.objects.get(username=username)
                user.set_password(password)
                user.save()

                response['messages'].append("Your account settings have been saved successfully.")
        else:
            response['errors'].append('You must provide a password, and passwords must match!')

    elif request.method == 'POST' and _contains(request.POST, ['username', 'password']):
        username = _clean(request.POST, 'username')
        password = _clean(request.POST, 'password')
        user = authenticate(username=username, password=password)
        if user:
            if user.is_active:
                login(request, user)

                if 'next' in request.GET:
                    return redirect(request.GET['next'])
                else:
                    return redirect("/")
            else:
                response['errors'].append('Account disabled!')
        else:
            response['errors'].append('Invalid credentials provided!')

    return render(
        request,
        'scholar.html',
        {
            'response': response,
            'register': register
        }
    )


@api_view(['GET'])
def api_search(request, corpus_id=None, document_id=None):
    response = _get_context(request)
    if response['scholar']:
        search_results = get_corpus_search_results(request, response['scholar'], corpus_id, document_id)
        return HttpResponse(
            json.dumps(search_results),
            content_type='application/json'
        )
    raise Http404("Search not completed.")


@api_view(['GET'])
def api_corpora(request):
    response = _get_context(request)
    corpora = get_corpus_search_results(request, response['scholar'])

    return HttpResponse(
        json.dumps(corpora),
        content_type='application/json'
    )


@api_view(['GET'])
def api_corpus(request, corpus_id):
    response = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, response['scholar'])

    return HttpResponse(
        corpus.to_json(),
        content_type='application/json'
    )


@api_view(['GET'])
def api_documents(request, corpus_id):
    response = _get_context(request)
    documents = get_corpus_search_results(request, response['scholar'], corpus_id)

    return HttpResponse(
        json.dumps(documents),
        content_type='application/json'
    )


@api_view(['GET'])
def api_document(request, corpus_id, document_id):
    response = _get_context(request)
    document = get_document(response['scholar'], corpus_id, document_id)

    return HttpResponse(
        document.to_json(),
        content_type='application/json'
    )


@api_view(['GET'])
def api_jobsites(request):
    response = _get_context(request)
    jobsites = get_jobsites(response['scholar'])

    return HttpResponse(
        jobsites.to_json(),
        content_type='application/json'
    )


@api_view(['GET'])
def api_tasks(request):
    response = _get_context(request)
    tasks = get_tasks(response['scholar'])

    return HttpResponse(
        tasks.to_json(),
        content_type='application/json'
    )


@api_view(['GET'])
def api_corpus_jobs(request, corpus_id):
    jobs = Job.get_jobs(corpus_id=corpus_id)
    payload = []
    for job in jobs:
        payload.append(job.to_dict())

    return HttpResponse(
        json.dumps(payload),
        content_type='application/json'
    )


@api_view(['GET'])
def api_document_jobs(request, corpus_id, document_id):
    jobs = Job.get_jobs(corpus_id=corpus_id, document_id=document_id)
    payload = []
    for job in jobs:
        payload.append(job.to_dict())

    return HttpResponse(
        json.dumps(payload),
        content_type='application/json'
    )


@api_view(['GET', 'POST'])
def api_document_kvp(request, corpus_id, document_id, key):
    value = ''
    response = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, response['scholar'])
    if corpus:
        document = corpus.get_document(document_id, only=['kvp__{0}'.format(key)])

        if request.method == 'GET' and document:
            value = document.kvp.get(key, '')
        elif request.method == 'POST' and document and 'value' in request.POST:
            value = _clean(request.POST, 'value')
            document.update(**{'set__kvp__{0}'.format(key): value})

    return HttpResponse(
        json.dumps(value),
        content_type='application/json'
    )


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
    document = get_document(response['scholar'], corpus_id, document_id)
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


@login_required
def get_document_iiif_manifest(request, corpus_id, document_id, collection=None, pageset=None):
    response = _get_context(request)
    iiif_template_path = "{0}/templates/iiif_manifest.json".format(settings.BASE_DIR)
    document = get_document(response['scholar'], corpus_id, document_id)
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
    return HttpResponse("Not yet implemented.")


@login_required
def get_document_file(request, corpus_id, document_id, file_key, ref_no=None):
    response = _get_context(request)
    file = get_file(response['scholar'], corpus_id, document_id, file_key, ref_no)

    if file:
        mime_type, encoding = mimetypes.guess_type(file.path)
        response = HttpResponse(content_type=mime_type)
        response['X-Accel-Redirect'] = "/files/{0}".format(file.path.replace('/corpora/', ''))
        return response
    raise Http404("File not found.")


@login_required
def get_document_image(request,
        corpus_id,
        document_id,
        image_key,
        region="full",
        size="full",
        rotation="0",
        quality="default",
        format="png",
        ref_no=None):
    response = _get_context(request)
    file = get_file(response['scholar'], corpus_id, document_id, image_key, ref_no)
    if file:
        mime_type, encoding = mimetypes.guess_type("file.{0}".format(format))
        response = HttpResponse(content_type=mime_type)
        response['X-Accel-Redirect'] = "/media/{identifier}/{region}/{size}/{rotation}/{quality}.{format}".format(
            identifier=file.path[1:].replace('/', '$!$'),
            region=region,
            size=size,
            rotation=rotation,
            quality=quality,
            format=format
        )
        return response
    raise Http404("Image not found.")

