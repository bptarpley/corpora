import subprocess
import mimetypes
import asyncio
from copy import deepcopy
from ipaddress import ip_address
from asgiref.sync import sync_to_async
from django.shortcuts import render, redirect, HttpResponse
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.template import Context, Template
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from mongoengine.errors import NotUniqueError
from rest_framework.decorators import api_view
from rest_framework.authtoken.models import Token
from django_eventstream import send_event
from notebook.notebookapp import list_running_servers, NotebookApp
from types import SimpleNamespace
from html import unescape
from time import sleep
from corpus import (
    Scholar, Task,
    ContentTypeGroupMember, FieldRenderer,
    run_neo, get_network_json, search_corpora, search_scholars,
    FIELD_LANGUAGES
)
from .captcha import generate_captcha, validate_captcha
from .tasks import *
from .utilities import (
    _get_context,
    _clean,
    _contains,
    build_search_params_from_dict,
    get_scholar_corpora,
    get_scholar_corpus,
    scholar_has_privilege,
    get_open_access_corpora,
    parse_uri,
    get_jobsites,
    get_tasks,
    clear_cached_session_scholar,
    order_content_schema,
    process_content_bundle,
    process_corpus_backup_file,
    fix_mongo_json,
    delimit_content_json,
    create_content_csv_rows,
    send_alert
)


@login_required
def corpora(request):
    context = _get_context(request)

    if context['scholar'].is_admin and request.method == 'POST':
        if 'new-corpus-name' in request.POST:
            include_document_content_types = 'new-corpus-content-types' in request.POST

            c_name = unescape(_clean(request.POST, 'new-corpus-name'))
            c_desc = unescape(_clean(request.POST, 'new-corpus-desc'))
            c_open = unescape(_clean(request.POST, 'new-corpus-open'))

            c = Corpus()
            c.name = c_name
            c.description = c_desc
            c.open_access = True if c_open else False
            c.save()

            if c.open_access:
                get_open_access_corpora(False)

            if include_document_content_types:
                from plugins.document.content import REGISTRY
                for schema in REGISTRY:
                    c.save_content_type(schema)

            sleep(4)

            context['messages'].append("{0} corpus successfully created.".format(c.name))

        elif 'admin-action' in request.POST:
            action = _clean(request.POST, 'admin-action')
            if action == 'scrub-provenance':
                scrub_all_provenance()
                context['messages'].append("Provenance scrubbing job launched!")

    scholar_corpora = get_scholar_corpora(context['scholar'], page_size=1000)
    if scholar_corpora:
        scholar_corpora = scholar_corpora.order_by('name')

    return render(
        request,
        'index.html',
        {
            'response': context,
            'corpora': scholar_corpora
        }
    )


@login_required
def corpus(request, corpus_id):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])
    content_views = []

    if corpus:
        # ADMIN REQUESTS
        if scholar_has_privilege('Admin', role):
            # get content views
            content_views = ContentView.objects(corpus=corpus, status__in=['populated', 'needs_refresh']).order_by('name')

            # schema export
            if 'export' in request.GET and request.GET['export'] == 'schema':
                schema = []
                for ct_name in corpus.content_types.keys():
                    schema.append(corpus.content_types[ct_name].to_dict())

                return HttpResponse(
                    json.dumps(schema, indent=4),
                    content_type='application/json'
                )

        # POST REQUESTS - only scholars with Contributor or higher privileges
        if request.method == 'POST' and scholar_has_privilege('Contributor', role):

            # HANDLE CONTENT DELETION
            if _contains(request.POST, ['deletion-confirmed', 'content-type', 'content-ids']):
                deletion_ct = _clean(request.POST, 'content-type')
                deletion_ids = _clean(request.POST, 'content-ids')

                if deletion_ct in corpus.content_types:
                    if deletion_ids == 'all':
                        corpus.delete_content_type(deletion_ct, content_only=True)
                        response['messages'].append("All instances of {0} were successfully deleted.".format(
                            corpus.content_types[deletion_ct].plural_name
                        ))
                    else:
                        deletion_ids = [d_id for d_id in deletion_ids.split(',') if d_id]
                        deleted = []
                        for deletion_id in deletion_ids:
                            try:
                                to_delete = corpus.get_content(deletion_ct, deletion_id)
                                to_delete.delete()
                                deleted.append(deletion_id)
                            except:
                                response['errors'].append(
                                    "An error occurred when attempting to delete {0} with ID {1}!".format(deletion_ct,
                                                                                                          deletion_id))
                                print(traceback.format_exc())

                        if deleted:
                            response['messages'].append("The following {0} were successfully deleted:<br><br>{1}".format(
                                corpus.content_types[deletion_ct].plural_name,
                                '<br>'.join(deleted)
                            ))

            # EDITOR OR HIGHER POST REQUESTS
            if scholar_has_privilege('Editor', role):

                # HANDLE IMPORT CORPUS FILES FORM SUBMISSION
                if 'import-corpus-files' in request.POST:
                    import_files = json.loads(request.POST['import-corpus-files'])
                    upload_path = corpus.path + '/files'

                    for import_file in import_files:
                        import_file_path = "{0}{1}".format(upload_path, import_file)
                        fixed_basename = re.sub(r'[^a-zA-Z0-9\\.\\-]', '_', os.path.basename(import_file_path))
                        import_file_path = "{0}/{1}".format(os.path.dirname(import_file_path), fixed_basename)

                        if os.path.exists(import_file_path):
                            extension = import_file.split('.')[-1]
                            corpus.save_file(File.process(
                                import_file_path,
                                desc=extension.upper() + " File",
                                prov_type="User Import",
                                prov_id=response['scholar']['username'],
                                primary=False
                            ))

                # HANDLE CORPUS FILE DELETION - only scholars with Admin or higher
                elif 'corpus-files-to-delete' in request.POST and scholar_has_privilege('Admin', role):
                    files_to_delete = _clean(request.POST, 'corpus-files-to-delete')
                    files_dir = "{0}/files".format(corpus.path)

                    if corpus.files and os.path.exists(files_dir):
                        if files_to_delete == 'ALL':
                            shutil.rmtree(files_dir)

                            run_neo('''
                                MATCH (c:Corpus {uri: $corpus_uri}) -[rel:hasFile]-> (f:_File)
                                DETACH DELETE f
                            ''', {'corpus_uri': corpus.uri})

                            corpus.files = {}
                            corpus.save()

                            os.makedirs(files_dir)
                        else:
                            files_to_delete = files_to_delete.split(',')
                            for file_to_delete in files_to_delete:
                                if file_to_delete in corpus.files:
                                    file = corpus.files[file_to_delete]
                                    if os.path.exists(file.path):
                                        os.remove(file.path)
                                        file._unlink(corpus.uri)
                                        del corpus.files[file_to_delete]
                            corpus.save()

                        response['messages'].append("Corpus file(s) deleted successfully.")

                # HANDLE REPO CREATION
                elif _contains(request.POST, ['new-repo-name', 'new-repo-url', 'new-repo-branch']):
                    repo = GitRepo()
                    repo.name = _clean(request.POST, 'new-repo-name')
                    repo.remote_url = _clean(request.POST, 'new-repo-url')
                    repo.remote_branch = _clean(request.POST, 'new-repo-branch')

                    if repo.name and repo.remote_url and repo.remote_branch:
                        repo.path = "{0}/{1}/{2}".format(corpus.path, 'repos', repo.name)

                        if repo.name not in corpus.repos and not os.path.exists(repo.path):
                            corpus.repos[repo.name] = repo
                            corpus.save()

                            clone_job_params = { 'repo_name': repo.name }
                            if 'new-repo-auth' in request.POST:
                                repo_user = _clean(request.POST, 'new-repo-user')
                                repo_pwd = _clean(request.POST, 'new-repo-pwd')
                                if repo_user and repo_pwd:
                                    clone_job_params['repo_user'] = repo_user
                                    clone_job_params['repo_pwd'] = repo_pwd

                            run_job(corpus.queue_local_job(task_name="Pull Repo", parameters=clone_job_params))
                            response['messages'].append('Repository "{0}" successfully added to this corpus.'.format(repo.name))
                        else:
                            response['errors'].append('A repository with that name already exists in this corpus!')
                    else:
                        response['errors'].append("Please provide values for the repository's name, URL, and branch.")

                # HANDLE REPO DELETION
                elif _contains(request.POST, ['deletion-confirmed', 'repo']):
                    repo_name = _clean(request.POST, 'repo')
                    if repo_name in corpus.repos:
                        corpus.repos[repo_name].clear()
                        del corpus.repos[repo_name]
                        corpus.save()

                        response['messages'].append('The "{0}" repository has been deleted.'.format(repo_name))
                    else:
                        response['errors'].append(
                            'An error occurred when attempting to delete the "{0}" repository!'.format(
                                repo_name))

                # HANDLE CONTENT VIEW DELETION
                elif _contains(request.POST, ['deletion-confirmed', 'content-view']):
                    cv_id = _clean(request.POST, 'content-view')
                    cv = ContentView.objects.get(id=cv_id)
                    cv_name = cv.name
                    cv.set_status('deleting')
                    cv.save()

                    run_job(corpus.queue_local_job(task_name="Content View Lifecycle", parameters={
                        'cv_id': cv_id,
                        'stage': 'delete',
                    }))

                    content_views = ContentView.objects(corpus=corpus, status='populated').order_by('name')
                    response['messages'].append('The "{0}" Content View is being deleted.'.format(cv_name))

                # HANDLE CONTENT TYPE SCHEMA SUBMISSION
                elif 'schema' in request.POST:
                    schema = json.loads(request.POST['schema'])

                    # reorder schema according to dependencies
                    ordered_schema = order_content_schema(schema)

                    # if no problems with dependencies, save the content types in correct order
                    if len(ordered_schema) == len(schema):

                        run_job(corpus.queue_local_job(task_name="Save Content Type Schema", parameters={
                            'schema': json.dumps(ordered_schema),
                        }))

                        response['messages'].append('''
                            The content type schema for this corpus is being saved, and once this task is completed, you'll need to refresh this page to see those changes. Due to the setting/unsetting of fields as being in lists, or the 
                            changing of label templates, <strong>reindexing of existing content may occur</strong>, which can 
                            result in the temporary unavailability of content in lists or searches. All existing content will be 
                            made available once reindexing completes.  
                        ''')
                    else:
                        response['errors'].append('''
                            Unable to save content type schema! There may be an issue with circular dependencies.
                        ''')

                # HANDLE CONTENT_TYPE/FIELD ACTIONS THAT REQUIRE CONFIRMATION
                elif _contains(request.POST, [
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

                            # delete content type
                            if action == 'delete':
                                run_job(corpus.queue_local_job(task_name="Delete Content Type", parameters={
                                    'content_type': action_content_type,
                                }))

                                response['messages'].append("Content type {0} successfully deleted.".format(action_content_type))
                                sleep(4)

                            # re-index content type
                            elif action == 'reindex':
                                run_job(corpus.queue_local_job(task_name="Adjust Content", parameters={
                                    'content_type': action_content_type,
                                    'reindex': True,
                                    'relabel': False,
                                    'resave': False
                                }))

                                response['messages'].append(
                                    "Content type {0} re-indexing successfully commenced.".format(action_content_type))

                            # re-label content type
                            elif action == 'relabel':
                                run_job(corpus.queue_local_job(task_name="Adjust Content", parameters={
                                    'content_type': action_content_type,
                                    'reindex': True,
                                    'relabel': True,
                                    'relink': True
                                }))

                                response['messages'].append(
                                    "Content type {0} re-labeling successfully commenced.".format(action_content_type))

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

            # CORPORA ADMIN POST REQUESTS
            if scholar_has_privilege('Admin', role):

                # LAUNCH CORPUS NOTEBOOK
                if 'launch-notebook' in request.POST:
                    if corpus.path:
                        # running_notebooks = subprocess.check_output("jupyter notebook list", shell=True).decode('utf-8')
                        running_notebooks = list(list_running_servers())
                        if running_notebooks and '0.0.0.0:9999' in running_notebooks[0]['url']:
                            subprocess.Popen("jupyter notebook stop 9999".split())
                            sleep(2)

                        notebook_path = "{0}/corpus_notebook.ipynb".format(corpus.path)
                        jupyter_token = "{0}{1}".format(corpus_id, ObjectId())
                        notebook_url = "/notebook/notebooks/corpus_notebook.ipynb?token={0}".format(jupyter_token)

                        if not os.path.exists(notebook_path):
                            notebook_contents = {
                                "cells": [
                                    {
                                        "cell_type": "code",
                                        "execution_count": None,
                                        "metadata": {
                                            "scrolled": True
                                        },
                                        "outputs": [],
                                        "source": [
                                            "import os, sys\n",
                                            "sys.path.insert(0, '/apps/corpora')\n",
                                            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', \"settings.py\")\n",
                                            "import django\n",
                                            "django.setup()\n",
                                            "from corpus import *\n",
                                            "my_corpus = get_corpus('{0}')\n".format(corpus_id),
                                            "\n",
                                            "# ~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~\n",
                                            "# ~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~\n",
                                            "# \n",
                                            "# WELCOME to Corpora's experimental iPython notebook shell!\n",
                                            "# \n",
                                            "# This cell must be executed in order to use Corpora's built-in\n",
                                            "# \"corpus\" module, which allows you to interact programmatically\n",
                                            "# with the content in your corpus.\n",
                                            "# \n",
                                            "# For your convenience, a variable named 'my_corpus' will be\n",
                                            "# instantiated by this cell, allowing you to dive right in :)\n",
                                            "# \n",
                                            "# NOTE: With great power comes great responsibility. While Corpora\n",
                                            "# itself runs under a non-privileged user, direct access to the \n",
                                            "# corpus module via Python shell currently grants you write access\n",
                                            "# to every corpus in Corpora. As such, access to this notebook\n",
                                            "# functionality should only given to the most trusted users!\n",
                                            "# \n",
                                            "# ~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~\n",
                                            "# ~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~@~~~\n",
                                        ]
                                    }
                                ],
                                "metadata": {
                                    "kernelspec": {
                                        "display_name": "Corpora",
                                        "language": "python",
                                        "name": "corpora"
                                    },
                                    "language_info": {
                                        "codemirror_mode": {
                                            "name": "ipython",
                                            "version": 3
                                        },
                                        "file_extension": ".py",
                                        "mimetype": "text/x-python",
                                        "name": "python",
                                        "nbconvert_exporter": "python",
                                        "pygments_lexer": "ipython3",
                                        "version": "3.7.5"
                                    }
                                },
                                "nbformat": 4,
                                "nbformat_minor": 2
                            }

                            with open(notebook_path, 'w') as notebook_out:
                                json.dump(notebook_contents, notebook_out, indent=2)

                        pid = subprocess.Popen([
                            #'/usr/local/bin/jupyter', 'notebook',
                            'jupyter', 'notebook',
                            notebook_path,
                            '--ip', '0.0.0.0',
                            '--port', '9999',
                            '--no-browser',
                            '--NotebookApp.base_url="/notebook/"',
                            '--NotebookApp.token="{0}"'.format(jupyter_token),
                            '--NotebookApp.notebook_dir="/corpora/{0}"'.format(corpus_id),
                            '--NotebookApp.shutdown_no_activity_timeout=3600',
                            '--NotebookApp.allow_origin="*"'
                        ])

                        #notebook = NotebookApp()
                        #notebook.initialize()

                        response['messages'].append("Notebook server successfully launched! Access your notebook <a href='{0}' target='_blank'>here</a>.".format(notebook_url))

                # HANDLE CORPUS DELETION
                elif 'corpus-deletion-name' in request.POST:
                    if corpus.name == request.POST['corpus-deletion-name']:
                        run_job(corpus.queue_local_job(task_name="Delete Corpus", parameters={}))

                        return redirect("/?msg=Corpus {0} is being deleted.".format(
                            corpus.name
                        ))

                # HANDLE OPEN ACCESS TOGGLE
                elif 'corpus-open-access-toggle' in request.POST:
                    if corpus.open_access:
                        corpus.open_access = False
                        response['messages'].append('This corpus is no longer open access.')
                    else:
                        corpus.open_access = True
                        response['messages'].append('This corpus is now open access.')
                    get_open_access_corpora(False)  # to refresh redis cache
                    corpus.save()

    return render(
        request,
        'corpus.html',
        {
            'page_title': corpus.name,
            'corpus_id': corpus_id,
            'role': role,
            'content_views': content_views,
            'invalid_field_names': settings.INVALID_FIELD_NAMES,
            'field_languages': FIELD_LANGUAGES,
            'response': response,
            'available_jobsites': [str(js.id) for js in response['scholar']['available_jobsites']],
            'available_tasks': [str(t.id) for t in response['scholar']['available_tasks']],
        }
    )


@login_required
def edit_content(request, corpus_id, content_type, content_id=None):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    edit_widget_url = None
    content_ids = request.POST.get('content-ids', None)
    content_query = request.POST.get('content-query', None)
    created_message_token = request.GET.get('created_message_token', None)
    popup = 'popup' in request.GET
    inclusions = None
    javascript_functions = None
    css_styles = None

    if scholar_has_privilege('Contributor', role) and corpus and content_type in corpus.content_types:
        inclusions, javascript_functions, css_styles = corpus.content_types[content_type].get_render_requirements('edit')

        if content_id:
            content = corpus.get_content(content_type, content_id)

            if content:
                corpus.content_types[content_type].set_field_values_from_content(content)

            if corpus.content_types[content_type].edit_widget_url:

                edit_widget_url = corpus.content_types[content_type].edit_widget_url.format(
                    corpus_id=corpus_id,
                    content_type=content_type,
                    content_id=content_id
                )

        if request.method == 'POST':
            content = corpus.get_content(content_type, content_id)

            # save content
            if _contains(request.POST, ['corpora-content-edit', 'content-bundle']):

                content_bundle = request.POST.get('content-bundle', None)
                if content_bundle:
                    content_bundle = json.loads(content_bundle)
                    print(json.dumps(content_bundle, indent=4))

                    if content_ids or content_query:
                        run_job(corpus.queue_local_job(
                            task_name='Bulk Edit Content',
                            parameters={
                                'content_type': content_type,
                                'content_ids': content_ids,
                                'content_query': content_query,
                                'content_bundle': content_bundle,
                                'scholar_id': str(context['scholar'].id)
                            }
                        ))
                        return redirect("/corpus/{0}/?msg=Bulk edit content job submitted.".format(corpus_id))

                    else:
                        try:
                            content = process_content_bundle(
                                corpus,
                                content_type,
                                content,
                                content_bundle,
                                context['scholar'].id
                            )
                        except NotUniqueError as e:
                            context['errors'].append(f"Unable to save content! You attempted to save a duplicate value to one or more unique fields.")

                        if not context['errors']:
                            if 'save-and-create' in request.POST:
                                return redirect("/corpus/{0}/{1}/?msg={1} saved.".format(
                                    corpus_id,
                                    content_type
                                ))
                            elif created_message_token:
                                send_event(corpus_id, 'event', {
                                    'event_type': created_message_token,
                                    'id': str(content.id),
                                    'uri': content.uri,
                                    'label': content.label
                                })
                                return HttpResponse(status=204)
                            else:
                                return redirect("/corpus/{0}/{1}/{2}".format(
                                    corpus_id,
                                    content_type,
                                    str(content.id)
                                ))

            # delete content
            elif 'delete-content' in request.POST:
                content_label = content.label
                content.delete()
                return redirect("/corpus/{0}/?msg={1} is being deleted.".format(
                    corpus_id,
                    content_label
                ))

            # delete repo
            elif _contains(request.POST, ['delete-repo', 'repo-name', 'field-name']):
                repo_name = _clean(request.POST, 'repo-name')
                field_name = _clean(request.POST, 'field-name')
                deletion_performed = False

                if getattr(content, field_name):
                    field = corpus.content_types[content_type].get_field(field_name)
                    if field.multiple:
                        for val_index, val in enumerate(getattr(content, field_name)):
                            if val and hasattr(val, 'name') and val.name == repo_name:
                                del getattr(content, field_name)[val_index]
                                deletion_performed = True
                    else:
                        setattr(content, field_name, None)
                        deletion_performed = True

                if deletion_performed:
                    content.save()

                    repo_path = f"{content.path}/repos/{request.POST.get('repo-name')}"
                    if os.path.exists(repo_path) and os.path.exists(f"{repo_path}/.git"):
                        shutil.rmtree(repo_path)

                return HttpResponse(status=204)

        return render(
            request,
            'content_edit.html',
            {
                'page_title': content_type,
                'corpus_id': corpus_id,
                'response': context,
                'content_type': content_type,
                'ct': corpus.content_types[content_type],
                'inclusions': inclusions,
                'javascript_functions': javascript_functions,
                'css_styles': css_styles,
                'edit_widget_url': edit_widget_url,
                'popup': popup,
                'content_id': content_id,
                'bulk_editing': content_ids or content_query,
                'content_ids': content_ids,
                'content_query': content_query
            }
        )
    else:
        raise Http404("You are not authorized to view this page.")


@login_required
def render_field_component(request, field_type, mode, language, field_name, suffix):
    language_mime_map = {
        'html': 'text/html',
        'css': 'text/css',
        'js': 'text/javascript',
    }
    renderer = FieldRenderer(field_type, mode, language)
    context = Context({'field': SimpleNamespace(type=field_type, name=field_name), 'suffix': suffix})
    return HttpResponse(
        renderer.render(context),
        content_type=language_mime_map[language]
    )


def view_content(request, corpus_id, content_type, content_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    render_template = _clean(request.GET, 'render_template', None)
    popup = 'popup' in request.GET
    view_widget_url = None
    default_css = None

    if not corpus or content_type not in corpus.content_types:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")

    if corpus.content_types[content_type].view_widget_url:
        view_widget_url = corpus.content_types[content_type].view_widget_url.format(
            corpus_id=corpus_id,
            content_type=content_type,
            content_id=content_id
        )

    if 'DefaultCSS' in corpus.content_types[content_type].templates:
        default_css = corpus.content_types[content_type].templates['DefaultCSS'].template

    content = corpus.get_content(content_type, content_id)

    if content:
        corpus.content_types[content_type].set_field_values_from_content(content)
        inclusions, javascript_functions, css_styles = corpus.content_types[content_type].get_render_requirements('view')

        if render_template and render_template in corpus.content_types[content_type].templates:
            django_template = Template(corpus.content_types[content_type].templates[render_template].template)
            context = Context({content_type: content})
            return HttpResponse(
                django_template.render(context),
                content_type=corpus.content_types[content_type].templates[render_template].mime_type
            )
    else:
        raise Http404("Content does not exist, or you are not authorized to view it.")

    return render(
        request,
        'content_view.html',
        {
            'page_title': content.label,
            'corpus_id': corpus_id,
            'role': role,
            'popup': popup,
            'content_type': corpus.content_types[content_type],
            'content_id': content_id,
            'content_label': content.label,
            'content_uri': content.uri,
            'inclusions': inclusions,
            'javascript_functions': javascript_functions,
            'css_styles': css_styles,
            'response': context,
            'view_widget_url': view_widget_url,
            'default_css': default_css,
        }
    )


def explore_content(request, corpus_id, content_type):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    content_ids = _clean(request.POST, 'content-ids', '')
    content_uris = _clean(request.POST, 'content-uris', '')
    popup = 'popup' in request.GET
    has_content = content_ids or content_uris

    if not corpus or content_type not in corpus.content_types or not has_content:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")
    else:
        if content_ids:
            content_ids = content_ids.split(',')
        else:
            content_ids = []

        if content_uris:
            content_uris = content_uris.split(',')
        else:
            content_uris = []

    return render(
        request,
        'content_explore.html',
        {
            'response': context,
            'corpus_id': corpus_id,
            'role': role,
            'content_type': content_type,
            'content_ids': content_ids,
            'content_uris': content_uris,
            'popup': popup
        }
    )


@login_required
def merge_content(request, corpus_id, content_type):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    merge_ids = request.POST.get('content-ids', '')
    merge_ids = [merge_id for merge_id in merge_ids.split(',') if merge_id]

    if scholar_has_privilege('Contributor', role) and corpus and content_type in corpus.content_types:
        merge_contents = corpus.get_content(content_type, {'id__in': merge_ids})

        target_id = request.POST.get('target-id', '')
        delete_merged = 'delete-merged' in request.POST
        cascade_deletion = 'cascade-deletion' in request.POST

        if not target_id:
            return render(
                request,
                'content_merge.html',
                {
                    'corpus_id': corpus_id,
                    'response': context,
                    'content_type': content_type,
                    'content_type_plural': corpus.content_types[content_type].plural_name,
                    'merge_contents': merge_contents,
                }
            )
        else:
            job_id = corpus.queue_local_job(task_name="Merge Content", parameters={
                'content_type': content_type,
                'target_id': target_id,
                'merge_ids': ','.join(merge_ids),
                'delete_merged': delete_merged,
                'cascade_deletion': cascade_deletion
            })
            run_job(job_id)
            sleep(4)
            return render(
                request,
                'content_merge.html',
                {
                    'corpus_id': corpus_id,
                    'response': context,
                    'content_type': content_type,
                    'content_type_plural': corpus.content_types[content_type].plural_name,
                    'merge_contents': merge_contents,
                    'job_id': job_id
                }
            )

    raise Http404("You are not authorized to view this page.")


@login_required
def job_widget(request, corpus_id=None, content_type=None, content_id=None):
    context = _get_context(request)
    role = None
    if context['scholar'].is_admin:
        role = 'Admin'
    elif corpus_id:
        corpus, role = get_scholar_corpus(corpus_id, context['scholar'])

    if role in ['Admin', 'Editor']:
        if request.method == 'POST' and 'kill-job-id' in request.POST:
            kill_job_id = _clean(request.POST, 'kill-job-id')
            job = Job(kill_job_id)
            job.kill()

        return render(
            request,
            'JobsWidget.html',
            {
                'popup': True,
                'role': role,
                'corpus_id': corpus_id,
                'content_type': content_type,
                'content_id': content_id
            }
        )
    else:
        raise Http404("You are not authorized to view this page.")


def iiif_widget(request, corpus_id, content_type, content_id, content_field):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    image_url = None

    if corpus:
        try:
            content = corpus.get_content(content_type, content_id, only=[content_field])
            image_url = getattr(content, content_field, None)

            if str(type(image_url)) == "<class 'corpus.File'>":
                image_url = image_url.get_url("/corpus/{0}/{1}/{2}".format(
                    corpus_id,
                    content_type,
                    content_id
                ))
        except:
            print(traceback.format_exc())
            raise Http404("You are not authorized to view this page.")

    return render(
        request,
        'IIIFWidget.html',
        {
            'corpus_id': corpus_id,
            'popup': True,
            'role': role,
            'image_url': image_url,
            'response': context,
        }
    )


@login_required
def bulk_job_manager(request, corpus_id, content_type):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    job_ids = []
    num_jobs = 0

    if (context['scholar'].is_admin or role == 'Editor') and request.method == 'POST':
        if _contains(request.POST, ['task-id', 'content-query']):
            task = Task.objects(id=_clean(request.POST, 'task-id'))[0]
            if not task.configuration:
                query = json.loads(request.POST['content-query'])
                search_params = build_search_params_from_dict(query)
                search_params['page_size'] = 1
                search_params['page'] = 1
                search_params['only'] = ['id']
                results = corpus.search_content(content_type, **search_params)
                num_jobs = results['meta']['total']
                bulk_job_id = corpus.queue_local_job(
                    task_name='Bulk Launch Jobs',
                    scholar_id=context['scholar'].id,
                    parameters={
                        'content_type': content_type,
                        'task_id': str(task.id),
                        'query': request.POST['content-query'],
                        'job_params': '{}'
                    }
                )
                run_job(bulk_job_id)

                context['messages'].append('Successfully enqueued {0} jobs.'.format(num_jobs))

                return render(
                    request,
                    'bulk_job_manager.html',
                    {
                        'corpus_id': corpus_id,
                        'corpus_name': corpus.name,
                        'response': context,
                        'content_type': content_type,
                        'content_type_plural': corpus.content_types[content_type].plural_name,
                        'num_jobs': num_jobs
                    }
                )

        elif _contains(request.POST, ['task-id', 'content-ids']):
            task = Task.objects(id=_clean(request.POST, 'task-id'))[0]
            if not task.configuration:
                content_ids = request.POST.get('content-ids', '')
                content_ids = [content_id for content_id in content_ids.split(',') if content_id]

                for content_id in content_ids:
                    job_ids.append(corpus.queue_local_job(
                        content_type=content_type,
                        content_id=content_id,
                        task_id=task.id,
                        scholar_id=context['scholar'].id
                    ))

                for job_id in job_ids:
                    run_job(job_id)

                num_jobs = len(job_ids)

                context['messages'].append('Successfully enqueued {0} jobs.'.format(num_jobs))

                return render(
                    request,
                    'bulk_job_manager.html',
                    {
                        'corpus_id': corpus_id,
                        'corpus_name': corpus.name,
                        'response': context,
                        'content_type': content_type,
                        'content_type_plural': corpus.content_types[content_type].plural_name,
                        'num_jobs': num_jobs
                    }
                )

    raise Http404("You are not authorized to view this page.")


# This view is special in that it streams the download of potentially very large files. As such, when proxying this
# view via nginx, there are certain nginx directives that must be enabled for the /export URI. And since we're serving
# Corpora via Daphne as an ASGI web app, to make this stream we must make use of async code; see here for explanation:
# https://docs.djangoproject.com/en/5.0/ref/request-response/#django.http.StreamingHttpResponse
@login_required
async def export(request, corpus_id, content_type):
    context = await sync_to_async(_get_context)(request)
    corpus, role = await sync_to_async(get_scholar_corpus)(corpus_id, context['scholar'])
    export_file_extension = 'json'
    csv_format = 'csv-format' in request.GET
    export_all = False
    export_ids = []
    contents = None

    if csv_format:
        export_file_extension = 'csv'

    if corpus:
        if context['search']:
            has_filtering_query = False
            filtering_parameters = [
                'fields_query',
                'fields_phrase',
                'fields_wildcard',
                'fields_filter',
                'fields_range',
                'fields_exist'
            ]
            if 'general_query' in context['search']:
                if context['search']['general_query'] != '*':
                    has_filtering_query = True
            for filtering_param in filtering_parameters:
                if filtering_param in context['search'] and context['search'][filtering_param]:
                    has_filtering_query = True

            if has_filtering_query:
                context['search']['page_size'] = 1000
                context['search']['page'] = 1
                context['search']['only'] = ['id']
                collect_results = True
                while collect_results:
                    results = await sync_to_async(corpus.search_content)(content_type, **context['search'])
                    if _contains(results, ['records', 'meta']):
                        export_ids += [r['id'] for r in results['records']]
                        if results['meta']['has_next_page']:
                            context['search']['page'] += 1
                            if results['meta']['next_page_token']:
                                context['search']['next_page_token'] = results['meta']['next_page_token']
                        else:
                            collect_results = False
                    else:
                        collect_results = False
            else:
                export_all = True

        elif 'content-ids' in request.GET:
            export_ids = request.GET['content-ids']
            export_ids = [export_id for export_id in export_ids.split(',') if export_id]

        if export_all:
            contents = await sync_to_async(corpus.get_content)(content_type, all=True)
            print('exporting all')
        elif export_ids:
            contents = await sync_to_async(corpus.get_content)(content_type, {'id__in': export_ids})
            print(f'exporting ids: {export_ids}')

        if contents:
            async def async_range(count):
                for i in range(count):
                    yield (i)
                    await asyncio.sleep(0.0)

            async def stream_exports(contents):
                try:
                    contents = await sync_to_async(contents.no_cache)()
                    contents = await sync_to_async(contents.batch_size)(10)
                    chunk_size = 1000
                    chunks = math.ceil(await sync_to_async(contents.count)() / chunk_size)
                    async for chunk in async_range(chunks):
                        start = chunk * chunk_size
                        end = start + chunk_size

                        content_slice = contents[start:end]
                        exported_content = ''

                        if csv_format:
                            exported_content = await sync_to_async(create_content_csv_rows)(content_slice)

                            if chunks == 1 or chunk == 0:
                                header_fields = [field.name for field in corpus.content_types[content_type].fields]
                                header_fields = ['id', 'label', 'uri'] + header_fields
                                header_row = f"{','.join(header_fields)}\n"
                                exported_content = f"{header_row}{exported_content}"

                            else:
                                exported_content = f"\n{exported_content}"

                        else:
                            exported_content = await sync_to_async(delimit_content_json)(content_slice)

                            if chunks > 1:
                                if chunk == 0:
                                    exported_content = '[' + exported_content + ', '
                                elif chunk == chunks - 1:
                                    exported_content = exported_content + ']'
                                else:
                                    exported_content = exported_content + ', '
                            else:
                                exported_content = '[' + exported_content + ']'

                        # asyncio.sleep(0)
                        yield exported_content
                except asyncio.CancelledError:
                    raise

            response = StreamingHttpResponse(stream_exports(contents))
            response['Content-Type'] = 'application/octet-stream'
            response['X-Accel-Buffering'] = 'no'
            response['Cache-Control'] = 'no-cache'
            response['Content-Disposition'] = f'attachment; filename="{content_type}.{export_file_extension}"'
            return response

    raise Http404("You are not authorized to view this page.")


@login_required
def backups(request):
    response = _get_context(request)

    if response['scholar'].is_admin:

        if request.method == 'POST':
            if _contains(request.POST, ['automated-backup-form-submission', 'automated-backup-corpus-id', 'automated-backup-status']):
                cba_corpus_id = _clean(request.POST, 'automated-backup-corpus-id')
                cba_status = _clean(request.POST, 'automated-backup-status')

                # make sure this is a valid corpus
                cba_corpus = get_corpus(cba_corpus_id, only=['name'])
                if cba_corpus:
                    # see if backup automation exists for this corpus
                    cba = None
                    try:
                        cba = CorpusBackupAutomation.objects.get(corpus_id=cba_corpus_id)
                    except:
                        cba = None

                    if cba:
                        if cba_status == 'disabled':
                            if cba.automated_backups:
                                delete_backups([ab.id for ab in cba.automated_backups])
                            cba.delete()
                            response['messages'].append(f'Automated backups for {cba_corpus.name} disabled.')

                        elif cba_status.isdigit():
                            num_to_retain = int(cba_status)
                            backups_to_delete = []
                            while len(cba.automated_backups) > num_to_retain:
                                backups_to_delete.append(cba.automated_backups.pop(0))
                            if backups_to_delete:
                                delete_backups([b.id for b in backups_to_delete])

                            cba.number_to_retain = num_to_retain
                            cba.save()
                            response['messages'].append(f'Will now retain {num_to_retain} automated backups for {cba_corpus.name}.')

                    elif cba_status.isdigit():
                        cba = CorpusBackupAutomation()
                        cba.corpus_id = cba_corpus_id
                        cba.number_to_retain = int(cba_status)
                        cba.save()
                        response['messages'].append(f'Will now retain {cba_status} automated backups for {cba_corpus.name}.')

            elif _contains(request.POST, ['backup-file-import', 'backup-upload-id']):
                upload_id = _clean(request.POST, 'backup-upload-id')
                temp_upload = TemporaryUpload.objects.get(upload_id=upload_id)
                temp_path = temp_upload.file.path

                corpora_backups_path = "/corpora/backups"
                os.makedirs(corpora_backups_path, exist_ok=True)

                new_path = f"{corpora_backups_path}/{temp_upload.upload_name.replace(' ', '_').replace('%20', '_')}"

                if os.path.exists(temp_path):
                    os.rename(temp_path, new_path)

                if os.path.exists(new_path):
                    backup_file = new_path
                    if backup_file:
                        if process_corpus_backup_file(backup_file):
                            response['messages'].append('Corpus backup file successfully imported.')
                        else:
                            response['errors'].append('An error occurred while importing this backup file!')
                            os.remove(new_path)

                temp_upload.delete()

            # HANDLE BACKUP ACTIONS
            backup_action = _clean(request.POST, 'backup-action')

            if backup_action == 'create' and _contains(request.POST, ['backup-corpus-id', 'backup-name']):
                backup_corpus_id = _clean(request.POST, 'backup-corpus-id')
                backup_name = _clean(request.POST, 'backup-name')
                backup = CorpusBackup.objects(corpus_id=backup_corpus_id, name=backup_name)

                if backup.count() > 0:
                    response['errors'].append('A backup with that name already exists for corpus {0}.'.format(backup_corpus_id))
                else:
                    corpus = get_corpus(backup_corpus_id)
                    job_id = corpus.queue_local_job(
                        task_name="Backup Corpus",
                        scholar_id=response['scholar'].id,
                        parameters={'backup_name': backup_name}
                    )
                    run_job(job_id)
                    response['messages'].append('Backup {0} successfully initiated!'.format(backup_name))

            elif 'backup-id' in request.POST:
                backup_id = _clean(request.POST, 'backup-id')
                backup = CorpusBackup.objects(id=backup_id)
                if backup.count() > 0:
                    backup = backup[0]

                    if backup_action == 'restore':
                        backup.status = 'restoring'
                        backup.save()
                        restore_corpus(str(backup.id))
                        response['messages'].append('Corpus restore successfully launched.')

                    elif backup_action == 'cancel':
                        backup.status = 'created'
                        backup.save()
                        response['messages'].append('Corpus restore cancelled.')

                    elif backup_action == 'delete':
                        try:
                            CorpusBackupAutomation.remove_backup(backup.id)
                            os.remove(backup.path)
                            backup.delete()
                            response['messages'].append('Backup successfully deleted.')
                        except:
                            print(traceback.format_exc())
                            response['errors'].append('An error occurred while deleting this backup file!')

        backups = CorpusBackup.objects.order_by('corpus_name', 'created')
        backups = [b.to_dict() for b in backups]

        backup_automations = CorpusBackupAutomation.objects.all()
        backup_automations = [ba.to_dict() for ba in backup_automations]

        return render(
            request,
            'backups.html',
            {
                'response': response,
                'backups': backups,
                'backup_automations': backup_automations,
            }
        )
    else:
        raise Http404("You are not authorized to view this page.")


@login_required
def download_backup(request, backup_id):
    response = _get_context(request)

    if response['scholar'].is_admin:
        backup = CorpusBackup.objects(id=backup_id)
        if backup.count() > 0:
            backup = backup[0]
            if os.path.exists(backup.path):
                response = HttpResponse(content_type="application/gzip")
                response['Content-Disposition'] = 'attachment; filename="{0}"'.format(os.path.basename(backup.path))
                response['X-Accel-Redirect'] = "/files/{0}".format(backup.path.replace('/corpora/', ''))
                return response
        print(f'{backup_id} not found')

    raise Http404("You are not authorized to view this page.")


@login_required
def download_export(request, corpus_id):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])

    if corpus and (response['scholar'].is_admin or role == 'Editor'):
        export_path = f"{corpus.path}/export.tar.gz"
        if os.path.exists(export_path):
            response = HttpResponse(content_type="application/gzip")
            response['Content-Disposition'] = 'attachment; filename="{0}"'.format(os.path.basename(export_path))
            response['X-Accel-Redirect'] = "/files/{0}".format(export_path.replace('/corpora/', ''))
            return response

    raise Http404("Export not found for this corpus, or you do not have permission to download it.")


@login_required
def scholars(request):
    response = _get_context(request)

    if response['scholar'].is_admin:
        if request.method == 'POST':
            if 'toggle-admin-privs' in request.POST:
                target_scholar = Scholar.objects(id=request.POST['toggle-admin-privs'])[0]
                if target_scholar.is_admin:
                    target_scholar.is_admin = False
                else:
                    target_scholar.is_admin = True
                target_scholar.save()
                response['messages'].append("Permissions for {0} successfully changed!".format(target_scholar.username))

            elif 'corpus-perms' in request.POST:
                target_scholar = Scholar.objects(id=request.POST['corpus-perms'])[0]
                new_perm_corpus_id = request.POST['corpus-id']
                new_perm_corpus_role = request.POST['corpus-permission']

                if new_perm_corpus_id != 'none' and new_perm_corpus_role in ['Viewer', 'Contributor', 'Editor']:
                    try:
                        corpus = Corpus.objects(id=new_perm_corpus_id)[0]
                        if str(corpus.id) not in target_scholar.available_corpora:
                            target_scholar.available_corpora[str(corpus.id)] = new_perm_corpus_role
                            target_scholar.save()
                    except:
                        response['errors'].append("No corpus was found with the name provided.")

                for post_param in request.POST.keys():
                    if post_param not in ['corpus-perms', 'corpus-id', 'corpus-permission'] and post_param.startswith('corpus-'):
                        corpus_id = post_param.replace('corpus-', '').replace('-permission', '')
                        corpus_role = request.POST[post_param]

                        if corpus_id in target_scholar.available_corpora and target_scholar.available_corpora[corpus_id] != corpus_role:
                            if corpus_role == 'None':
                                del target_scholar.available_corpora[corpus_id]
                            else:
                                target_scholar.available_corpora[corpus_id] = corpus_role

                            target_scholar.save()
                            response['messages'].append("Permissions for {0} successfully changed!".format(target_scholar.username))

            elif 'job-perms' in request.POST:
                target_scholar = Scholar.objects(id=request.POST['job-perms'])[0]
                target_scholar.available_jobsites = []
                target_scholar.available_tasks = []

                for post_param in request.POST.keys():
                    if post_param.startswith('jobsite-'):
                        jobsite_id = post_param.replace('jobsite-', '')
                        jobsite = JobSite.objects(id=jobsite_id)[0]
                        target_scholar.available_jobsites.append(jobsite)
                    elif post_param.startswith('task-'):
                        task_id = post_param.replace('task-', '')
                        task = Task.objects(id=task_id)[0]
                        target_scholar.available_tasks.append(task)

                target_scholar.save()
                response['messages'].append("Permissions for {0} successfully changed!".format(target_scholar.username))

            elif 'change-pwd' in request.POST:
                password = request.POST['password']

                if password == request.POST['password2']:
                    target_scholar = Scholar.objects(id=request.POST['change-pwd'])[0]
                    user = User.objects.get(username=target_scholar.username)
                    user.set_password(password)
                    user.save()
                    clear_cached_session_scholar(user.id)
                    response['messages'].append("Password for {0} successfully changed!".format(target_scholar.username))
                else:
                    response['errors'].append("Passwords must match!")

        return render(
            request,
            'scholars.html',
            {
                'response': response
            }
        )
    else:
        raise Http404("You are not authorized to view this page.")


def scholar(request):
    response = _get_context(request)
    register = False

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

    if request.method == 'POST' and _contains(request.POST, ['username', 'password', 'password2', 'fname', 'lname', 'email', 'captcha-check', 'captcha-word']):
        username = _clean(request.POST, 'username')
        password = _clean(request.POST, 'password')
        password2 = _clean(request.POST, 'password2')
        fname = _clean(request.POST, 'fname')
        lname = _clean(request.POST, 'lname')
        email = _clean(request.POST, 'email')
        captcha_hash = _clean(request.POST, 'captcha-check')
        captcha_word = _clean(request.POST, 'captcha-word')

        if validate_captcha(captcha_word, captcha_hash):
            if (register and not User.objects.filter(username=username).exists()) or (User.objects.filter(username=username).exists() and not register):

                valid_ips = True
                auth_token_ips = [request.POST[val] for val in request.POST.keys() if val.startswith('auth-token-ip-')]
                for auth_token_ip in auth_token_ips:
                    try:
                        ip = ip_address(auth_token_ip)
                    except:
                        valid_ips = False

                if valid_ips:
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
                            response['scholar'].auth_token_ips = auth_token_ips

                            token, created = Token.objects.get_or_create(user=user)
                            response['scholar'].auth_token = token.key
                            response['scholar'].save()
                            clear_cached_session_scholar(user.id)

                            return redirect("/scholar?msg=You have successfully registered. Please login below.")
                        else:
                            response['scholar'].fname = fname
                            response['scholar'].lname = lname
                            response['scholar'].email = email
                            response['scholar'].auth_token_ips = auth_token_ips
                            response['scholar'].save()

                            user = User.objects.get(username=username)
                            user.set_password(password)
                            user.save()
                            clear_cached_session_scholar(user.id)

                            response['messages'].append("Your account settings have been saved successfully.")
                    else:
                        response['errors'].append('You must provide a password, and passwords must match!')
                else:
                    response['errors'].append('One or more of your API IP addresses is invalid!')
            else:
                response['errors'].append('This username already exists!')
        else:
            response['errors'].append('Capcha word must match image!')

    elif request.method == 'POST' and _contains(request.POST, ['username', 'password']):
        username = _clean(request.POST, 'username')
        password = _clean(request.POST, 'password')
        user = authenticate(username=username, password=password)
        if user:
            if user.is_active:
                login(request, user)

                # make sure a scholar object exists for this user.
                # sometimes after a migration scholar data can be lost, especially if scholar data
                # was not exported (in case just individual corpora and user credentials were
                # migrated).
                if Scholar.objects(username=username).count() == 0:
                    s = Scholar()
                    s.username = username
                    s.fname = user.first_name
                    s.lname = user.last_name
                    s.email = user.email
                    s.auth_token_ips = []
                    token, created = Token.objects.get_or_create(user=user)
                    s.auth_token = token.key
                    s.save()

                if 'next' in request.GET:
                    return redirect(request.GET['next'])
                else:
                    return redirect("/")
            else:
                response['errors'].append('Account disabled!')
        else:
            response['errors'].append('Invalid credentials provided!')

    captcha_image, captcha_hash = generate_captcha()

    return render(
        request,
        'scholar.html',
        {
            'response': response,
            'register': register,
            'captcha_image': captcha_image,
            'captcha_hash': captcha_hash
        }
    )


def get_file(request, file_uri):
    context = _get_context(request)
    file_uri = file_uri.replace('|', '/')
    uri_dict = parse_uri(file_uri)
    file_path = None

    if 'corpus' in uri_dict:
        if (
                context['scholar'] and (
                context['scholar'].is_admin
                or uri_dict['corpus'] in context['scholar'].available_corpora.keys())
        ) or uri_dict['corpus'] in get_open_access_corpora():
            results = run_neo(
                '''
                    MATCH (f:_File { uri: $file_uri })
                    return f.path as file_path
                ''',
                {
                    'file_uri': file_uri
                }
            )

            if results and 'file_path' in results[0].keys():
                file_path = results[0]['file_path']

    if file_path:
        mime_type = None
        explicit_mime_types = {
            'hocr': 'application/xml'
        }

        lowered_extension = file_path.split('.')[-1].lower()
        mime_type = explicit_mime_types.get(lowered_extension, None)

        if not mime_type:
            mime_type, encoding = mimetypes.guess_type(file_path)

        response = HttpResponse(content_type=mime_type)
        response['X-Accel-Redirect'] = "/files/{0}".format(file_path.replace('/corpora/', ''))
        return response

    raise Http404("File not found.")


def get_repo_file(request, corpus_id, repo_name):
    context = _get_context(request)
    if 'path' in request.GET:
        file_path = None

        if (
            context['scholar'] and (
            context['scholar'].is_admin
            or corpus_id in context['scholar'].available_corpora.keys())
        ) or corpus_id in get_open_access_corpora():
            corpus = get_corpus(corpus_id)
            if repo_name in corpus.repos:
                file_path = os.path.join(corpus.repos[repo_name].path, _clean(request.GET, 'path'))
                file_path = file_path.replace('../', '').replace('.git/', '')
                if not os.path.exists(file_path):
                    file_path = None

        if file_path:
            mime_type = None
            explicit_mime_types = {
                'hocr': 'application/xml'
            }

            lowered_extension = file_path.split('.')[-1].lower()
            mime_type = explicit_mime_types.get(lowered_extension, None)

            if not mime_type:
                mime_type, encoding = mimetypes.guess_type(file_path)

            response = HttpResponse(content_type=mime_type)
            response['X-Accel-Redirect'] = "/files/{0}".format(file_path.replace('/corpora/', ''))
            return response

    raise Http404("File not found.")


@login_required
def get_corpus_file(request, corpus_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    path = request.GET.get('path', None)

    if corpus:
        file_path = "{0}/files/{1}".format(corpus.path, path)
        path_exists = False
        if os.path.exists(file_path):
            path_exists = True
        else:
            file_path = "{0}/{1}".format(corpus.path, path)
            if os.path.exists(file_path):
                path_exists = True

        if path_exists:
            mime_type, encoding = mimetypes.guess_type(file_path)
            response = HttpResponse(content_type=mime_type)
            response['X-Accel-Redirect'] = "/files/{0}".format(file_path.replace('/corpora/', ''))
            return response

    raise Http404("File not found.")


def get_corpus_event_dispatcher(request, corpus_id):
    return render(
        request,
        'corpus_worker.js',
        {
            'corpus_id': corpus_id
        },
        content_type='application/javascript'
    )


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
    is_external = False

    req_type = request.META.get('HTTP_ACCEPT', 'none')

    if 'corpus' in uri_dict:
        if (context['scholar'] and (context['scholar'].is_admin or uri_dict['corpus'] in context['scholar'].available_corpora.keys())) or uri_dict['corpus'] in get_open_access_corpora():
            results = run_neo(
                '''
                    MATCH (f:_File { uri: $image_uri, is_image: true })
                    return f.path as file_path, f.external as external
                ''',
                {
                    'image_uri': image_uri
                }
            )

            if results and _contains(results[0].keys(), ['file_path', 'external']):
                file_path = results[0]['file_path']
                is_external = results[0]['external']

    if file_path:
        if is_external:
            return redirect("{iiif_id}/{region}/{size}/{rotation}/{quality}.{format}".format(
                iiif_id=file_path,
                region=region,
                size=size,
                rotation=rotation,
                quality=quality,
                format=format
            ))

        elif req_type == '*/*' or request.build_absolute_uri().endswith('/info.json'):
            response = HttpResponse(content_type='application/json')
            response['X-Accel-Redirect'] = "/media/{identifier}/info.json".format(
                identifier=file_path[1:].replace('/', '$!$'),
            )
            return response
        else:
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


def iiif_passthrough(request, req_path):
    context = _get_context(request)

    if req_path.endswith('/info.json'):
        req_path_parts = req_path.split('/')
        file_path = "/".join(req_path_parts[:-1])
        iiif_identifier = "$!$".join(req_path_parts[:-1])
        response = HttpResponse(content_type='application/json')
        response['X-Accel-Redirect'] = f"/media/{iiif_identifier}/info.json"
        return response

    req_path_parts = req_path.split('/')
    file_path = "/".join(req_path_parts[:-4])
    iiif_identifier = "$!$".join(req_path_parts[:-4])
    internal_req_path = "{0}/{1}".format(
        iiif_identifier,
        "/".join(req_path_parts[-4:])
    )

    mime_type, encoding = mimetypes.guess_type(file_path)
    response = HttpResponse(content_type=mime_type)
    response['X-Accel-Redirect'] = "/media/{internal_req_path}".format(
        internal_req_path=internal_req_path
    )
    return response


@api_view(['GET'])
def api_corpora(request):
    context = _get_context(request)
    ids = []
    open_access_only = True

    if not context['search']:
        context['search'] = {
            'general_query': "*",
            'page': 1,
            'page_size': 100,
        }

    if context['scholar'] and context['scholar'].is_admin:
        open_access_only = False
    elif context['scholar']:
        ids = [c_id for c_id in context['scholar'].available_corpora.keys()]

    corpora = search_corpora(context['search'], ids=ids, open_access_only=open_access_only)

    return HttpResponse(
        json.dumps(corpora),
        content_type='application/json'
    )


@api_view(['GET'])
def api_scholar(request, scholar_id=None):
    context = _get_context(request)

    if not context['search']:
        context['search'] = {
            'general_query': "*",
            'page': 1,
            'page-size': 50
        }

    if context['scholar'] and context['scholar'].is_admin:
        if scholar_id:
            scholar = Scholar.objects(id=scholar_id)[0]

            return HttpResponse(
                json.dumps(scholar.to_dict()),
                content_type='application/json'
            )

        else:
            scholars = search_scholars(context['search'])

            return HttpResponse(
                json.dumps(scholars),
                content_type='application/json'
            )
    elif context['scholar'] and str(context['scholar'].id) == scholar_id:
        return HttpResponse(
            json.dumps(context['scholar'].to_dict()),
            content_type='application/json'
        )
    else:
        raise Http404("You are not authorized to access this endpoint.")


@api_view(['GET'])
def api_corpus(request, corpus_id):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])

    if corpus:
        include_views = 'include-views' in request.GET
        corpus_dict = corpus.to_dict(include_views)
        corpus_dict['scholar_role'] = role
        corpus_dict['available_synonyms'] = settings.ES_SYNONYM_OPTIONS

        return HttpResponse(
            json.dumps(corpus_dict),
            content_type='application/json'
        )
    else:
        return JsonResponse({
            'error_message': "Corpus not found!"
        }, status=404)


@api_view(['GET'])
def api_content(request, corpus_id, content_type, content_id=None):
    context = _get_context(request)
    content = {}
    render_template = _clean(request.GET, 'render_template', None)

    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and content_type in corpus.content_types:
        if content_id:
            content = corpus.get_content(content_type, content_id, context['only'])

            if render_template and render_template in corpus.content_types[content_type].templates:
                if content.id:
                    django_template = Template(corpus.content_types[content_type].templates[render_template].template)
                    context = Context({content_type: content})

                    return HttpResponse(
                        django_template.render(context),
                        content_type=corpus.content_types[content_type].templates[render_template].mime_type
                    )

            content = content.to_dict()
        else:
            if context['search']:
                content = corpus.search_content(content_type=content_type, **context['search'])
            else:
                content = corpus.search_content(content_type=content_type, general_query="*")

    return HttpResponse(
        json.dumps(content),
        content_type='application/json'
    )


@api_view(['GET'])
def api_suggest(request, corpus_id, content_type):
    context = _get_context(request)
    suggestions = {}
    query = _clean(request.GET, 'q', None)

    if query:
        corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
        fields = _clean(request.GET, 'fields', [])
        max_per_field = _clean(request.GET, 'max_per_field', '5')
        es_debug = 'es_debug' in request.GET

        if fields:
            fields = fields.split(',')

        filters = {}
        filter_params = [param for param in request.GET if param.startswith('f_')]
        if filter_params:
            for filter_param in filter_params:
                filters[filter_param[2:]] = _clean(request.GET, filter_param)

        if corpus and content_type in corpus.content_types and max_per_field.isdigit():
            suggestions = corpus.suggest_content(content_type, query, fields, int(max_per_field), filters, es_debug)

    return HttpResponse(
        json.dumps(suggestions),
        content_type='application/json'
    )


@api_view(['GET', 'POST'])
def api_content_view(request, corpus_id, content_view_id=None):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    cv = None

    if corpus:
        cv_dict = {}
        if content_view_id:
            cv = ContentView.objects.get(id=content_view_id)
            cv_dict = cv.to_dict()

        if request.method == 'POST' and scholar_has_privilege('Editor', role):
            if _contains(request.POST, ['cv-name', 'cv-target-ct', 'cv-search-json', 'cv-patass']):
                cv_search_params = json.loads(unescape(_clean(request.POST, 'cv-search-json')))
                cv_search_params = build_search_params_from_dict(cv_search_params)

                cv = ContentView()
                cv.name = _clean(request.POST, 'cv-name')
                cv.corpus = corpus
                cv.target_ct = _clean(request.POST, 'cv-target-ct')
                cv.search_filter = json.dumps(cv_search_params)
                cv.graph_path = _clean(request.POST, 'cv-patass').replace('&lt;', '<').replace('&gt;', '>')
                cv.set_status('populating')
                cv.save()
                cv_dict = cv.to_dict()

                run_job(corpus.queue_local_job(task_name="Content View Lifecycle", parameters={
                    'cv_id': str(cv.id),
                    'stage': 'populate',
                }))

            elif cv and 'cv-action' in request.POST:
                action = _clean(request.POST, 'cv-action')

                if action == 'refresh':
                    cv.status = 'populating'
                    cv.save()
                    cv_dict = cv.to_dict()

                    run_job(corpus.queue_local_job(task_name="Content View Lifecycle", parameters={
                        'cv_id': str(cv.id),
                        'stage': 'refresh',
                    }))

        return HttpResponse(
            json.dumps(cv_dict),
            content_type='application/json'
        )


@api_view(['GET', 'POST'])
def api_content_group(request, corpus_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and request.method == 'POST' and (context['scholar'].is_admin or role == 'Editor'):
        if _contains(request.POST, ['content-group-json', 'action']):
            content_group_dict = json.loads(unescape(_clean(request.POST, 'content-group-json')))
            existing_titles = []
            existing_members = []
            for ctg in corpus.content_type_groups:
                existing_titles.append(ctg.title)
                for member in ctg.members:
                    existing_members.append(member.name)

            action = _clean(request.POST, 'action')

            if action == 'create':
                if content_group_dict['title'] and content_group_dict['title'] not in existing_titles:
                    for member in content_group_dict['members']:
                        if member['name'] in existing_members:
                            return HttpResponse(
                                json.dumps({'success': False, 'message': 'Content types can only belong to one content group at a time.'}),
                                content_type='application/json'
                            )

                    ct_group = ContentTypeGroup()
                    ct_group.title = content_group_dict['title']
                    if content_group_dict['description']:
                        ct_group.description = content_group_dict['description']

                    for member in content_group_dict['members']:
                        ctg_member = ContentTypeGroupMember()
                        ctg_member.name = member['name']
                        ctg_member.display_preference = member['display_preference']
                        ct_group.members.append(ctg_member)

                    corpus.content_type_groups.append(ct_group)
                    corpus.save()
                else:
                    return HttpResponse(
                        json.dumps({'success': False, 'message': 'Title blank or not unique.'}),
                        content_type='application/json'
                    )

            elif action in ['edit', 'delete']:
                ct_group_index = -1
                for index in range(0, len(corpus.content_type_groups)):
                    if corpus.content_type_groups[index].title == content_group_dict['title']:
                        ct_group_index = index

                if action == 'edit' and ct_group_index > -1:
                    members_currently_in_relevant_group = [m.name for m in corpus.content_type_groups[ct_group_index].members]
                    existing_members = [m for m in existing_members if m not in members_currently_in_relevant_group]

                    corpus.content_type_groups[ct_group_index].description = content_group_dict['description']
                    corpus.content_type_groups[ct_group_index].members = []
                    for member in content_group_dict['members']:
                        if member['name'] not in existing_members:
                            ctg_member = ContentTypeGroupMember()
                            ctg_member.name = member['name']
                            ctg_member.display_preference = member['display_preference']
                            corpus.content_type_groups[ct_group_index].members.append(ctg_member)

                    corpus.save()

                elif action == 'delete' and ct_group_index > -1:
                    corpus.content_type_groups.pop(ct_group_index)
                    corpus.save()


    return HttpResponse(
        json.dumps({'success': True}),
        content_type='application/json'
    )


@api_view(['GET'])
def api_plugin_schema(request):
    context = _get_context(request)
    schema = []

    if (context['scholar']):
        plugins = [app for app in settings.INSTALLED_APPS if app.startswith('plugins.')]
        for plugin in plugins:
            plugin_name = plugin.split('.')[1]
            if os.path.exists("{0}/plugins/{1}/content.py".format(settings.BASE_DIR, plugin_name)):
                content_module = importlib.import_module(plugin + '.content')
                if hasattr(content_module, 'REGISTRY'):
                    schema.append({
                        'plugin': plugin_name,
                        'content_types': getattr(content_module, 'REGISTRY')
                    })

    return HttpResponse(
        json.dumps(schema),
        content_type='application/json'
    )


@api_view(['GET'])
def api_network_json(request, corpus_id, content_type, content_id):
    context = _get_context(request)
    per_type_limit = int(request.GET.get('per_type_limit', '20'))
    per_type_skip = int(request.GET.get('per_type_skip', '0'))
    meta_only = 'meta-only' in request.GET
    is_seed = 'is-seed' in request.GET
    target_ct = request.GET.get('target-ct', '')
    network_json = {
        'nodes': [],
        'edges': [],
        'meta': {}
    }
    filters = {}
    collapses = []
    excluded_cts = []

    if 'filters' in request.GET:
        filter_specs = request.GET['filters'].split(',')
        for filter_spec in filter_specs:
            if ':' in filter_spec:
                filters[filter_spec.split(':')[0]] = filter_spec.split(':')[1]

    if 'collapses' in request.GET:
        collapse_params = request.GET['collapses'].split(',')
        for collapse_param in collapse_params:
            collapse_parts = collapse_param.split('-')
            from_ct = collapse_parts[0]
            proxy_ct = collapse_parts[1]
            to_ct = collapse_parts[2]

            if '.' in proxy_ct:
                proxy_cts = proxy_ct.split('.')
                for p in proxy_cts:
                    excluded_cts.append(p)
            else:
                excluded_cts.append(proxy_ct)

            if from_ct == content_type:
                collapses.append({
                    'from_ct': from_ct,
                    'proxy_ct': proxy_ct,
                    'to_ct': to_ct
                })
            elif to_ct == content_type:
                collapses.append({
                    'from_ct': to_ct,
                    'proxy_ct': proxy_ct,
                    'to_ct': from_ct
                })

    if 'hidden' in request.GET:
        excluded_cts += request.GET['hidden'].split(',')

    excluded_cts = list(set(excluded_cts))

    exclusion_clause = ""
    for excluded_ct in excluded_cts:
        exclusion_clause += '''
            AND NOT a:{0}
            AND NOT c:{0}
        '''.format(excluded_ct)

    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and content_type in corpus.content_types:
        content_uri = '/corpus/{0}/{1}/{2}'.format(
            corpus_id,
            content_type,
            content_id
        )

        distinct_relationships = run_neo(
            '''
                MATCH (a:{origin}) -[b]- (c)
                WHERE a.uri = '{uri}'
                AND ANY(l in labels(c) WHERE NOT l STARTS WITH '_') {exclusions}
                RETURN distinct type(b) as REL, labels(c) as CT, count(labels(c)) as COUNT
            '''.format(
                    origin=content_type,
                    uri=content_uri,
                    exclusions=exclusion_clause
                 )
            , {}
        )

        for relationship in distinct_relationships:
            if not meta_only and (not target_ct or target_ct == relationship.get('CT')[0]):
                filter_clause = ''
                if content_type in filters:
                    filter_clause += " AND (a) <-[:hasContent]- (:`_ContentView` {{ uri: '{0}' }})".format(filters[content_type])
                if relationship.get('CT')[0] in filters:
                    filter_clause += " AND (c) <-[:hasContent]- (:`_ContentView` {{ uri: '{0}' }})".format(filters[relationship.get('CT')[0]])

                rel_net_json = get_network_json(
                    '''
                        MATCH path = (a:{origin}) -[b:{relationship}]- (c:{destination})
                        WHERE a.uri = '{uri}' {exclusions}{filters} 
                        RETURN path
                        SKIP {skip}
                        LIMIT {limit}
                    '''.format(
                        origin=content_type,
                        relationship=relationship.get('REL'),
                        destination=relationship.get('CT')[0],
                        uri=content_uri,
                        exclusions=exclusion_clause,
                        filters=filter_clause,
                        skip=per_type_skip,
                        limit=per_type_limit
                    )
                )

                node_uris = [n['id'] for n in network_json['nodes']]
                network_json['nodes'] += [n for n in rel_net_json['nodes'] if n['id'] not in node_uris]
                network_json['edges'] += rel_net_json['edges']

            path_key = "{0}-{1}".format(relationship.get('REL'), relationship.get('CT')[0])
            network_json['meta'][path_key] = {
                'count': relationship.get('COUNT'),
                'skip': per_type_skip,
                'limit': per_type_limit,
                'collapsed': False
            }

        node_uris = [n['id'] for n in network_json['nodes']]

        for collapse in collapses:
            filter_clause = ''
            if collapse['from_ct'] in filters:
                filter_clause += " AND (a) <-[:hasContent]- (:`_ContentView` {{ uri: '{0}' }})".format(filters[collapse['from_ct']])
            if collapse['to_ct'] in filters:
                filter_clause += " AND (c) <-[:hasContent]- (:`_ContentView` {{ uri: '{0}' }})".format(filters[collapse['to_ct']])

            path_key = "{0}-{1}-{2}".format(
                collapse['from_ct'],
                collapse['proxy_ct'],
                collapse['to_ct']
            )
            proxy_path = []
            proxy_cts = collapse['proxy_ct'].split('.')
            for proxy_index in range(0, len(proxy_cts)):
                proxy_path.append("(b{0}:{1})".format(proxy_index, proxy_cts[proxy_index]))
            proxy_path = " -- ".join(proxy_path)

            proxied_cypher = '''
                MATCH path = (a:{origin}) -- {proxy_path} -- (c:{destination})
                WHERE a.uri = '{uri}' {exclusions}{filters}
            '''.format(
                origin=collapse['from_ct'],
                proxy_path=proxy_path,
                destination=collapse['to_ct'],
                uri=content_uri,
                exclusions=exclusion_clause,
                filters=filter_clause
            )

            proxied_count = run_neo('''
                {proxied_cypher}
                RETURN count(path) as COUNT
            '''.format(proxied_cypher=proxied_cypher), {})

            network_json['meta'][path_key] = {
                'count': proxied_count[0].get('COUNT'),
                'skip': per_type_skip,
                'limit': per_type_limit,
                'collapsed': True
            }

            if not meta_only and (not target_ct or target_ct == collapse['to_ct']):
                proxied_content = run_neo('''
                    {proxied_cypher}
                    RETURN distinct c, count(path) as freq
                    SKIP {skip}
                    LIMIT {limit}
                '''.format(
                    proxied_cypher=proxied_cypher,
                    skip=per_type_skip,
                    limit=per_type_limit
                ), {})

                for result in proxied_content:
                    uri = result.get('c').get('uri')
                    freq = result.get('freq')
                    if uri not in node_uris:
                        network_json['nodes'].append({
                            'group': collapse['to_ct'],
                            'id': uri,
                            'label': result.get('c').get('label')
                        })
                        node_uris.append(uri)
                        network_json['edges'].append(
                            {
                                'from': content_uri,
                                'id': content_uri + '-' + uri,
                                'title': 'has{0}via{1}'.format(collapse['to_ct'], collapse['proxy_ct']),
                                'to': uri,
                                'freq': freq
                            }
                        )

        if is_seed and content_uri not in node_uris:
            seed = run_neo('''
                MATCH (a:{content_type})
                WHERE a.uri = '{uri}'
                RETURN a
            '''.format(content_type=content_type, uri=content_uri), {})
            if seed:
                network_json['nodes'].append({
                    'id': content_uri,
                    'group': content_type,
                    'label': seed[0].get('a').get('label')
                })

    return HttpResponse(
        json.dumps(network_json),
        content_type='application/json'
    )


@api_view(['GET', 'POST'])
def api_content_files(request, corpus_id, content_type=None, content_id=None):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    files = []

    if (context['scholar'].is_admin or role == 'Editor') and corpus:

        if content_type:
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
        else:
            base_path = "{0}/files".format(corpus.path)

        if base_path:
            sub_path = _clean(request.GET, 'path', '')
            full_path = base_path + sub_path
            filter = _clean(request.GET, 'filter', '')

            # HANDLE UPLOADS
            if 'filepond' in request.FILES:
                filename = re.sub(r'[^a-zA-Z0-9\\.\\-]', '_', request.FILES['filepond'].name)
                file_path = "{0}/{1}".format(full_path, filename)

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
        fix_mongo_json(jobsites.to_json()),
        content_type='application/json'
    )


@api_view(['GET'])
def api_tasks(request, content_type=None):
    context = _get_context(request)
    response_content = '[]'

    tasks = get_tasks(context['scholar'], content_type=content_type)

    if tasks:
        response_content = fix_mongo_json(tasks.to_json())

    return HttpResponse(
        response_content,
        content_type='application/json'
    )


@api_view(['GET'])
def api_job(request, corpus_id=None, job_id=None):
    if corpus_id and job_id:
        context = _get_context(request)
        corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
        if corpus:
            job = Job(job_id)
            if job:
                return HttpResponse(
                    json.dumps(job.to_dict()),
                    content_type='application/json'
                )

    return Http404("Job not found.")


@api_view(['GET'])
def api_jobs(request, corpus_id=None, content_type=None, content_id=None):
    context = _get_context(request)
    payload = {
        'meta': {
            'counts': { 'total': 0, 'by_status': {}, 'by_task': {} },
            'page': int(_clean(request.GET, 'page', '1')),
            'page_size': int(_clean(request.GET, 'page-size', '50')),
            'num_pages': 0,
            'has_next_page': False
        },
        'records': []
    }
    limit = payload['meta']['page_size']
    skip = payload['meta']['page_size'] * (payload['meta']['page'] - 1)
    results = []
    detailed = 'detailed' in request.GET
    cached_jobsites = {}
    cached_tasks = {}

    if not corpus_id and context['scholar'] and context['scholar'].is_admin:
        payload['meta']['counts'] = Job.get_jobs(count_only=True)
        results = Job.get_jobs(
            limit=limit,
            skip=skip
        )

    elif corpus_id:
        corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
        if corpus:
            payload['meta']['counts'] = Job.get_jobs(
                corpus_id=corpus_id,
                content_type=content_type,
                content_id=content_id,
                count_only=True)
            results = Job.get_jobs(
                corpus_id=corpus_id,
                content_type=content_type,
                content_id=content_id,
                limit=limit,
                skip=skip
            )

    if payload['meta']['page'] * payload['meta']['page_size'] < payload['meta']['counts']['total']:
        payload['meta']['has_next_page'] = True

    for job in results:
        job_dict = job.to_dict()
        if detailed:
            if job.jobsite_id not in cached_jobsites:
                cached_jobsites[job.jobsite_id] = job.jobsite

            job_dict['jobsite_name'] = cached_jobsites[job.jobsite_id].name
            job_dict['jobsite_type'] = cached_jobsites[job.jobsite_id].type

            if job.task_id not in cached_tasks:
                cached_tasks[job.task_id] = job.task

            job_dict['task_name'] = cached_tasks[job.task_id].name
            job_dict['task_version'] = cached_tasks[job.task_id].version

        payload['records'].append(job_dict)

    return HttpResponse(
        json.dumps(payload),
        content_type='application/json'
    )


@api_view(['POST'])
def api_submit_jobs(request, corpus_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and scholar_has_privilege('Editor', role):
        if 'job-submissions' in request.POST:
            job_submissions = json.loads(request.POST['job-submissions'])
            for job_submission in job_submissions:
                if _contains(job_submission, ['jobsite_id', 'task_id', 'parameters', 'content_type', 'content_id']):
                    try:
                        jobsite = JobSite.objects(id=job_submission['jobsite_id'])[0]
                        task = Task.objects(id=job_submission['task_id'])[0]

                        job = Job()
                        job.corpus = corpus
                        job.content_type = job_submission['content_type']
                        job.content_id = job_submission['content_id']
                        job.task_id = str(task.id)
                        job.scholar = context['scholar']
                        job.jobsite = jobsite
                        job.configuration = deepcopy(task.configuration)

                        for param in task.configuration['parameters'].keys():
                            if param in job_submission['parameters']:
                                job.configuration['parameters'][param]['value'] = job_submission['parameters'][param]

                        job.save()
                        run_job(job.id)
                        send_alert(corpus_id, 'success', f'Job submitted: {task.name}')
                    except:
                        print(traceback.format_exc())
                        send_alert(corpus_id, 'error', "Error submitting job!")

        elif _contains(request.POST, ['retry-job-id', 'retry-content-type']):
            retried = False
            job_id = _clean(request.POST, 'retry-job-id').strip()
            content_type = _clean(request.POST, 'retry-content-type').strip()
            content_id = _clean(request.POST, 'retry-content-id', None)
            content = None

            if content_type == 'Corpus':
                content = corpus
            elif content_id:
                content = corpus.get_content(content_type, content_id.strip())

            if content:
                for prov in content.provenance:
                    if prov.job_id == job_id:
                        job = Job.setup_retry_for_completed_task(corpus, context['scholar'], content_type, content_id, prov)
                        content.modify(pull__provenance=prov)
                        run_job(job.id)
                        send_alert(corpus_id, 'success', f'Task {prov.task_name} successfully retried.')
                        retried = True

            if not retried:
                send_alert(corpus_id, 'error', "Error retrying job!")

    return HttpResponse(status=204)


@api_view(['GET', 'POST'])
def api_scholar_preference(request, content_type, preference):
    context = _get_context(request)
    value = None

    if request.method == 'GET' and 'content_uri' in request.GET:
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


@api_view(['GET'])
def api_publish(request, corpus_id, event_type):
    data = {
        'event_type': event_type
    }
    for param in request.GET.keys():
        data[param] = request.GET[param]

    if data:
        send_event(corpus_id, 'event', data)

    return HttpResponse(status=204)

