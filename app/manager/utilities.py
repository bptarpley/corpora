from corpus import *
from mongoengine.queryset.visitor import Q
from django.utils.html import escape
from bs4 import BeautifulSoup
from math import ceil
from bson.objectid import ObjectId
from google.cloud import vision
from elasticsearch_dsl import A
import traceback
import shutil
import json
import redis


def get_scholar_corpora(scholar, only=[], page=1, page_size=50):
    corpora = []
    start_record = (page - 1) * page_size
    end_record = start_record + page_size

    if scholar:
        if scholar.is_admin:
            corpora = Corpus.objects
        else:
            corpora = Corpus.objects(Q(id__in=[c_id for c_id in scholar.available_corpora.keys()]) | Q(open_access=True))
    else:
        corpora = Corpus.objects(open_access=True)

    if corpora and only:
        corpora = corpora.only(only)

    return corpora[start_record:end_record]


def get_scholar_corpus(corpus_id, scholar, only=[]):
    corpus = None
    role = 'Viewer'

    if (scholar and scholar.is_admin) or \
            (scholar and corpus_id in scholar.available_corpora.keys()) or \
            corpus_id in get_open_access_corpora():

        corpus = get_corpus(corpus_id, only)
        if scholar and scholar.is_admin:
            role = 'Admin'
        elif scholar and corpus_id in scholar.available_corpora.keys():
            role = scholar.available_corpora[corpus_id]

    return corpus, role


def parse_uri(uri):
    uri_dict = {}
    uri_parts = [part for part in uri.split('/') if part]

    if len(uri_parts) % 2 == 0:
        key_index = 0

        while key_index < len(uri_parts):
            uri_dict[uri_parts[key_index]] = uri_parts[key_index + 1]
            key_index += 2

    return uri_dict


def get_tasks(scholar, content_type=None):
    tasks = []

    if scholar:
        if scholar.is_admin:
            if content_type:
                tasks = Task.objects(content_type=content_type)
            else:
                tasks = Task.objects
        else:
            if content_type:
                tasks = Task.objects(id__in=[t.pk for t in scholar.available_tasks], content_type=content_type)
            else:
                tasks = Task.objects(id__in=[t.pk for t in scholar.available_tasks])

    return tasks


def get_jobsites(scholar):
    jobsites = []

    if scholar:
        if scholar.is_admin:
            jobsites = JobSite.objects
        else:
            jobsites = JobSite.objects(id__in=[j.pk for j in scholar.available_jobsites])

    return jobsites


def _get_context(req):
    context = {
        'errors': [],
        'messages': [],
        'scholar': {},
        'url': req.build_absolute_uri(req.get_full_path()),
        'only': [],
        'search': build_search_params_from_dict(req.GET)
    }

    if 'msg' in req.GET:
        context['messages'].append(req.GET['msg'])
    elif 'only' in req.GET:
        context['only'] = req.GET['only'].split(',')
        if context['search']:
            context['search']['only'] = context['only']

    if req.user.is_authenticated:

        scholar_json = req.session.get('scholar_json', None)
        if scholar_json:
            context['scholar'] = Scholar.from_json(scholar_json)
        else:
            try:
                context['scholar'] = Scholar.objects(username=req.user.username)[0]
                req.session['scholar_json'] = context['scholar'].to_json()
            except:
                print(traceback.format_exc())
                context['scholar'] = {}

        if context['scholar'] and 'HTTP_AUTHORIZATION' in req.META:
            req.session['corpora_api_user_id'] = str(req.user.id)
            req.session.set_expiry(300)
            if 'HTTP_X_REAL_IP' in req.META:
                if req.META['HTTP_X_REAL_IP'] not in context['scholar'].auth_token_ips:
                    context['scholar'] = {}
            else:
                context['scholar'] = {}
        else:
            req.session.set_expiry(0)

    return context


def build_search_params_from_dict(params):
    search = {}
    
    default_search = {
        'general_query': '',
        'fields_query': {},
        'fields_term': {},
        'fields_phrase': {},
        'fields_filter': {},
        'fields_range': {},
        'fields_wildcard': {},
        'fields_exist': [],
        'fields_highlight': [],
        'fields_sort': [],
        'aggregations': {},
        'content_view': None,
        'page': 1,
        'page_size': 50,
        'only': [],
        'operator': "and",
        'highlight_num_fragments': 5,
        'highlight_fragment_size': 100,
        'es_debug': False
    }

    for param in params.keys():
        value = params[param]
        search_field_name = param[2:]

        if not search and param in [
            'q',
            'page',
            'page-size',
            'only',
            'operator',
            'content_view',
            'highlight_fields',
            'highlight_num_fragments',
            'highlight_fragment_size',
            'page-token',
            'es_debug',
            'es_debug_query'
        ] or param[:2] in ['q_', 't_', 'p_', 's_', 'f_', 'r_', 'w_', 'e_', 'a_']:
            search = default_search

        if param == 'highlight_fields':
            search['fields_highlight'] = value.split(',')
        elif param == 'highlight_num_fragments' and value.isdigit():
            search['highlight_num_fragments'] = int(value)
        elif param == 'highlight_fragment_size' and value.isdigit():
            search['highlight_fragment_size'] = int(value)
        elif param == 'content_view':
            search['content_view'] = value
        elif param == 'page-token':
            search['next_page_token'] = value
        elif param == 'q':
            search['general_query'] = value
        elif param.startswith('q_'):
            search['fields_query'][search_field_name] = value
        elif param.startswith('t_'):
            search['fields_term'][search_field_name] = value
        elif param.startswith('p_'):
            search['fields_phrase'][search_field_name] = value
        elif param.startswith('s_'):
            if value.lower() == 'asc':
                search['fields_sort'].append({search_field_name: {"order": 'ASC', "missing": "_first"}})
            else:
                search['fields_sort'].append({search_field_name: {"order": value}})
        elif param.startswith('f_'):
            search['fields_filter'][search_field_name] = value
        elif param.startswith('r_'):
            search['fields_range'][search_field_name] = value
        elif param.startswith('w_'):
            search['fields_wildcard'][search_field_name] = value
        elif param.startswith('e_'):
            search['fields_exist'].append(search_field_name)
        elif param.startswith('a_'):
            if param.startswith('a_terms_'):
                agg_name = param.replace('a_terms_', '')
                field_val = None
                script_val = None

                if ',' in value:
                    agg_fields = value.split(',')
                    script_agg_fields = ["doc['{0}'].value".format(f) for f in agg_fields if f]
                    script_val = "return {0}".format(" + '|||' + ".join(script_agg_fields))
                else:
                    field_val = value

                if '.' in value:
                    nested_path = value.split('.')[0]
                    agg = A('nested', path=nested_path)
                    if field_val:
                        agg.bucket('names', 'terms', size=10000, field=field_val)
                    elif script_val:
                        agg.bucket('names', 'terms', size=10000, script={'source': script_val})
                    search['aggregations'][agg_name] = agg
                elif field_val:
                    search['aggregations'][agg_name] = A('terms', size=10000, field=field_val)
                elif script_val:
                    search['aggregations'][agg_name] = A('terms', size=10000, script={'source': script_val})

            elif param.startswith('a_max_') or param.startswith('a_min_'):
                metric_parts = param.split('_')
                if len(metric_parts) == 3:
                    metric_type = metric_parts[1]
                    agg_name = metric_parts[2]

                    if '.' in value:
                        nested_path = value.split('.')[0]
                        agg = A('nested', path=nested_path)
                        agg.bucket('names', metric_type, field=value)
                        search['aggregations'][agg_name] = agg
                    else:
                        search['aggregations'][agg_name] = A(metric_type, field=value)

        elif param == 'operator':
            search['operator'] = value
        elif param == 'page':
            search['page'] = int(value)
        elif param == 'page-size':
            search['page_size'] = int(value)
        elif param == 'es_debug':
            search['es_debug'] = True
        elif param == 'es_debug_query':
            search['es_debug_query'] = True

    if search and (not search['general_query'] and not search['fields_query'] and not search['fields_filter'] and not search['fields_wildcard'] and not search['fields_range']):
        search['general_query'] = "*"

    return search


def clear_cached_session_scholar(user_id):
    cache = redis.Redis(host='redis', db=1, decode_responses=True)
    key_prefix = 'corpora:1:django.contrib.sessions.cache'
    from importlib import import_module
    SessionStore = import_module(settings.SESSION_ENGINE).SessionStore

    for key in cache.keys():
        if key.startswith(key_prefix):
            session_key = key.replace(key_prefix, '')
            session = SessionStore(session_key=session_key)
            clear_scholar_json = False
            if session and 'scholar_json' in session:
                if '_auth_user_id' in session and session['_auth_user_id'] == str(user_id):
                    clear_scholar_json = True
                elif 'corpora_api_user_id' in session and session['corpora_api_user_id'] == str(user_id):
                    clear_scholar_json = True

            if clear_scholar_json:
                session.pop('scholar_json')
                session.save()


def get_open_access_corpora(use_cache=True):
    oa_corpora = []

    cache = redis.Redis(host='redis', decode_responses=True)
    oa_corpora_list = cache.get('/open_access_corpora')
    if not oa_corpora_list or not use_cache:
        corpora = Corpus.objects(open_access=True)
        oa_corpora_list = ",".join([str(corpus.id) for corpus in corpora])
        cache.set('/open_access_corpora', oa_corpora_list)

    if oa_corpora_list:
        oa_corpora = oa_corpora_list.split(',')

    return oa_corpora


def order_content_schema(schema):
    ordered_schema = []
    ordering = True
    while ordering:
        num_ordered_cts = len(ordered_schema)
        ordered_ct_names = [ct['name'] for ct in ordered_schema]

        for ct_spec in schema:
            independent = True
            for field in ct_spec['fields']:
                if field['type'] == 'cross_reference' and field['cross_reference_type'] != ct_spec['name'] and field['cross_reference_type'] not in ordered_ct_names:
                    independent = False
                    break
            if independent and ct_spec['name'] not in ordered_ct_names:
                ordered_schema.append(ct_spec)
                ordered_ct_names.append(ct_spec['name'])

        if num_ordered_cts == len(ordered_schema) or len(schema) == len(ordered_schema):
            ordering = False

    return ordered_schema


def process_content_bundle(corpus, content_type, content, content_bundle, scholar_id, bulk_editing=False):
    if content_type in corpus.content_types:
        ct_fields = corpus.content_types[content_type].get_field_dict()
        temp_file_fields = []

        for field_name, data in content_bundle.items():
            if field_name in ct_fields:
                field = ct_fields[field_name]

                if (not bulk_editing) or (field.type not in ['file', 'repo'] and not field.unique):

                    if field.multiple:
                        setattr(content, field_name, [])
                    else:
                        data = [data]

                    for datum in data:
                        value = datum['value']
                        valid_value = True
                        if (not value) and value != 0:
                            valid_value = False
                            value = None

                        if valid_value:
                            if field.type == 'cross_reference':
                                value = corpus.get_content(field.cross_reference_type, value).to_dbref()

                            elif field.type == 'file':
                                base_path = "{corpus_path}/{content_type}/temporary_uploads".format(
                                    corpus_path=corpus.path,
                                    content_type=content_type
                                )

                                if content.id:
                                    base_path = "{content_path}/files".format(content_path=content.path)

                                file_path = "{base_path}{sub_path}".format(
                                    base_path=base_path,
                                    sub_path=value
                                )
                                if os.path.exists(file_path):
                                    value = File.process(
                                        file_path,
                                        desc="{0} for {1}".format(ct_fields[field_name].label, content_type),
                                        prov_type="Scholar",
                                        prov_id=str(scholar_id)
                                    )

                                    if not content.id and field_name not in temp_file_fields:
                                        temp_file_fields.append(field_name)

                            elif field.type == 'date':
                                value = parse_date_string(value)

                        if field.multiple:
                            if valid_value:
                                getattr(content, field_name).append(value)
                        else:
                            setattr(content, field_name, value)

                        if field.has_intensity and 'intensity' in datum:
                            content.set_intensity(field_name, value, datum['intensity'])

        content.save(relabel=True)

        if temp_file_fields:
            for temp_file_field in temp_file_fields:
                if ct_fields[temp_file_field].multiple:
                    for f_index in range(0, len(getattr(content, temp_file_field))):
                        content._move_temp_file(temp_file_field, f_index)
                else:
                    content._move_temp_file(temp_file_field)

            content.save(relabel=True)


def _contains(obj, keys):
    for key in keys:
        if key not in obj:
            return False
    return True


def _contains_any(obj, keys):
    for key in keys:
        if key in obj:
            return True
    return False


def _clean(obj, key, default_value=''):
    val = obj.get(key, False)
    if val:
        return escape(val)
    else:
        return default_value

