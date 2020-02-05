import logging
import json
import re
import mimetypes
from django.shortcuts import render, redirect, HttpResponse
from django.http import Http404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from html import unescape
from time import sleep
from corpus import *
from .tasks import *
from .utilities import _get_context, _clean, _contains, get_corpus_search_results, \
    get_scholar_corpora, get_scholar_corpus, parse_uri, \
    get_jobsites, get_tasks
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

        from plugins.document.content import REGISTRY
        for schema in REGISTRY:
            c.save_content_type(schema)

        sleep(4)
        response['messages'].append("{0} corpus successfully created.".format(c.name))

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
        if request.method == 'POST' and 'schema' in request.POST:
            schema = json.loads(request.POST['schema'])
            for ct_schema in schema:
                queued_job_ids = corpus.save_content_type(ct_schema)
                for queued_job_id in queued_job_ids:
                    run_job(queued_job_id)

            response['messages'].append('''
                Content type(s) successfully saved. Due to the setting/unsetting of fields as being in lists, or the 
                changing of label templates, <strong>reindexing of existing content may occur</strong>, which can 
                result in the temporary unavailability of content in lists or searches. All existing content will be 
                made available once reindexing completes.  
            ''')

        # HANDLE CONTENT_TYPE/FIELD ACTIONS THAT REQUIRE CONFIRMATION
        elif request.method == 'POST' and _contains(request.POST, [
            'content_type',
            'field',
            'action'
        ]):
            action_content_type = _clean(request.POST, 'content_type')
            action_field_name = _clean(request.POST, 'field')
            action = _clean(request.POST, 'action')

            if action_content_type in corpus.content_types:

                # content type actions
                if not action_field_name:
                    if action == 'delete':
                        run_job(corpus.queue_local_job(task_name="Delete Content Type", parameters={
                            'content_type': action_content_type,
                        }))

                        response['messages'].append("Content type {0} successfully deleted.".format(action_content_type))

                # field actions
                else:
                    if action == 'delete':
                        run_job(corpus.queue_local_job(task_name="Delete Content Type Field", parameters={
                            'content_type': action_content_type,
                            'field_name': action_field_name
                        }))

                        response['messages'].append("Field {0} successfully deleted from {1}.".format(
                            action_field_name,
                            action_content_type
                        ))
                        
                    elif action.startswith('shift_'):
                        ct = corpus.content_types[action_content_type]
                        field_index = -1
                        new_field_index = -1

                        for index in range(0, len(ct.fields)):
                            if ct.fields[index].name == action_field_name:
                                field_index = index

                        if field_index > -1:
                            if action.endswith("_up") and field_index > 0:
                                new_field_index = field_index - 1
                            elif action.endswith("_down") and field_index < len(ct.fields) - 1:
                                new_field_index = field_index + 1

                        if field_index > -1 and new_field_index > -1:
                            swap_field = ct.fields[new_field_index]
                            corpus.content_types[action_content_type].fields[new_field_index] = corpus.content_types[action_content_type].fields[field_index]
                            corpus.content_types[action_content_type].fields[field_index] = swap_field
                            corpus.save()

                            response['messages'].append("Field {0} successfully successfully repositioned.".format(
                                action_field_name
                            ))

        # HANDLE SCHEMA EXPORT
        elif request.method == 'GET' and 'export' in request.GET and request.GET['export'] == 'schema':
            schema = []
            for ct_name in corpus.content_types.keys():
                schema.append(corpus.content_types[ct_name].to_dict())

            return HttpResponse(
                json.dumps(schema),
                content_type='application/json'
            )

        # HANDLE CORPUS DELETION
        elif request.method == 'POST' and 'corpus-deletion-name' in request.POST:
            if corpus.name == request.POST['corpus-deletion-name']:
                run_job(corpus.queue_local_job(task_name="Delete Corpus", parameters={}))

                return redirect("/?msg=Corpus {0} is being deleted.".format(
                    corpus.name
                ))

    return render(
        request,
        'corpus.html',
        {
            'corpus_id': corpus_id,
            'response': response,
        }
    )


def edit_content(request, corpus_id, content_type, content_id=None):
    context = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and content_type in corpus.content_types:

        if request.method == 'POST':
            temp_file_fields = []
            multi_field_values = {}
            ct_fields = {}
            for field in corpus.content_types[content_type].fields:
                if not field.type == 'embedded':
                    ct_fields[field.name] = field
                    if field.multiple:
                        multi_field_values[field.name] = []

            content = corpus.get_content(content_type, content_id)

            for field_param, field_value in request.POST.items():
                param_parts = field_param.split('-')
                field_name = param_parts[0]

                if field_name in ct_fields:
                    # set value for file fields
                    if ct_fields[field_name].type == 'file':
                        if field_value:
                            base_path = "{corpus_path}/{content_type}/temporary_uploads".format(
                                corpus_path=corpus.path,
                                content_type=content_type
                            )

                            if content.id:
                                base_path = "{content_path}/files".format(content_path=content.path)

                            file_path = "{base_path}{sub_path}".format(
                                base_path=base_path,
                                sub_path=field_value
                            )
                            if os.path.exists(file_path):
                                field_value = File.process(
                                    file_path,
                                    desc="{0} for {1}".format(ct_fields[field_name].label, content_type),
                                    prov_type="Scholar",
                                    prov_id=str(context['scholar'].id)
                                )

                                if not content.id and field_name not in temp_file_fields:
                                    temp_file_fields.append(field_name)
                        else:
                            field_value = None

                    # set value for xref fields
                    elif ct_fields[field_name].type == 'cross_reference':
                        field_value = corpus.get_content(ct_fields[field_name].cross_reference_type, field_value).to_dbref()

                    # set value for number fields
                    elif ct_fields[field_name].type == 'number' and not field_value:
                        field_value = None

                    # set value for number fields
                    elif ct_fields[field_name].type == 'date' and not field_value:
                        field_value = None

                    if ct_fields[field_name].multiple and len(param_parts) == 3:
                        multi_field_values[field_name].append(field_value)
                    else:
                        setattr(content, field_name, field_value)

            for multi_field_name in multi_field_values.keys():
                setattr(content, multi_field_name, multi_field_values[multi_field_name])

            content.save()

            if temp_file_fields:
                print('has temp file fields')
                for temp_file_field in temp_file_fields:
                    if ct_fields[temp_file_field].multiple:
                        for f_index in range(0, len(getattr(content, temp_file_field))):
                            content._move_temp_file(temp_file_field, f_index)
                    else:
                        content._move_temp_file(temp_file_field)
                content.save()

            return redirect("/corpus/{0}/{1}/{2}".format(
                corpus_id,
                content_type,
                str(content.id)
            ))

        return render(
            request,
            'content_edit.html',
            {
                'corpus_id': corpus_id,
                'response': context,
                'content_type': content_type,
                'content_id': content_id,
            }
        )


def view_content(request, corpus_id, content_type, content_id):
    context = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, context['scholar'])

    if not corpus or content_type not in corpus.content_types:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")

    return render(
        request,
        'content_view.html',
        {
            'response': context,
            'corpus_id': corpus_id,
            'content_type': content_type,
            'content_id': content_id,
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


@login_required
def get_file(request, file_uri):
    context = _get_context(request)
    file_uri = file_uri.replace('|', '/')
    uri_dict = parse_uri(file_uri)
    file_path = None

    if 'corpus' in uri_dict:
        if context['scholar'].is_admin or uri_dict['corpus'] in context['scholar'].available_corpora:
            results = run_neo(
                '''
                    MATCH (f:File { uri: $file_uri })
                    return f.path as file_path
                ''',
                {
                    'file_uri': file_uri
                }
            )

            if results and 'file_path' in results[0].keys():
                file_path = results[0]['file_path']

    if file_path:
        mime_type, encoding = mimetypes.guess_type(file_path)
        response = HttpResponse(content_type=mime_type)
        response['X-Accel-Redirect'] = "/files/{0}".format(file_path.replace('/corpora/', ''))
        return response

    raise Http404("File not found.")


@login_required
def get_image(
    request,
    image_uri,
    region="full",
    size="full",
    rotation="0",
    quality="default",
    format="png",
):
    context = _get_context(request)
    image_uri = image_uri.replace('|', '/')
    uri_dict = parse_uri(image_uri)
    file_path = None

    if 'corpus' in uri_dict:
        if context['scholar'].is_admin or uri_dict['corpus'] in context['scholar'].available_corpora:
            results = run_neo(
                '''
                    MATCH (f:File { uri: $image_uri, is_image: true })
                    return f.path as file_path
                ''',
                {
                    'image_uri': image_uri
                }
            )

            if results and 'file_path' in results[0].keys():
                file_path = results[0]['file_path']

    if file_path:
        mime_type, encoding = mimetypes.guess_type(file_path)
        response = HttpResponse(content_type=mime_type)
        response['X-Accel-Redirect'] = "/media/{identifier}/{region}/{size}/{rotation}/{quality}.{format}".format(
            identifier=file_path[1:].replace('/', '$!$'),
            region=region,
            size=size,
            rotation=rotation,
            quality=quality,
            format=format
        )
        return response

    raise Http404("File not found.")


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
        json.dumps(corpus.to_dict()),
        content_type='application/json'
    )


@api_view(['GET'])
def api_content(request, corpus_id, content_type, content_id=None):
    context = _get_context(request)
    content = {}
    corpus = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and content_type in corpus.content_types:
        if content_id:
            content = corpus.get_content(content_type, content_id, context['only'])
            content = content.to_dict()
        else:
            xref_fields = [field.name for field in corpus.content_types[content_type].fields if field.cross_reference_type]

            if context['search']:
                content = corpus.search_content(content_type=content_type, **context['search'])
            else:
                content = corpus.search_content(content_type=content_type, general_search_query="*")

            for hit in range(0, len(content['records'])):
                for field_name in content['records'][hit].keys():
                    if field_name in xref_fields:
                        content['records'][hit][field_name] = json.loads(content['records'][hit][field_name])


    return HttpResponse(
        json.dumps(content),
        content_type='application/json'
    )


@api_view(['GET', 'POST'])
def api_content_files(request, corpus_id, content_type, content_id=None):
    context = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, context['scholar'])
    files = []

    if corpus:

        base_path = "{corpus_path}/{content_type}/temporary_uploads".format(
            corpus_path=corpus.path,
            content_type=content_type
        )

        if content_id:
            content = corpus.get_content(content_type, content_id, only=['path'])
            if content:
                base_path = "{content_path}/files".format(content_path=content.path)
            else:
                base_path = ""

        if base_path:
            print(base_path)

            sub_path = _clean(request.GET, 'path', '')
            full_path = base_path + sub_path
            filter = _clean(request.GET, 'filter', '')

            # HANDLE UPLOADS
            if 'filepond' in request.FILES:
                filename = re.sub(r'[^a-zA-Z0-9\\.\\-]', '_', request.FILES['filepond'].name)
                file_path = "{0}/{1}".format(full_path, filename)
                print(file_path)

                if not os.path.exists(full_path):
                    os.makedirs(full_path)

                with open(file_path, 'wb+') as destination:
                    for chunk in request.FILES['filepond'].chunks():
                        destination.write(chunk)

                return HttpResponse(ObjectId(), content_type='text/plain')

            # HANDLE NEW DIRECTORY
            if request.method == 'POST' and _contains(request.POST, ['path', 'newdir']):
                sub_path = _clean(request.POST, 'path')
                full_path = base_path + sub_path
                new_dir = _clean(request.POST, 'newdir')
                new_dir_path = full_path + '/' + new_dir
                if not os.path.exists(new_dir_path):
                    os.makedirs(new_dir_path)
                return HttpResponse(status=204)

            # BUILD LIST OF FILES
            if os.path.exists(full_path):
                contents = os.listdir(full_path)
                contents = sorted(contents, key=lambda s: s.casefold())
                for filename in contents:
                    if not filter or filter in filename.lower():
                        filepath = "{0}/{1}".format(full_path, filename)
                        if os.path.isdir(filepath):
                            files.append({
                                'type': 'dir',
                                'path': "{0}/{1}".format(sub_path, filename),
                                'filename': filename
                            })
                        else:
                            files.append({
                                'type': 'file',
                                'path': sub_path,
                                'filename': filename
                            })

    return HttpResponse(
        json.dumps(files),
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
def api_tasks(request, content_type=None):
    response = _get_context(request)
    tasks = get_tasks(response['scholar'], content_type=content_type)

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
def api_content_jobs(request, corpus_id, content_type, content_id):
    jobs = Job.get_jobs(corpus_id=corpus_id, content_type=content_type, content_id=content_id)
    payload = []
    for job in jobs:
        payload.append(job.to_dict())

    return HttpResponse(
        json.dumps(payload),
        content_type='application/json'
    )


@api_view(['GET', 'POST'])
def api_scholar_preference(request, content_type, preference):
    context = _get_context(request)
    value = None

    if request.method == 'GET' and 'content_uri' in request.GET:

        print("uri: {0}".format(request.GET['content_uri']))

        value = context['scholar'].get_preference(
            content_type,
            request.GET['content_uri'],
            preference
        )

    elif request.method == 'POST' and _contains(request.POST, ['content_uri', 'value']):
        value = request.POST['value']
        context['scholar'].set_preference(
            content_type,
            request.POST['content_uri'],
            preference,
            value
        )

    return HttpResponse(
        json.dumps(value),
        content_type='application/json'
    )
