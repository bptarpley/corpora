import json
import os
from urllib.parse import unquote
import re
import traceback
from time import time, sleep
from django.shortcuts import render, HttpResponse, redirect
from django.utils.html import escape
from django.template import Template, RequestContext, Context
from django.conf import settings
from html import unescape
from bson.objectid import ObjectId
from manager.utilities import _get_context, _clean, _contains, get_scholar_corpus
from .utilities import get_content_search_results
from .decorators import superuser_required
from . import DEFAULT_TEMPLATE_FORMATS, TemplateFormat, Field, ContentType, Content, \
    ContentList, Page, Block, XMLPageSet, XMLTransform, load_content_types_from_schema
from .tasks import build_indexes


@superuser_required
def type_manager(request, corpus_id):
    context = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, context['scholar'], only=['id', 'path'])
    current_formats = TemplateFormat.objects
    templates_changed = False
    indexes_to_build = []

    # HANDLE CONTENT_TYPE/FIELD ACTIONS THAT REQUIRE CONFIRMATION
    if request.method == 'POST' and _contains(request.POST, [
        'content_type',
        'field',
        'action'
    ]):
        action_content_type = _clean(request.POST, 'content_type')
        action_field_name = _clean(request.POST, 'field')
        action = _clean(request.POST, 'action')

        if action_content_type:
            content_type = ContentType.objects(name=action_content_type)[0]

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

        if new_format_label and new_format_extension and new_format_extension not in [default['extension'] for default in DEFAULT_TEMPLATE_FORMATS]:
            new_format = TemplateFormat()
            new_format.label = new_format_label
            new_format.extension = new_format_extension
            new_format.ace_editor_mode = 'django'
            new_format.save()

    # HANDLE OVERALL SCHEMA EDITS
    elif request.method == 'POST' and 'schema' in request.POST:
        schema = json.loads(request.POST['schema'])

        if schema:
            for content_type in schema:
                context['content_types'] = ContentType.objects

                if not content_type['id']:
                    new_content_type = ContentType()
                    new_content_type.corpus = corpus
                    new_content_type.name = content_type['name']
                    new_content_type.plural_name = content_type['plural_name']
                    new_content_type.show_in_nav = content_type['show_in_nav']
                    new_content_type.proxy_field = content_type['proxy_field']
                    for template_type in content_type['templates'].keys():
                        new_content_type.templates[template_type] = content_type['templates'][template_type]

                    self_referencing_fields = {}
                    field_count = 0

                    for field in content_type['fields']:
                        self_referenced = False

                        new_field = Field()
                        new_field.name = field['name']
                        new_field.label = field['label']
                        new_field.in_lists = field['in_lists']
                        new_field.indexed = field['indexed']
                        new_field.indexed_with = field['indexed_with']
                        new_field.unique = field['unique']
                        new_field.unique_with = field['unique_with']
                        new_field.multiple = field['multiple']
                        new_field.type = field['type']

                        if new_field.type == 'cross_reference':
                            if new_content_type.name == field['cross_reference_type']:
                                self_referencing_fields[field_count] = new_field
                                self_referenced = True
                            else:
                                for current_type in context['content_types']:
                                    if current_type.name == field['cross_reference_type']:
                                        new_field.cross_reference_type = current_type

                        if not self_referenced:
                            new_content_type.fields.append(new_field)
                        field_count += 1

                    new_content_type.save()
                    if self_referencing_fields:
                        for field_index in self_referencing_fields.keys():
                            self_referencing_fields[field_index].cross_reference_type = new_content_type
                            new_content_type.fields.insert(field_index, self_referencing_fields[field_index])
                        new_content_type.save()
                    templates_changed = True
                    indexes_to_build.append(new_content_type.name)

                else:
                    ct = None
                    try:
                        ct = ContentType.objects(id=content_type['id'])[0]
                    except:
                        ct = None
                    if ct:
                        ct.plural_name = content_type['plural_name']
                        ct.show_in_nav = content_type['show_in_nav']
                        ct.proxy_field = content_type['proxy_field']
                        for template_type in content_type['templates'].keys():
                            if ct.templates[template_type] != content_type['templates'][template_type]:
                                ct.templates[template_type] = content_type['templates'][template_type]
                                templates_changed = True
                        
                        old_fields = {}
                        for x in range(0, len(ct.fields)):
                            old_fields[ct.fields[x].name] = x
                            
                        for x in range(0, len(content_type['fields'])):
                            if content_type['fields'][x]['name'] not in old_fields:
                                new_field = Field()
                                new_field.name = content_type['fields'][x]['name']
                                new_field.label = content_type['fields'][x]['label']
                                new_field.in_lists = content_type['fields'][x]['in_lists']
                                new_field.indexed = content_type['fields'][x]['indexed']
                                new_field.indexed_with = content_type['fields'][x]['indexed_with']
                                new_field.unique = content_type['fields'][x]['unique']
                                new_field.unique_with = content_type['fields'][x]['unique_with']
                                new_field.multiple = content_type['fields'][x]['multiple']
                                new_field.type = content_type['fields'][x]['type']

                                if new_field.type == 'cross_reference':
                                    for current_type in context['content_types']:
                                        if current_type.name == content_type['fields'][x]['cross_reference_type']:
                                            new_field.cross_reference_type = current_type
                                ct.fields.append(new_field)
                                indexes_to_build.append(ct.name)

                            else:
                                field_index = old_fields[content_type['fields'][x]['name']]
                                ct.fields[field_index].label = content_type['fields'][x]['label']

                                if ct.fields[field_index].in_lists != content_type['fields'][x]['in_lists']:
                                    ct.fields[field_index].in_lists = content_type['fields'][x]['in_lists']
                                    indexes_to_build.append(ct.name)

                                ct.fields[field_index].indexed = content_type['fields'][x]['indexed']
                                ct.fields[field_index].indexed_with = content_type['fields'][x]['indexed_with']
                                ct.fields[field_index].unique = content_type['fields'][x]['unique']
                                ct.fields[field_index].unique_with = content_type['fields'][x]['unique_with']
                                ct.fields[field_index].multiple = content_type['fields'][x]['multiple']
                                ct.fields[field_index].type = content_type['fields'][x]['type']
                                if ct.fields[field_index].type == 'cross_reference':
                                    for current_type in context['content_types']:
                                        if current_type.name == content_type['fields'][x]['cross_reference_type']:
                                            ct.fields[field_index].cross_reference_type = current_type
                                else:
                                    ct.fields[field_index].cross_reference_type = None
                        ct.save()

    if templates_changed:
        context['content_types'] = ContentType.objects

        if templates_changed:
            template_dir = "{0}/templates/types".format(corpus.path)
            os.makedirs(template_dir, exist_ok=True)
            for ct in context['content_types']:
                ct_template_dir = "{0}/{1}".format(template_dir, ct.name)
                os.makedirs(ct_template_dir, exist_ok=True)
                for template_type in ct.templates.keys():
                    if template_type != 'field_templates':
                        for template_format in ct.templates[template_type].keys():
                            template_path = "{0}/{1}.{2}".format(
                                ct_template_dir,
                                template_type,
                                template_format
                            )
                            with open(template_path, 'w', encoding='utf-8') as template_out:
                                template_out.write(ct.templates[template_type][template_format])

    if indexes_to_build:
        build_indexes(corpus_id, indexes_to_build)

    return render(
        request,
        'type_manager.html',
        {
            'corpus_id': corpus_id,
            'context': context
        }
    )


@superuser_required
def type_schema(request, corpus_id):
    schema = {
        'content_types': [],
        'template_formats': []
    }
    context = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, context['scholar'], only=['id', 'path', 'uri'])
    if corpus:
        # HANDLE OVERALL SCHEMA EDITS
        if request.method == 'POST' and 'schema' in request.POST:
            schema = json.loads(request.POST['schema'])

            if schema:
                load_content_types_from_schema(corpus, schema)
        else:
            types = ContentType.objects(corpus=corpus_id)
            template_formats = TemplateFormat.objects(corpus=corpus_id)
            ct_obj = json.loads(types.to_json())
            if ct_obj:
                for x in range(0, len(ct_obj)):
                    ct_obj[x]['id'] = ct_obj[x]['_id']['$oid']
                    for y in range(0, len(ct_obj[x]['fields'])):
                        if ct_obj[x]['fields'][y]['type'] == 'cross_reference':
                            for t in types:
                                if str(t.id) == ct_obj[x]['fields'][y]['cross_reference_type']['$oid']:
                                    ct_obj[x]['fields'][y]['cross_reference_type'] = t.name
                                    break
                schema['content_types'] = ct_obj

            fmt_obj = json.loads(template_formats.to_json())
            if fmt_obj:
                schema['template_formats'] = DEFAULT_TEMPLATE_FORMATS + fmt_obj
            else:
                schema['template_formats'] = DEFAULT_TEMPLATE_FORMATS

    return HttpResponse(
        json.dumps(schema),
        content_type='application/json'
    )


@superuser_required
def edit_content(request, corpus_id, content_type, id=None):
    context = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, context['scholar'], only=['id', 'path'])
    content = {}
    content_type = escape(content_type)
    popup = 'popup' in request.GET

    if not id:
        content = Content(corpus_id, content_type)
    else:
        content = Content(corpus_id, content_type, escape(id))

    if content and request.method == "POST":
        for field in content.fields.keys():
            if content.fields[field]['multiple']:
                content.fields[field]['value'] = []
                post_var_prefix = "{0}-{1}-".format(content_type, field)
                for post_var in request.POST.keys():
                    if post_var.startswith(post_var_prefix):
                        value = _clean(request.POST, post_var)
                        if content.fields[field]['type'] == 'html':
                            value = unescape(value)

                        if content.fields[field]['cross_reference_type']:
                            referenced = Content(corpus_id, content.fields[field]['cross_reference_type'], value)
                            if referenced.instance:
                                content.fields[field]['value'].append({
                                    'id': str(referenced.instance.id),
                                    'label': referenced.instance._label,
                                    'url': "/corpus/{0}/type/{1}/view/{2}/".format(corpus_id, referenced.content_type.name, referenced.id),
                                })
                        else:
                            content.fields[field]['value'].append(value)
            else:
                post_var = "{0}-{1}".format(content_type, field)
                if post_var in request.POST:
                    print(post_var)
                    if not request.POST[post_var]:
                        content.fields[field]['value'] = None
                    else:
                        value = _clean(request.POST, post_var)
                        if content.fields[field]['type'] == 'html':
                            value = unescape(value)

                        if content.fields[field]['cross_reference_type']:
                            referenced = Content(corpus_id, content.fields[field]['cross_reference_type'], value)
                            if referenced.instance:
                                content.fields[field]['value'] = {
                                    'id': str(referenced.instance.id),
                                    'label': referenced.instance._label,
                                    'url': "/corpus/{0}/type/{1}/view/{2}/".format(corpus_id, referenced.content_type.name, referenced.id)
                                }
                                print(content.fields[field]['value'])
                        else:
                            content.fields[field]['value'] = value
        content.save()

        if popup:
            return render(
                request,
                '/popup_submission.html',
                {
                    'new_id': content.id,
                    'new_label': content.label
                }
            )
        else:
            return redirect("/corpus/{0}/#{1}".format(corpus_id, content.content_type.plural_name))

    if content:
        html_template_path = "{0}/templates/types/{1}/edit.html".format(corpus_id, content_type)
        js_template_path = "{0}/templates/types/{1}/edit.js".format(corpus_id, content_type)

        if os.path.exists("/corpora/{0}".format(html_template_path)):
            template_string = '''
                {{% extends 'base.html' %}}
                {{% load static %}}
                {{% load extras %}}
                {{% block main %}}
                    {{% include '{0}' with {1}=List{1} %}}
                {{% endblock %}}
            '''.format(
                html_template_path,
                content_type
            )

            if os.path.exists("/corpora/{0}".format(js_template_path)):
                template_string += '''
                {{% block js %}}
                    {{% include '{0}' with {1}=List{1} %}}
                {{% endblock %}}
                '''.format(
                    js_template_path,
                    content_type
                )

            response = HttpResponse()
            template = Template(template_string)
            template_context = RequestContext(request, {
                'List' + content_type: content,
                'popup': popup,
                'context': context,
                'corpus_id': corpus_id,
                'cms': True
            })
            response.write(template.render(template_context))
            return response
    else:
        return redirect('/')


def view_content(request, corpus_id, content_type, id, format_extension=None):
    context = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, context['scholar'], only=['id', 'path'])
    popup = 'popup' in request.GET
    content = {}
    content_type = escape(content_type)
    id = escape(id)

    content = Content(corpus_id, content_type, id)

    if content.id:
        if format_extension:
            template_format = TemplateFormat.objects(corpus=corpus_id, extension=format_extension)[0]
            template_path = "{0}/templates/types/{1}/view.{2}".format(corpus_id, content_type, format_extension)
            if os.path.exists("/corpora/{0}".format(template_path)):
                template_string = '''
                    {{% load static %}}
                    {{% load extras %}}
                    {{% include '{0}' with {1}=View{1} %}}
                '''.format(
                    template_path,
                    content_type
                )
                template = Template(template_string)
                template_context = Context({
                    'View' + content_type: content,
                })
                return HttpResponse(
                    template.render(template_context),
                    content_type=template_format.mime_type
                )
        else:
            html_template_path = "{0}/templates/types/{1}/view.html".format(corpus_id, content_type)
            js_template_path = "{0}/templates/types/{1}/view.js".format(corpus_id, content_type)

            if os.path.exists("/corpora/{0}".format(html_template_path)):
                template_string = '''
                    {{% extends 'base.html' %}}
                    {{% load static %}}
                    {{% load extras %}}
                    {{% block main %}}
                        {{% include '{0}' with {1}=View{1} %}}
                    {{% endblock %}}
                '''.format(
                    html_template_path,
                    content_type
                )

                if os.path.exists("/corpora/{0}".format(js_template_path)):
                    template_string += '''
                    {{% block js %}}
                        {{% include '{0}' with {1}=View{1} %}}
                    {{% endblock %}}
                    '''.format(
                        js_template_path,
                        content_type
                    )

                response = HttpResponse()
                template = Template(template_string)
                template_context = RequestContext(request, {
                    'View' + content_type: content,
                    'popup': popup,
                    'context': context,
                    'corpus_id': corpus_id,
                    'cms': True
                })
                response.write(template.render(template_context))
                return response
    else:
        return redirect('/')


def list_content(request, corpus_id, content_type):
    context = _get_context(request)
    corpus = get_scholar_corpus(corpus_id, context['scholar'], only=['id', 'path'])
    content_type = escape(content_type)
    my_type = ContentType.objects(corpus=corpus_id, name=content_type)[0]

    if my_type:
        html_template_path = "{0}/templates/types/{1}/list.html".format(corpus_id, content_type)
        js_template_path = "{0}/templates/types/{1}/list.js".format(corpus_id, content_type)

        if os.path.exists("/corpora/{0}".format(html_template_path)):
            template_string = '''
                {{% extends 'base.html' %}}
                {{% load static %}}
                {{% load extras %}}
                {{% block main %}}
                    {{% include '{0}' %}}
                {{% endblock %}}
            '''.format(html_template_path)

            if os.path.exists("/corpora/{0}".format(js_template_path)):
                template_string += '''
                {{% block js %}}
                    {{% include '{0}' %}}
                {{% endblock %}}
                '''.format(js_template_path)

            response = HttpResponse()
            template = Template(template_string)
            template_context = RequestContext(request, {
                'context': context,
                'corpus_id': corpus_id,
                'cms': True
            })
            response.write(template.render(template_context))
            return response
    else:
        return redirect('/')


def api_content_data(request, corpus_id, content_type, id=None):
    content_type = escape(content_type)
    context = _get_context(request)
    if not id:
        payload = get_content_search_results(request, context['scholar'], corpus_id, content_type)
    else:
        only = []
        if 'only' in request.GET:
            only = _clean(request.GET, 'only').split(',')

        content = Content(corpus_id, content_type, escape(id), only=only)
        payload = {
            'id': content.id,
            'label': content.label,
            'fields': content.fields
        }

    return HttpResponse(
        json.dumps(payload),
        content_type='application/json'
    )


def get_field_stats(request, content_type):
    content_type = escape(content_type)
    try:
        return HttpResponse(
            json.dumps(ContentType.objects(name=content_type)[0].get_field_stats()),
            content_type='application/json'
        )
    except:
        return HttpResponse(
            "{}",
            content_type='application/json'
        )


def render_page(request):
    try:
        context = _get_context(request)
        print(request.path)
        page = Page.objects(url=request.path)[0]
        print(page.title)
        page_template = "{0}/pages{1}page.html".format(
            settings.TEMPLATE_DIR,
            page.url
        )
        print(page_template)
        if os.path.exists(page_template):
            return render(
                request,
                page_template,
                {
                    'skin': settings.SKIN,
                    'base_template': 'skins/{0}/base.html'.format(settings.SKIN),
                    'context': context
                }
            )
    except:
        print(traceback.format_exc())

    return HttpResponse(
        json.dumps({'error': 'no page found at this url: ' + request.path})
    )


@superuser_required
def manage_files(request):
    files = []
    base_path = settings.MEDIA_DIR
    sub_path = _clean(request.GET, 'path', '')
    full_path = base_path + sub_path
    filter = _clean(request.GET, 'filter', '')

    # HANDLE UPLOADS
    if 'filepond' in request.FILES:
        filename = re.sub(r'[^a-zA-Z0-9\\.\\-]', '_', request.FILES['filepond'].name)
        print(filename)
        file_path = "{0}/{1}".format(full_path, filename)

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
            os.mkdir(new_dir_path)
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
