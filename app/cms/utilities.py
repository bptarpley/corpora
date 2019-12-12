from math import ceil
from django.utils.html import escape
from . import ContentType, Page, ContentList
from manager.utilities import get_scholar_corpus
from django.template import Template, Context


def _get_context(request):
    pages = []
    page_objects = Page.objects().order_by('+nav_parent', '+nav_location')

    for page in page_objects:
        if page.show_in_nav:
            pages.append({
                'title': page.title,
                'url': page.url,
                'nav_parent': page.nav_parent,
                'children': []
            })

    x = len(pages) - 1
    while x >= 0:
        if pages[x]['nav_parent']:
            for y in range(0, len(pages)):
                if pages[x]['nav_parent'] == pages[y]['url']:
                    pages[y]['children'].append(pages.pop(x))
                    break
        x -= 1

    return {
        'is_admin': request.user.is_superuser,
        'content_types': ContentType.objects,
        'pages': pages
    }


def _clean(obj, key, default_value=''):
    val = obj.get(key, False)
    if val:
        return escape(val)
    return default_value


def _contains(obj, keys):
    for key in keys:
        if key not in obj:
            return False
    return True


def get_content_search_results(request, scholar, corpus_id, content_type_name):
    valid_search = False
    results = {
        'meta': {
            'content_type': content_type_name,
            'total': 0,
            'page': 1,
            'page_size': 50,
            'num_pages': 1,
            'has_next_page': False
        },
        'records': []
    }

    corpus = get_scholar_corpus(corpus_id, scholar, only=['id'])
    if corpus:
        content_type = ContentType.objects(corpus=corpus_id, name=content_type_name)[0]
        search_results = []
        general_search_query = None
        render_template = None
        only = []
        fields_query = {}
        fields_sort = []

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
            elif query_field == 'render_template':
                render_template = _clean(request.GET, query_field)
            elif query_field == 'only':
                only = _clean(request.GET, query_field).split(',')

        start_record = (results['meta']['page'] - 1) * results['meta']['page_size']
        end_record = start_record + results['meta']['page_size']

        if not valid_search:
            general_search_query = '*'
            valid_search = True

        if valid_search and content_type:
            sane = True
            ct_fields = {}
            for f_index in range(0, len(content_type.fields)):
                ct_fields[content_type.fields[f_index].name] = f_index

            # make sure all fields_query fields are in content type...
            for field_name in fields_query.keys():
                if not (field_name in ct_fields and content_type.fields[ct_fields[field_name]]['in_lists'] or content_type.fields[ct_fields[field_name]]['indexed']):
                    sane = False
                    break

            # make sure all fields_sort fields are in content type...
            for sort_entry in fields_sort:
                field_name = sort_entry
                if sort_entry.startswith('-'):
                    field_name = field_name[1:]
                if sort_entry.endswith('.raw'):
                    field_name = field_name[:-4]

                if field_name in ct_fields and content_type.fields[ct_fields[field_name]]['in_lists']:
                    if content_type.fields[ct_fields[field_name]]['type'] != 'text' and sort_entry.endswith('.raw'):
                        fields_sort[fields_sort.index(sort_entry)] = sort_entry[:-4]
                else:
                    sane = False
                    break

            # make sure all only fields are in content type...
            if only and not _contains(ct_fields, only):
                sane = False

            if sane:
                contents = ContentList(
                    corpus_id,
                    content_type,
                    page_size=results['meta']['page_size'],
                    current_page=results['meta']['page'],
                    search=general_search_query,
                    query=fields_query,
                    sort=fields_sort,
                    only=only
                )
                results['meta']['total'] = contents.count
                results['meta']['num_pages'] = ceil(results['meta']['total'] / results['meta']['page_size'])
                results['meta']['has_next_page'] = results['meta']['num_pages'] > results['meta']['page']

                for content in contents:
                    content_json = {
                        'id': content.id,
                        'label': content.label,
                        'url': content.url,
                        'fields': content.fields
                    }
                    if render_template:
                        for field in content.fields.keys():
                            template_string = "{{% load extras %}}{0}".format(
                                contents.get_template('field_templates')[field])
                            template = Template(template_string)
                            template_context = Context({
                                content_type: content,
                            })
                            content_json['fields'][field]['_template'] = template.render(template_context)

                    results['records'].append(content_json)

    return results
