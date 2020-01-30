from corpus import *
from mongoengine.queryset.visitor import Q
from django.utils.html import escape
from bs4 import BeautifulSoup
from math import ceil
from bson.objectid import ObjectId
from google.cloud import vision
import traceback
import shutil
import json


def get_scholar_corpora(scholar, only=[], page=1, page_size=50):
    corpora = []
    start_record = (page - 1) * page_size
    end_record = start_record + page_size

    if scholar:
        if scholar.is_admin:
            corpora = Corpus.objects
        else:
            corpora = Corpus.objects(Q(id__in=[c.pk for c in scholar.available_corpora]) | Q(open_access=True))
    else:
        corpora = Corpus.objects(open_access=True)

    if corpora and only:
        corpora = corpora.only(only)

    return corpora[start_record:end_record]


def get_scholar_corpus(corpus_id, scholar, only=[]):
    corpus = None
    if scholar.is_admin or corpus_id in [str(c.pk) for c in scholar.available_corpora]:
        corpus = get_corpus(corpus_id, only)

    return corpus


def get_document(scholar, corpus_id, document_id, only=[]):
    doc = None
    corpus = get_scholar_corpus(corpus_id, scholar, ['id'])

    if corpus:
        doc = corpus.get_document(document_id, only)

    return doc


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


def get_corpus_search_results(request, scholar, corpus_id=None, document_id=None):
    valid_search = False
    results = {
        'meta': {
            'total': 0,
            'page': 1,
            'page_size': 50,
            'num_pages': 1,
            'has_next_page': False
        },
        'records': []
    }
    search_results = []
    general_search_query = None
    fields_query = {}
    fields_sort = []
    search_pages = request.GET.get('search-pages', 'n') == 'y'

    # Users can provide a general search query (q)
    if 'q' in request.GET:
        general_search_query = request.GET['q']
        valid_search = True

    # Users can alternatively provide specific queries per field (q_[field]=query),
    # and can also specify how they want to sort the data (s_[field]=asc/desc)
    for query_field in request.GET.keys():
        field_name = query_field[2:]
        if query_field.startswith('q_'):
            fields_query[field_name] = request.GET[query_field]
            valid_search = True
        elif query_field.startswith('s_'):
            if request.GET[query_field] == 'desc':
                field_name = '-' + field_name
            fields_sort.append(field_name + '.raw')
        elif query_field == 'page':
            results['meta']['page'] = int(request.GET[query_field])
        elif query_field == 'page-size':
            results['meta']['page_size'] = int(request.GET[query_field])

    start_record = (results['meta']['page'] - 1) * results['meta']['page_size']
    end_record = start_record + results['meta']['page_size']

    if not valid_search:
        general_search_query = '*'
        valid_search = True

    if valid_search and corpus_id:
        corpus = get_scholar_corpus(corpus_id, scholar, only=['field_settings'])
        if corpus:
            sane = True

            es_field_name_map = {}
            for field_name, settings in corpus.field_settings.items():
                es_field_name_map[settings['es_field_name']] = field_name

            # make sure all fields_query fields are in corpus field settings...
            for es_field_name in fields_query.keys():
                if not (es_field_name in es_field_name_map and corpus.field_settings[es_field_name_map[es_field_name]]['display']):
                    sane = False
                    break

            # make sure all fields_sort fields are in corpus field settings...
            for sort_entry in fields_sort:
                es_field_name = sort_entry
                if sort_entry.startswith('-'):
                    es_field_name = es_field_name[1:]
                if sort_entry.endswith('.raw'):
                    es_field_name = es_field_name[:-4]

                if es_field_name in es_field_name_map and corpus.field_settings[es_field_name_map[es_field_name]]['sort']:
                    if corpus.field_settings[es_field_name_map[es_field_name]]['type'] != 'text' and sort_entry.endswith('.raw'):
                        fields_sort[fields_sort.index(sort_entry)] = sort_entry[:-4]
                else:
                    sane = False
                    break

            if sane:
                search_results = corpus.search_documents(general_search_query, fields_query, fields_sort, search_pages, document_id, start_record, end_record)

    elif valid_search:
        sane = True
        if fields_sort and not (len(list(fields_sort.keys())) == 1 and ('name.raw' in fields_sort or '-name.raw' in fields_sort)):
            sane = False

        if sane:
            search_results = search_corpora(general_search_query, fields_sort, start_record, end_record)

    if search_results:
        results['meta']['total'] = search_results['hits']['total']['value']
        results['meta']['num_pages'] = ceil(results['meta']['total'] / results['meta']['page_size'])
        results['meta']['has_next_page'] = results['meta']['num_pages'] > results['meta']['page']
        for search_result in search_results['hits']['hits']:
            result = search_result['_source']
            result['_id'] = { '$oid': search_result['_id'] }
            results['records'].append(result)

    return results


def _get_context(req):
    context = {
        'errors': [],
        'messages': [],
        'scholar': {},
        'url': req.build_absolute_uri(req.get_full_path()),
        'only': [],
        'search': {}
    }

    default_search = {
        'general_query': '',
        'fields_query': {},
        'fields_sort': [],
        'page': 1,
        'page_size': 50,
        'only': []
    }

    for param in req.GET.keys():
        value = req.GET[param]
        search_field_name = param[2:]

        if param in ['q', 'page', 'page-size'] or param.startswith('q_') or param.startswith('s_'):
            context['search'] = default_search
        
        if param == 'msg':
            context['messages'].append(value)
        if param == 'only':
            context['only'] = value.split(',')
            if context['search']:
                context['search']['only'] = context['only']
        elif param == 'q':
            context['search']['general_query'] = value
        elif param.startswith('q_'):
            context['search']['fields_query'][search_field_name] = value
        elif param.startswith('s_'):
            if value == 'desc':
                search_field_name = '-' + search_field_name
            context['search']['fields_sort'].append(search_field_name + '.raw')
        elif param == 'page':
            context['search']['page'] = int(value)
        elif param == 'page-size':
            context['search']['page_size'] = int(value)

    if context['search'] and (not context['search']['general_query'] and not context['search']['fields_query']):
        context['search']['general_query'] = "*"

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

    return context


def _contains(obj, keys):
    for key in keys:
        if key not in obj:
            return False
    return True


def _clean(obj, key, default_value=''):
    val = obj.get(key, False)
    if val:
        return escape(val)
    else:
        return default_value

