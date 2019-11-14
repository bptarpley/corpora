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


def get_scholar_corpora(scholar):
    corpora = []

    if scholar:
        if scholar.is_admin:
            corpora = Corpus.objects
        else:
            corpora = Corpus.objects(Q(id__in=[c.id for c in scholar.available_corpora]) | Q(open_access=True))
    else:
        corpora = Corpus.objects(open_access=True)

    return corpora


def get_scholar_corpus(corpus_id, scholar):
    corpus = None

    corpus = get_corpus(corpus_id)
    if corpus:
        if not (corpus.open_access or (scholar and scholar.is_admin) or (scholar and corpus in scholar.avialable_corpora)):
            corpus = None

    return corpus


def get_documents(corpus_id, request, response):
    documents = []
    corpus = None
    count = 0
    num_pages = 0
    order = "+author"
    query = None
    query_type = None

    corpus = get_scholar_corpus(corpus_id, response['scholar'])
    projection = [setting['field'] for setting in corpus.field_settings if setting['display']]
    projection.append("id")

    if corpus:
        order = _clean(request.GET, 'order', '+author').strip()
        query = _clean(request.GET, 'query', None)
        query_type = _clean(request.GET, 'query-type', None)

        if query and query_type:
            if query_type == 'default':
                count = Document.objects(corpus=corpus).search_text('"' + query + '"').count()
                documents = Document.objects(corpus=corpus).search_text('"' + query + '"').order_by('$text_score').only(*projection)
            else:
                for setting in corpus.field_settings:
                    if query_type.replace('__', '.') == setting['field']:
                        if setting.get('type') == 'int':
                            try:
                                query = int(query.strip())
                            except:
                                response['errors'].append('Search query must be a number for this field.')

                filters = {
                    'corpus': corpus,
                    query_type: query
                }
                count = Document.objects(**filters).count()
                documents = Document.objects(**filters).order_by(order).only(*projection)

        else:
            count = Document.objects(corpus=corpus).count()
            documents = Document.objects(corpus=corpus).order_by(order).only(*projection)

        num_pages = ceil(count / response['per_page'])

    return documents[response['start_index']:response['end_index']], count, num_pages


def get_document(scholar, corpus_id, document_id, only=[]):
    doc = None
    corpus = get_scholar_corpus(corpus_id, scholar)

    if corpus:
        doc = corpus.get_document(document_id, only)

    return doc


def get_tasks(scholar):
    tasks = []

    if scholar:
        if scholar.is_admin:
            tasks = Task.objects
        else:
            tasks = Task.objects(id__in=[t.id for t in scholar.available_tasks])

    return tasks


def get_jobsites(scholar):
    jobsites = []

    if scholar:
        if scholar.is_admin:
            jobsites = JobSite.objects
        else:
            jobsites = JobSite.objects(id__in=[j.id for j in scholar.available_jobsites])

    return jobsites


def get_document_page_file_collections(scholar, corpus_id, document_id):
    page_file_collections = {}
    corpus = get_scholar_corpus(corpus_id, scholar)
    if corpus:
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


def setup_document_directory(corpus_id, document_id):
    corpus = get_corpus(corpus_id)
    if corpus:
        document = corpus.get_document(document_id)
        if document:
            document_path = "/corpora/{0}/{1}".format(corpus_id, document_id)
            os.makedirs(document.path, exist_ok=True)
            if not document.path or document.path != document_path:
                document.path = document_path
                document.update(set__path="/corpora/{0}/{1}".format(corpus_id, document_id))


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
        try:
            resp['scholar'] = Scholar.objects(username=req.user.username)[0]
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

