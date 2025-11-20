import os
import re
import json
import redis
import traceback
import tarfile
from copy import deepcopy
from mongoengine.queryset.visitor import Q
from django.utils.html import escape
from django.conf import settings
from urllib.parse import unquote
from django_eventstream import send_event
from django_drf_filepond.models import TemporaryUpload
from corpus import (
    Corpus, CorpusBackup, Scholar,
    JobSite, Task,
    File, GitRepo, Timespan,
    get_corpus, parse_date_string
)


# for use by the fix_mongo_json function:
mongo_id_pattern = re.compile(r'{"\$oid":\s*"([^"]*)"\}')
mongo_date_pattern = re.compile(r'{"\$date":\s*([^}]*)}')


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


def scholar_has_privilege(privilege, role):
    return role == privilege or role == 'Admin' or \
        (role == 'Editor' and privilege in ['Editor', 'Contributor', 'Viewer']) or \
        (role == 'Contributor' and privilege in ['Contributor', 'Viewer'])


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
    grouped_params = {}
    
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
        'grouped_searches': [],
        'content_view': None,
        'page': 1,
        'page_size': 50,
        'only': [],
        'operator': "and",
        'highlight_num_fragments': 5,
        'highlight_fragment_size': 100,
        'only_highlights': False,
        'es_debug': False
    }

    for param in params.keys():
        value = params[param]
        search_field_name = param[2:]

        if not search and (param in [
            'q',
            'page',
            'page-size',
            'only',
            'operator',
            'content_view',
            'highlight_fields',
            'highlight_num_fragments',
            'highlight_fragment_size',
            'only_highlights',
            'page-token',
            'es_debug',
            'es_debug_query'
        ] or param[:2] in ['q_', 't_', 'p_', 's_', 'f_', 'r_', 'w_', 'e_', 'a_', '1_', '2_', '3_', '4_', '5_', '6_', '7_', '8_', '9_']):
            search = deepcopy(default_search)

        if param == 'highlight_fields':
            search['fields_highlight'] = value.split(',')
        elif param == 'highlight_num_fragments' and value.isdigit():
            search['highlight_num_fragments'] = int(value)
        elif param == 'highlight_fragment_size' and value.isdigit():
            search['highlight_fragment_size'] = int(value)
        elif param == 'only_highlights':
            search['only_highlights'] = True
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
                    agg = {'nested': {'path': nested_path}, 'aggs': {}}
                    if field_val:
                        agg['aggs']['names'] = {'terms': {'field': field_val, 'size': 1000}}
                    elif script_val:
                        agg['aggs']['names'] = {'terms': {'script': {'source': script_val}, 'size': 1000}}
                    search['aggregations'][agg_name] = agg
                elif field_val:
                    search['aggregations'][agg_name] = {'terms': {'field': field_val, 'size': 1000}}
                elif script_val:
                    search['aggregations'][agg_name] = {'terms': {'script': {'source': script_val}, 'size': 1000}}

            elif param.startswith('a_max_') or param.startswith('a_min_') or param.startswith('a_geobounds_'):
                metric_parts = param.split('_')
                if len(metric_parts) == 3:
                    metric_type = metric_parts[1]
                    if metric_type == 'geobounds':
                        metric_type = 'geo_bounds'
                    agg_name = metric_parts[2]

                    if '.' in value:
                        nested_path = value.split('.')[0]
                        agg = {'nested': {'path': nested_path}, 'aggs': {
                            'names': {metric_type: {'field': value}}
                        }}
                        search['aggregations'][agg_name] = agg
                    else:
                        search['aggregations'][agg_name] = {metric_type: {'field': value}}

            elif param.startswith('a_histogram_'):
                metric_parts = param.split('_')
                if len(metric_parts) == 3:
                    agg_name = metric_parts[2]
                    field_parts = value.split('__')
                    if len(field_parts) == 2:
                        field = field_parts[0]
                        interval = field_parts[1]

                        if interval.isdigit() and int(interval) > 0:
                            if '.' in field:
                                nested_path = field.split('.')[0]
                                agg = {'nested': {'path': nested_path}, 'aggs': {
                                    'names': {'histogram': {'field': field, 'interval': int(interval)}}
                                }}
                                search['aggregations'][agg_name] = agg
                            else:
                                search['aggregations'][agg_name] = {'histogram': {'field': field, 'interval': int(interval)}}

            elif param.startswith('a_geotile_'):
                metric_parts = param.split('_')
                if len(metric_parts) == 3:
                    agg_name = metric_parts[2]
                    if '__' in value and len(value.split('__')) == 2:
                        [field_name, precision] = value.split('__')
                    else:
                        field_name = value
                        precision = 8

                    agg = None
                    if '.' in value:
                        nested_path = value.split('.')[0]
                        agg = {'nested': {'path': nested_path}, 'aggs': {
                            'names': {'geotile_grid': {'field': field_name, 'precision': precision}}
                        }}
                    else:
                        agg == {'geotile_grid': {'field': field_name, 'precision': precision}}
                    search['aggregations'][agg_name] = agg

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

        # extract params for grouped searches
        elif param[:2] in ['1_', '2_', '3_', '4_', '5_', '6_', '7_', '8_', '9_']:
            group_num = param[0]
            group_param = param[2:]
            if group_num not in grouped_params:
                grouped_params[group_num] = {}
            grouped_params[group_num][group_param] = value

    # build group searches
    if grouped_params:
        for group_num in grouped_params.keys():
            search['grouped_searches'].append(deepcopy(build_search_params_from_dict(grouped_params[group_num])))

    if search:
        has_query = False
        for search_param in [
            'general_query', 'fields_query', 'fields_filter', 'fields_wildcard', 'fields_range', 'fields_filter',
            'fields_phrase', 'fields_term', 'grouped_searches'
        ]:
            if search[search_param]:
                has_query = True
                break

        if not has_query:
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
        cache.set('/open_access_corpora', oa_corpora_list, ex=3600)

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
        post_save_file_moves = []
        files_to_delete = []
        single_valued_fields_with_values = []
        repo_fields = []
        repo_jobs = []

        # If this content isn't new, we need to detect when file fields have been changed
        # or emptied so we can appropriately delete stale files, so lets build a list of
        # all file paths saved to this content
        if content.id:
            for field in corpus.content_types[content_type].fields:
                if field.type == 'file':
                    file_field_value = getattr(content, field.name)
                    if file_field_value:
                        if field.multiple:
                            for file_value in file_field_value:
                                files_to_delete.append(file_value.path)
                        else:
                            files_to_delete.append(file_field_value.path)

                if not field.multiple:
                    field_value = getattr(content, field.name)
                    if field_value or field_value == 0 or field_value is False:
                        single_valued_fields_with_values.append(field.name)

        for field_name, data in content_bundle.items():
            if field_name in ct_fields:
                field = ct_fields[field_name]

                if (not bulk_editing) or (field.type not in ['file', 'repo'] and not field.unique):

                    if field.multiple:
                        setattr(content, field_name, [])
                    else:
                        data = [data]

                    for value_index, datum in enumerate(data):
                        value = datum['value']
                        valid_value = True
                        if (not value) and value != 0 and value is not False:
                            valid_value = False
                            value = None

                        if valid_value:
                            if field.type == 'cross_reference':
                                value = corpus.get_content(field.cross_reference_type, value).to_dbref()

                            elif field.type == 'file':
                                # If content has an id and there are forward slashes in the value, we're dealing with
                                # an already processed/saved file, so we'll just make sure the file still exists and
                                # re-gather the metadata
                                if content.id and '/' in value:
                                    base_path = f"{content.path}/files"
                                    file_path = f"{base_path}{value}"

                                # Here we're assuming the file has been freshly uploaded, which should've been handled
                                # by the django-drf-filepond app. A record of the uploaded file should be retrievable
                                # in the form of a TemporaryUpload (a model used by django-drf-filepond). In order to
                                # move it from temporary upload storage, we need to save the content first and move it
                                # to a more appropriate place later. This is because, in order for content to have a
                                # directory to store files, it must first have an id which it receives during the save
                                # process (the id is part of the content's "files" path).
                                else:
                                    temp_upload = TemporaryUpload.objects.get(upload_id=value)
                                    file_path = temp_upload.file.path

                                    post_save_file_moves.append({
                                        'field': field_name,
                                        'multiple': field.multiple,
                                        'upload': temp_upload
                                    })

                                if os.path.exists(file_path):
                                    # let's be sure and remove this from files_to_delete since it's still supposed to
                                    # be there
                                    if file_path in files_to_delete:
                                        files_to_delete.remove(file_path)

                                    value = File.process(
                                        file_path,
                                        desc="{0} for {1}".format(ct_fields[field_name].label, content_type),
                                        prov_type="Scholar",
                                        prov_id=str(scholar_id)
                                    )

                                else:
                                    valid_value = False

                            elif field.type == 'repo':
                                if value.get('name') and value.get('url') and value.get('branch'):
                                    repo = GitRepo()
                                    repo.name = value['name']
                                    repo.remote_url = value['url']
                                    repo.remote_branch = value['branch']

                                    if content.path:
                                        repo.path = "{0}/{1}/{2}".format(content.path, 'repos', value['name'])
                                    elif field_name not in repo_fields:
                                        repo_fields.append(field_name)

                                    clone_job_params = {
                                        'repo_name': repo.name,
                                        'repo_content_type': content_type,
                                        'repo_field': field.name
                                    }
                                    if value.get('user') and value.get('password'):
                                        clone_job_params['repo_user'] = value['user']
                                        clone_job_params['repo_pwd'] = value['password']

                                    repo_jobs.append(clone_job_params)
                                    value = repo
                                else:
                                    valid_value = False

                            elif field.type == 'timespan':
                                span = Timespan()
                                span.start = parse_date_string(value['start'])
                                span.end = parse_date_string(value['end'])
                                span.uncertain = value['uncertain']
                                span.granularity = value['granularity']
                                span.normalize()
                                value = span

                            elif field.type == 'date':
                                value = parse_date_string(value)

                            elif field.type == 'html':
                                value = unquote(value)

                            if valid_value:
                                if field.multiple:
                                    getattr(content, field_name).append(value)

                                    if field.type == 'repo' and repo_jobs:
                                        repo_jobs[-1]['repo_field_multi_index'] = len(getattr(content, field_name)) - 1
                                else:
                                    setattr(content, field_name, value)

                        elif field.name in single_valued_fields_with_values:
                            setattr(content, field_name, None)

                        if field.has_intensity and 'intensity' in datum:
                            content.set_intensity(field_name, value, datum['intensity'])

        content.save(relabel=True)

        if not bulk_editing:
            if repo_fields:
                for repo_field in repo_fields:
                    if ct_fields[repo_field].multiple:
                        for repo_index in range(0, len(getattr(content, repo_field))):
                            repo_name = getattr(content, repo_field)[repo_index].name
                            getattr(content, repo_field)[repo_index].path = "{0}/{1}/{2}".format(content.path, 'repos', repo_name)
                    else:
                        repo_name = getattr(content, repo_field).name
                        getattr(content, repo_field).path = "{0}/{1}/{2}".format(content.path, 'repos', repo_name)
                content.save()

            for repo_job in repo_jobs:
                repo_job['repo_content_id'] = str(content.id)
                corpus.queue_local_job(task_name="Pull Repo", parameters=repo_job)

            # Let's cleanup stale files before moving any temp uploads to their permanent spot.
            # This will improve the chances of files living in folders that correspond to their field names
            if files_to_delete:
                for file_to_delete in files_to_delete:
                    if os.path.exists(file_to_delete):
                        os.remove(file_to_delete)
                        stale_folder = os.path.dirname(file_to_delete)
                        is_empty = len(os.listdir(stale_folder)) == 0
                        if stale_folder not in [content.path, f"{content.path}/files"] and is_empty:
                            os.rmdir(stale_folder)

            if post_save_file_moves:
                for post_save_file_move in post_save_file_moves:
                    if post_save_file_move['multiple']:
                        for value_index in range(0, len(getattr(content, post_save_file_move['field']))):
                            if settings.DJANGO_DRF_FILEPOND_UPLOAD_TMP in getattr(content, post_save_file_move['field'])[value_index].path:
                                content._move_temp_file(
                                    post_save_file_move['field'],
                                    value_index,
                                    new_basename=post_save_file_move['upload'].upload_name.replace(' ', '_').replace('%20', '_')
                                )
                    else:
                        content._move_temp_file(
                            post_save_file_move['field'],
                            new_basename=post_save_file_move['upload'].upload_name.replace(' ', '_').replace('%20', '_')
                        )

                    post_save_file_move['upload'].delete()

                content.save(relabel=True)

    return content


def process_corpus_backup_file(backup_file):
    if backup_file:
        if not backup_file.startswith('/corpora/backups'):
            backup_file = os.path.join('/corpora/backups', backup_file)

        if os.path.exists(backup_file):
            basename = os.path.basename(backup_file)
            if '_' in basename and basename.endswith('.tar.gz'):
                backup_name = basename.split('.')[0]
                backup_name = "_".join(backup_name.split('_')[1:])
                backup_corpus = None

                with tarfile.open(backup_file, 'r:gz') as tar_in:
                    backup_corpus = tar_in.extractfile('corpus.json').read()

                if backup_corpus:
                    backup_corpus = json.loads(backup_corpus)
                    if _contains(backup_corpus, ['id', 'name', 'description']):
                        backup = CorpusBackup()
                        backup.name = backup_name
                        backup.corpus_id = backup_corpus['id']
                        backup.corpus_name = backup_corpus['name']
                        backup.corpus_description = backup_corpus['description']
                        backup.path = backup_file
                        backup.save()

                        return True
    return False


def send_alert(corpus_id, alert_type, message):
    send_event(corpus_id, 'event', {'event_type': 'alert', 'type': alert_type, 'message': message})


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


def _replace_all(target, replacement_pairs):
    for pair in replacement_pairs:
        target = target.replace(pair[0], pair[1])
    return target


def _clean(obj, key, default_value=''):
    val = obj.get(key, False)
    if val:
        return escape(val).strip()
    else:
        return default_value


def fix_mongo_json(json_string):
    json_string = mongo_id_pattern.sub(r'"\1"', json_string)
    json_string = mongo_date_pattern.sub(r'\1', json_string)
    return json_string.replace('"_id"', '"id"')


def delimit_content_json(contents, delimiter=', '):
    return delimiter.join([fix_mongo_json(c.to_json()) for c in contents])


def convert_content_to_csv_row(content):
        """
        Converts a Content object to a CSV row.

        Args:
            content: Content object to output to CSV row

        Returns:
            CSV values in correct order
        """

        internal_list_delimiter = '|'

        # Preallocate result array
        values = [''] * len(content._ct.fields)
        for field_index in range(0, len(content._ct.fields)):
            field = content._ct.fields[field_index]
            if getattr(content, field.name) not in ['', None] and field.type != 'embedded':
                field_values = [getattr(content, field.name)]
                if field.multiple:
                    field_values = getattr(content, field.name)

                if field.type in ['text', 'large_text', 'keyword', 'html', 'choice']:
                    for field_value_index in range(0, len(field_values)):
                        field_values[field_value_index] = field_values[field_value_index].replace('"', '""')

                elif field.type == 'cross_reference':
                    for field_value_index in range(0, len(field_values)):
                        field_values[field_value_index] = f"{field_values[field_value_index].id}"

                elif field.type == 'date':
                    for field_value_index in range(0, len(field_values)):
                        field_values[field_value_index] = field_values[field_value_index].strftime('%Y-%m-%d')

                elif field.type == 'geo_point':
                    for field_value_index in range(0, len(field_values)):
                        field_values[field_value_index] = f"{field_values[field_value_index]['coordinates']}"

                elif field.type == 'timespan':
                    for field_value_index in range(0, len(field_values)):
                        field_values[field_value_index] = field_values[field_value_index].string_representation

                elif field.type == 'file':
                    for field_value_index in range(0, len(field_values)):
                        field_values[field_value_index] = field_values[field_value_index].path

                elif field.type == 'repo':
                    for field_value_index in range(0, len(field_values)):
                        field_values[field_value_index] = f"{field_values[field_value_index].remote_url} ({field_values[field_value_index].remote_branch})"

                else:
                    for field_value_index in range(0, len(field_values)):
                        field_values[field_value_index] = f"{field_values[field_value_index]}"

                csv_value = internal_list_delimiter.join(field_values)

                if field.type in ['text', 'large_text', 'keyword', 'html', 'choice', 'geo_point', 'timespan', 'file', 'repo']:
                    if field.type == 'html':
                        csv_value = csv_value.replace('\n', ' ')

                    csv_value = f'"{csv_value.strip()}"'

                values[field_index] = csv_value

        escaped_label = content.label.replace('"', '""')
        values = [str(content.id), f'"{escaped_label}"', content.uri] + values
        return ','.join(values)


def create_content_csv_rows(contents):
    return '\n'.join([convert_content_to_csv_row(c) for c in contents])
