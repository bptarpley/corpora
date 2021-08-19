import re
import subprocess
import mimetypes
from ipaddress import ip_address
from django.shortcuts import render, redirect, HttpResponse
from django.http import Http404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.management import call_command
from html import unescape
from time import sleep
from corpus import *
from .tasks import *
from .utilities import(
    _get_context,
    _clean,
    _contains,
    build_search_params_from_dict,
    get_scholar_corpus,
    get_open_access_corpora,
    parse_uri,
    get_jobsites,
    get_tasks,
    clear_cached_session_scholar
)
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
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])
    if corpus:
        # HANDLE ADMIN ONLY POST REQUESTS
        if (response['scholar'].is_admin or role == 'Editor') and request.method == 'POST':

            # HANDLE IMPORT DOCUMENT FILES FORM SUBMISSION
            if 'import-corpus-files' in request.POST:
                import_files = json.loads(request.POST['import-corpus-files'])
                upload_path = corpus.path + '/files'

                for import_file in import_files:
                    import_file_path = "{0}{1}".format(upload_path, import_file)
                    fixed_basename = re.sub(r'[^a-zA-Z0-9\\.\\-]', '_', os.path.basename(import_file_path))
                    import_file_path = "{0}/{1}".format(os.path.dirname(import_file_path), fixed_basename)

                    print(import_file_path)
                    if os.path.exists(import_file_path):
                        extension = import_file.split('.')[-1]
                        corpus.save_file(File.process(
                            import_file_path,
                            extension.upper() + " File",
                            "User Import",
                            response['scholar']['username'],
                            False
                        ))

            # HANDLE NEW REPO SUBMISSION
            if _contains(request.POST, ['new-repo-name', 'new-repo-url', 'new-repo-branch']):
                repo = GitRepo()
                repo.name = _clean(request.POST, 'new-repo-name')
                repo.remote_url = _clean(request.POST, 'new-repo-url')
                repo.remote_branch = _clean(request.POST, 'new-repo-branch')

                if repo.name and repo.remote_url and repo.remote_branch:
                    repo.path = "{0}/{1}/{2}".format(corpus.path, 'repos', repo.name)

                    if repo.name not in corpus.repos and not os.path.exists(repo.path):
                        corpus.repos[repo.name] = repo
                        corpus.save()
                        run_job(corpus.queue_local_job(task_name="Pull Corpus Repo", parameters={
                            'repo_name': repo.name,
                        }))
                        response['messages'].append('Repository "{0}" successfully added to this corpus.'.format(repo.name))
                    else:
                        response['errors'].append('A repository with that name already exists in this corpus!')
                else:
                    response['errors'].append("Please provide values for the repository's name, URL, and branch.")

            # HANDLE CONTENT DELETION
            elif _contains(request.POST, ['deletion-confirmed', 'content-type', 'content-ids']):
                deletion_ct = _clean(request.POST, 'content-type')
                deletion_ids = _clean(request.POST, 'content-ids')
                deletion_ids = [d_id for d_id in deletion_ids.split(',') if d_id]

                if deletion_ct in corpus.content_types:
                    deleted = []
                    for deletion_id in deletion_ids:
                        try:
                            to_delete = corpus.get_content(deletion_ct, deletion_id)
                            to_delete.delete()
                            deleted.append(deletion_id)
                        except:
                            response['errors'].append("An error occurred when attempting to delete {0} with ID {1}!".format(deletion_ct, deletion_id))
                            print(traceback.format_exc())

                    if deleted:
                        response['messages'].append("The following {0} were successfully deleted:<br><br>{1}".format(
                            corpus.content_types[deletion_ct].plural_name,
                            '<br>'.join(deleted)
                        ))

            # HANDLE JOB SUBMISSION
            elif _contains(request.POST, ['jobsite', 'task']):
                jobsite = JobSite.objects(id=_clean(request.POST, 'jobsite'))[0]
                task = Task.objects(id=_clean(request.POST, 'task'))[0]
                task_parameters = [key for key in task.configuration['parameters'].keys() if task.configuration['parameters'][key]['type'] != 'boolean']
                if _contains(request.POST, task_parameters):
                    job = Job()
                    job.corpus_id = corpus_id
                    job.content_type = 'Corpus'
                    job.content_id = None
                    job.task_id = str(task.id)
                    job.scholar_id = str(response['scholar'].id)
                    job.jobsite_id = str(jobsite.id)
                    job.status = "preparing"
                    job.configuration = task.configuration

                    for parameter in task_parameters:
                        job.configuration['parameters'][parameter]['value'] = unescape(_clean(request.POST, parameter))

                    for bool_parameter in [key for key in task.configuration['parameters'].keys() if task.configuration['parameters'][key]['type'] == 'boolean']:
                        job.configuration['parameters'][bool_parameter]['value'] = bool_parameter in request.POST

                    job.save()
                    run_job(job.id)
                    response['messages'].append("Job successfully submitted.")
                else:
                    response['errors'].append("Please provide values for all task parameters.")

            # HANDLE JOB RETRY
            elif _contains(request.POST, ['retry-job-id']):
                retry_job_id = _clean(request.POST, 'retry-job-id')
                for completed_task in corpus.provenance:
                    if completed_task.job_id == retry_job_id:
                        job = Job.setup_retry_for_completed_task(corpus_id, 'Corpus', None, completed_task)
                        corpus.modify(pull__provenance=completed_task)
                        run_job(job.id)

            # HANDLE JOB KILL
            elif _contains(request.POST, ['kill-job-id']):
                kill_job_id = _clean(request.POST, 'kill-job-id')
                job = Job(kill_job_id)
                job.kill()

            # HANDLE VIEW CREATION
            elif 'create-view' in request.POST:
                new_view = json.loads(request.POST['create-view'])
                exploration = corpus.make_exploration(**new_view)
                print(exploration)
                if exploration['status'] == 'performing':
                    run_job(exploration['job'])
                    response['messages'].append("View successfully created.")

            # HANDLE CONTENT TYPE SCHEMA SUBMISSION
            elif 'schema' in request.POST:
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

            # HANDLE NOTEBOOK LAUNCH
            elif 'launch-notebook' in request.POST:
                if corpus.path:
                    running_notebooks = subprocess.check_output("jupyter notebook list".split()).decode('utf-8')
                    if '0.0.0.0:9999' in running_notebooks:
                        subprocess.Popen("jupyter notebook stop 9999".split())
                        sleep(2)

                    notebook_path = "{0}/corpus_notebook.ipynb".format(corpus.path)
                    jupyter_token = "{0}{1}".format(corpus_id, response['scholar'].id)
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
                        'jupyter', 'notebook',
                        notebook_path,
                        '--ip', '0.0.0.0',
                        '--port', '9999',
                        '--no-browser',
                        '--NotebookApp.base_url="/notebook/"',
                        '--NotebookApp.token="{0}"'.format(jupyter_token),
                        '--NotebookApp.notebook_dir="/corpora/{0}"'.format(corpus_id),
                        '--NotebookApp.allow_origin="*"'
                    ])

                    response['messages'].append("Notebook server successfully launched! Access your notebook <a href='{0}' target='_blank'>here</a>.".format(notebook_url))

            # HANDLE CORPUS DELETION
            elif 'corpus-deletion-name' in request.POST:
                if corpus.name == request.POST['corpus-deletion-name']:
                    run_job(corpus.queue_local_job(task_name="Delete Corpus", parameters={}))

                    return redirect("/?msg=Corpus {0} is being deleted.".format(
                        corpus.name
                    ))

        # HANDLE SCHEMA EXPORT
        elif request.method == 'GET' and 'export' in request.GET and request.GET['export'] == 'schema':
            schema = []
            for ct_name in corpus.content_types.keys():
                schema.append(corpus.content_types[ct_name].to_dict())

            return HttpResponse(
                json.dumps(schema, indent=4),
                content_type='application/json'
            )

    return render(
        request,
        'corpus.html',
        {
            'corpus_id': corpus_id,
            'role': role,
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

    if (context['scholar'].is_admin or role == 'Editor') and corpus and content_type in corpus.content_types:
        if corpus.content_types[content_type].edit_widget_url:
            edit_widget_url = corpus.content_types[content_type].edit_widget_url.format(
                corpus_id=corpus_id,
                content_type=content_type,
                content_id=content_id
            )

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

            # set all boolean fields to False by default--boolean field inputs are checkboxes, and unchecked checkboxes don't
            # show up as POST params. True values for checked boolean fields will get overwritten further below.
            for ct_field_name in ct_fields.keys():
                if ct_fields[ct_field_name].type == 'boolean':
                    setattr(content, ct_field_name, False)

            # iterate over the POST params, assuming each one corresponds with a field value
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

                    # set value for number/decimal fields
                    elif ct_fields[field_name].type in ['number', 'decimal'] and not field_value:
                        field_value = None
                    elif ct_fields[field_name].type == 'decimal':
                        field_value = float(field_value)

                    # set value for boolean fields
                    elif ct_fields[field_name].type == 'boolean':
                        field_value = True

                    # set value for date fields
                    elif ct_fields[field_name].type == 'date' and not field_value:
                        field_value = None
                    elif ct_fields[field_name].type == 'date':
                        field_value = parse_date_string(field_value)

                    # having parsed the value correctly depending on data type, now actually set the field value for
                    # our content
                    if ct_fields[field_name].multiple and len(param_parts) == 3:
                        multi_field_values[field_name].append(field_value)
                    else:
                        setattr(content, field_name, field_value)

            for multi_field_name in multi_field_values.keys():
                setattr(content, multi_field_name, multi_field_values[multi_field_name])

            content.save()

            if temp_file_fields:
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
                'edit_widget_url': edit_widget_url,
                'content_id': content_id,
            }
        )
    else:
        raise Http404("You are not authorized to view this page.")


def view_content(request, corpus_id, content_type, content_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    render_template = _clean(request.GET, 'render_template', None)
    popup = 'popup' in request.GET
    view_widget_url = None

    if not corpus or content_type not in corpus.content_types:
        raise Http404("Corpus does not exist, or you are not authorized to view it.")

    if corpus.content_types[content_type].view_widget_url:
        view_widget_url = corpus.content_types[content_type].view_widget_url.format(
            corpus_id=corpus_id,
            content_type=content_type,
            content_id=content_id
        )

    if render_template and render_template in corpus.content_types[content_type].templates:
        content = corpus.get_content(content_type, content_id)
        if content.id:
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
            'response': context,
            'corpus_id': corpus_id,
            'role': role,
            'popup': popup,
            'content_type': content_type,
            'content_id': content_id,
            'view_widget_url': view_widget_url
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

    if (merge_ids and context['scholar'].is_admin or role == 'Editor') and corpus and content_type in corpus.content_types:
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
        except:
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
                new_perm_corpus_name = request.POST['corpus-name']
                new_perm_corpus_role = request.POST['corpus-permission']

                if new_perm_corpus_name and new_perm_corpus_role in ['Viewer', 'Editor']:
                    try:
                        corpus = Corpus.objects(name=new_perm_corpus_name)[0]
                        if str(corpus.id) not in target_scholar.available_corpora:
                            target_scholar.available_corpora[str(corpus.id)] = new_perm_corpus_role
                            target_scholar.save()
                    except:
                        response['errors'].append("No corpus was found with the name provided.")

                for post_param in request.POST.keys():
                    if post_param not in ['corpus-perms', 'corpus-name', 'corpus-permission'] and post_param.startswith('corpus-'):
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

    #if settings.USE_SSL and not response['url'].startswith('https'):
    #    secure_url = response['url'].replace('http://', 'https://')
    #    return redirect(secure_url)

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

    if corpus and path and (context['scholar'].is_admin or role == 'Editor'):
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
        if context['scholar'].is_admin or uri_dict['corpus'] in context['scholar'].available_corpora.keys():
            results = run_neo(
                '''
                    MATCH (f:_File { uri: $image_uri, is_image: true })
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
def api_corpora(request):
    context = _get_context(request)
    ids = []
    open_access_only = True

    if not context['search']:
        context['search'] = {
            'general_query': "*"
        }

    if context['scholar'] and context['scholar'].is_admin:
        open_access_only = False
    elif context['scholar']:
        ids = [c_id for c_id in context['scholar'].available_corpora.keys()]

    corpora = search_corpora(**context['search'], ids=ids, open_access_only=open_access_only)

    return HttpResponse(
        json.dumps(corpora),
        content_type='application/json'
    )


@api_view(['GET'])
def api_scholar(request, scholar_id=None):
    context = _get_context(request)

    if not context['search']:
        context['search'] = {
            'general_query': "*"
        }

    if context['scholar'] and context['scholar'].is_admin:
        if scholar_id:
            scholar = Scholar.objects(id=scholar_id)[0]
            scholar_dict = {
                'username': scholar.username,
                'fname': scholar.fname,
                'lname': scholar.lname,
                'email': scholar.email,
                'is_admin': scholar.is_admin,
                'available_corpora': {},
                'available_jobsites': [str(js.id) for js in scholar.available_jobsites],
                'available_tasks': [str(task.id) for task in scholar.available_tasks]
            }
            if scholar.available_corpora:
                corpora = Corpus.objects(id__in=list(scholar.available_corpora.keys())).only('id', 'name')
                for corpus in corpora:
                    scholar_dict['available_corpora'][str(corpus.id)] = {
                        'name': corpus.name,
                        'role': scholar.available_corpora[str(corpus.id)]
                    }

            return HttpResponse(
                json.dumps(scholar_dict),
                content_type='application/json'
            )

        else:
            scholars = search_scholars(**context['search'])

            return HttpResponse(
                json.dumps(scholars),
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
        return HttpResponse(
            "{}",
            content_type='application/json'
        )


@api_view(['GET'])
def api_content(request, corpus_id, content_type, content_id=None):
    context = _get_context(request)
    content = {}

    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and content_type in corpus.content_types:
        if content_id:
            content = corpus.get_content(content_type, content_id, context['only'])
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
    collapses = []
    excluded_cts = []

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
                WHERE a.uri = '{uri}' {exclusions}
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
                rel_net_json = get_network_json(
                    '''
                        MATCH path = (a:{origin}) -[b:{relationship}]- (c:{destination})
                        WHERE a.uri = '{uri}' {exclusions} 
                        RETURN path
                        SKIP {skip}
                        LIMIT {limit}
                    '''.format(
                        origin=content_type,
                        relationship=relationship.get('REL'),
                        destination=relationship.get('CT')[0],
                        uri=content_uri,
                        exclusions=exclusion_clause,
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
                WHERE a.uri = '{uri}'
            '''.format(
                origin=collapse['from_ct'],
                proxy_path=proxy_path,
                destination=collapse['to_ct'],
                uri=content_uri
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
def api_jobs(request, corpus_id=None, content_type=None, content_id=None):
    context = _get_context(request)
    payload = {
        'meta': {
            'total': 0,
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

    if not corpus_id and context['scholar'].is_admin:
        payload['meta']['total'] = Job.get_jobs(count_only=True)
        results = Job.get_jobs(
            limit=limit,
            skip=skip
        )

    elif corpus_id:
        corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
        if corpus:
            payload['meta']['total'] = Job.get_jobs(
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

    if payload['meta']['page'] * payload['meta']['page_size'] < payload['meta']['total']:
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
