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


def get_file(scholar, corpus_id, document_id, file_key, ref_no=None):
    file = None

    try:
        if ref_no:
            document = get_document(scholar, corpus_id, document_id, ['pages.{0}.files.{1}'.format(ref_no, file_key)])
            if document:
                file = document.pages[ref_no].files[file_key]
        else:
            document = get_document(scholar, corpus_id, document_id, ['files.{0}'.format(file_key)])
            if document:
                file = document.files[file_key]
    except:
        print("Error retrieving file!")

    return file


def get_tasks(scholar):
    tasks = []

    if scholar:
        if scholar.is_admin:
            tasks = Task.objects
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


def get_document_page_file_collections(scholar, corpus_id, document_id, pfc_slug=None):
    page_file_collections = {}
    corpus = get_scholar_corpus(corpus_id, scholar, only=['id'])
    if corpus:
        if pfc_slug:
            pfc = Document.get_page_file_collection(corpus_id, document_id, pfc_slug)
            if pfc:
                page_file_collections[pfc_slug] = pfc
        else:
            document = corpus.get_document(document_id)
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


def reset_page_extraction(corpus_id, document_id):
    corpus = get_corpus(corpus_id)
    if corpus:
        document = corpus.get_document(document_id)
        if document:
            print('found objects')

            dirs_to_delete = [
                "{0}/temporary_uploads".format(document.path),
                "{0}/files".format(document.path),
                "{0}/pages".format(document.path),
            ]

            for dir_to_delete in dirs_to_delete:
                if os.path.exists(dir_to_delete):
                    print('found {0}'.format(dir_to_delete))
                    shutil.rmtree(dir_to_delete)

            document.files = []
            document.pages = {}
            document.jobs = []
            corpus.jobs = []

            document.save(index_pages=True)
            corpus.save()


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

            # make sure all fields_query fields are in corpus field settings...
            for field_name in fields_query.keys():
                if not (field_name in corpus.field_settings and corpus.field_settings[field_name]['display']):
                    sane = False
                    break

            # make sure all fields_sort fields are in corpus field settings...
            for sort_entry in fields_sort:
                field_name = sort_entry
                if sort_entry.startswith('-'):
                    field_name = field_name[1:]
                if sort_entry.endswith('.raw'):
                    field_name = field_name[:-4]

                if field_name in corpus.field_settings and corpus.field_settings[field_name]['sort']:
                    if corpus.field_settings[field_name]['type'] != 'text' and sort_entry.endswith('.raw'):
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
    resp = {
        'errors': [],
        'messages': [],
        'scholar': {},
        'url': req.build_absolute_uri(req.get_full_path()),
        'page': int(_clean(req.GET, 'page', 1)),
        'per_page': int(_clean(req.GET, 'per-page', 50)),
    }

    resp['start_index'] = (resp['page'] - 1) * resp['per_page']
    resp['end_index'] = resp['start_index'] + resp['per_page']

    if 'msg' in req.GET:
        resp['messages'].append(req.GET['msg'])

    if req.user.is_authenticated:
        scholar_json = req.session.get('scholar_json', None)
        if scholar_json:
            resp['scholar'] = Scholar.from_json(scholar_json)
        else:
            try:
                resp['scholar'] = Scholar.objects(username=req.user.username)[0]
                req.session['scholar_json'] = resp['scholar'].to_json()
            except:
                print(traceback.format_exc())
                resp['scholar'] = {}

    return resp


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

