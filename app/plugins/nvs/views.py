import time
import re
from django.shortcuts import render, HttpResponse, redirect
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
from corpus import *
from mongoengine.queryset.visitor import Q
from manager.utilities import _get_context, get_scholar_corpus, _contains, _clean, parse_uri, build_search_params_from_dict
from importlib import reload
from plugins.nvs import tasks
from rest_framework.decorators import api_view
from math import floor
from PIL import Image, ImageDraw
from elasticsearch_dsl import A


def splash(request):
    return render(
        request,
        'splash.html',
        {}
    )


def playviewer(request, corpus_id=None, play_prefix=None):
    site_request = False
    corpora_url = 'https://' if settings.USE_SSL else 'http://'
    corpora_url += settings.ALLOWED_HOSTS[0]
    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]
    nvs_session = get_nvs_session(request, play_prefix, reset='reset' in request.GET)

    # GET params
    act_scene = request.GET.get('act-scene', nvs_session['filter']['act_scene'])
    character = request.GET.get('character', nvs_session['filter']['character'])

    lines = []
    witnesses = {}
    witness_centuries = {}

    session_changed = False

    if 'play_id' not in nvs_session or nvs_session['play_id'] != str(play.id):
        nvs_session['play_id'] = str(play.id)
        session_changed = True
    if nvs_session['filter']['character'] != character:
        nvs_session['filter']['character'] = character
        nvs_session['filter']['character_lines'] = []
        session_changed = True
    if nvs_session['filter']['act_scene'] != act_scene:
        nvs_session['filter']['act_scene'] = act_scene
        session_changed = True

    if session_changed:
        nvs_session['is_filtered'] = character != 'all' or act_scene != 'all'
        nvs_session['filter']['no_results'] = False

        if character != 'all':
            char_line_results = corpus.search_content(
                content_type='Speech',
                page=1,
                page_size=5000,
                fields_filter={'play.id': str(play.id), 'speaking.xml_id': character},
                fields_sort=[{'lines.line_number': {'order': 'ASC'}}],
                only=['lines.id']
            )
            if char_line_results['records']:
                for record in char_line_results['records']:
                    for line in record['lines']:
                        nvs_session['filter']['character_lines'].append(line['id'])
            else:
                nvs_session['filter']['no_results'] = True

        set_nvs_session(request, nvs_session, play_prefix)

    lines = get_session_lines(corpus, nvs_session)

    notes = {}
    line_note_map = {}
    note_results = corpus.search_content(
        'TextualNote',
        page_size=10000,
        fields_filter={
            'play.id': str(play.id)
        },
        fields_sort=[{'lines.line_number': {'order': 'asc'}}],
        only=['xml_id', 'variants', 'lines.xml_id']
    )
    if note_results and 'records':
        for note in note_results['records']:
            notes[note['xml_id']] = note
            for line in note['lines']:
                if line['xml_id'] not in line_note_map:
                    line_note_map[line['xml_id']] = [note['xml_id']]
                else:
                    line_note_map[line['xml_id']].append(note['xml_id'])

    act_scenes = {}
    as_search = {
        'page-size': 0,
        'e_act': 'y',
        'e_scene': 'y',
        'f_play.id': str(play.id),
        'a_terms_act_scenes': 'act,scene',
    }
    as_search_params = build_search_params_from_dict(as_search)
    as_results = corpus.search_content('PlayLine', **as_search_params)
    if as_results:
        if 'Dramatis Personae|||0' in as_results['meta']['aggregations']['act_scenes']:
            act_scenes['DP'] = "Dramatis Personae.0"

        act_scene_keys = sorted(as_results['meta']['aggregations']['act_scenes'].keys())
        for act_scene in act_scene_keys:
            if act_scene not in ['Dramatis Personae|||0', 'Trailer|||0']:
                as_parts = act_scene.split('|||')
                act = as_parts[0]
                scene = as_parts[1]
                act_label = to_roman(int(act))
                act_scene_label = "{0}.{1}".format(act_label, scene)
                act_scenes[act_scene_label] = "{0}.{1}".format(act, scene)

        if 'Trailer|||0' in as_results['meta']['aggregations']['act_scenes']:
            act_scenes['TR'] = "Trailer.0"

    witness_docs = corpus.get_content('Document', {'nvs_doc_type': 'witness'}).order_by('pub_date')
    play_wit_ids = [w.id for w in play.primary_witnesses]
    wit_counter = 0
    for wit_doc in witness_docs:
        if wit_doc.id in play_wit_ids:
            witnesses[wit_doc.siglum] = {
                'slots': [wit_counter],
                'document_id': str(wit_doc.id),
                'bibliographic_entry': wit_doc.bibliographic_entry
            }

            century = wit_doc.pub_date[:2] + "00"
            if century in witness_centuries:
                witness_centuries[century] += 1
            else:
                witness_centuries[century] = 1

            wit_counter += 1

    document_collections = corpus.get_content('DocumentCollection', all=True)
    for collection in document_collections:
        slots = []
        bib_entry = ""

        for reffed_doc in collection.referenced_documents:
            if reffed_doc.siglum in witnesses:
                slots += witnesses[reffed_doc.siglum]['slots']
                if bib_entry:
                    bib_entry += "<br /><br />"
                bib_entry += reffed_doc.bibliographic_entry

        witnesses[collection.siglum] = {
            'slots': slots,
            'bibliographic_entry': bib_entry
        }


    return render(
        request,
        'playviewer.html',
        {
            'site_request': site_request,
            'corpora_url': corpora_url,
            'corpus_id': corpus_id,
            'lines': lines,
            'act_scenes': act_scenes,
            'notes': json.dumps(notes),
            'line_note_map': line_note_map,
            'play': play,
            'witnesses': witnesses,
            'witness_centuries': witness_centuries,
            'witness_count': wit_counter,
            'nvs_session': nvs_session
        }
    )


def get_session_lines(corpus, session, only_ids=False):
    if session['filter']['no_results']:
        return []

    line_criteria = {
        'play': session['play_id'],
    }

    if session['filter']['act_scene'] != 'all':
        act_scene_parts = session['filter']['act_scene'].split('.')
        line_criteria['act'] = act_scene_parts[0]
        if len(act_scene_parts) > 1:
            line_criteria['scene'] = act_scene_parts[1]

    if session['filter']['character_lines']:
        line_criteria['id__in'] = session['filter']['character_lines']

    lines = corpus.get_content('PlayLine', line_criteria).order_by('line_number')
    if only_ids:
        lines = lines.only('id')
    return lines


def bibliography(request, corpus_id, play_prefix):
    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]

    docs = corpus.get_content('Document', all=True).order_by('bibliographic_entry_text')
    bibliographic_entries = [doc.bibliographic_entry for doc in docs]

    return render(
        request,
        'bibliography.html',
        {
            'corpus_id': corpus_id,
            'bibliography': bibliographic_entries
        }
    )


def paratext(request, corpus_id=None, play_prefix=None, section=None):
    corpora_url = 'https://' if settings.USE_SSL else 'http://'
    corpora_url += settings.ALLOWED_HOSTS[0]
    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix}, single_result=True)
    section_toc = "<ul>"
    section_html = ""

    top_paratexts = corpus.get_content('ParaText', {
        'play': play.id,
        'section': section,
        'level': 1
    }).order_by('order')

    for pt in top_paratexts:
        section_toc += pt.toc_html
        section_html += pt.full_html.replace('/file/uri/', "{0}/file/uri/".format(corpora_url))

    section_toc += "</ul>"

    return render(
        request,
        'paratext.html',
        {
            'corpus_id': corpus_id,
            'play': play,
            'section': section,
            'toc': section_toc,
            'html': section_html
        }
    )


def witness_meter(request, witness_flags, height, width, inactive_color_hex):
    if height.isdigit() and width.isdigit():
        height = int(height)
        width = int(width)
        color_map = {
            '0': '#' + inactive_color_hex,
            '1': '#f7bb78',
            '2': '#faae63',
            '3': '#f99b4e',
            '4': '#ef8537',
            '5': '#d87b48',
            '6': '#de6d4b',
            '7': '#bd5822',
            '8': '#a84f1f',
            '9': '#8f2d13',
            'x': '#c4dffc'
        }
        indicator_width = width / len(witness_flags)
        img = Image.new('RGBA', (width, height), (255, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        for flag_index in range(0, len(witness_flags)):
            indicator_color = color_map[witness_flags[flag_index]]
            start_x = flag_index * indicator_width
            start_y = 0
            end_x = start_x + indicator_width - 2
            end_y = height

            draw.rectangle(
                [(start_x, start_y), (end_x, end_y)],
                fill=indicator_color,
                outline=None,
                width=0
            )

        response = HttpResponse(content_type="image/png")
        img.save(response, 'PNG')
        return response


def play_minimap(request, corpus_id=None, play_prefix=None):
    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]
    nvs_session = get_nvs_session(request, play_prefix)
    lines = get_session_lines(corpus, nvs_session)
    highlight_lines = []
    if 'results' in nvs_session['search']:
        highlight_lines = [l['xml_id'] for l in nvs_session['search']['results']['lines']]

    width = request.GET.get('width', '300')
    height = request.GET.get('height', '900')
    line_count = 0
    max_line_length = 10

    line_height = 3
    line_spacing = 2

    if width.isdigit() and height.isdigit():
        width = int(width)
        height = int(height)
        ratio = width / height

        for line in lines:
            line_count += 1
            if len(line.text) > max_line_length:
                max_line_length = len(line.text)

        if line_count > 0:
            min_img_height = (line_count * line_height) + ((line_count - 1) * line_spacing)
            while min_img_height < height:
                line_height += 2
                line_spacing += 1
                min_img_height = (line_count * line_height) + ((line_count - 1) * line_spacing)

            min_img_width = int(min_img_height * ratio)
            character_width = int(min_img_width / max_line_length)

            img = Image.new('RGB', (min_img_width, min_img_height), '#F2F2F2')
            draw = ImageDraw.Draw(img)

            x = 0
            y = 0
            emphasis_lines = 0

            for line in lines:
                draw_highlight = False

                if line.xml_id in highlight_lines:
                    draw_highlight = True
                    emphasis_lines = 5
                elif emphasis_lines > 0:
                    draw_highlight = True
                    emphasis_lines -= 1

                if draw_highlight:
                    line_color = '#F99B4E'
                    draw.rectangle([(0, y), (max_line_length * character_width, y + line_height)], fill=line_color, outline=None, width=0)
                else:
                    line_color = '#9A9A99'
                    word_start = None

                    for char_index in range(0, len(line.text)):
                        char = line.text[char_index]

                        if not word_start:
                            word_start = x

                        if (char == ' ' or char_index == len(line.text) - 1) and word_start:
                            word_end = x
                            draw.rectangle([(word_start, y), (word_end, y + line_height)], fill=line_color, outline=None, width=0)
                            word_start = None
                            x += character_width
                        else:
                            x += character_width

                x = 0
                y += (line_height + line_spacing)

            response = HttpResponse(content_type="image/png")
            img.save(response, 'PNG')
            return response


def info_about(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_about'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_about.html',
        {
            'corpus_id': corpus_id,
            'content': dynamic_content
        }
    )


def info_contributors(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_contributors'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_contributors.html',
        {
            'corpus_id': corpus_id,
            'content': dynamic_content
        }
    )


def info_print_editions(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_print'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_print.html',
        {
            'corpus_id': corpus_id,
            'content': dynamic_content
        }
    )


def info_how_to(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_how_to'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_how_to.html',
        {
            'corpus_id': corpus_id,
            'content': dynamic_content
        }
    )


def info_faqs(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_faqs'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_faqs.html',
        {
            'corpus_id': corpus_id,
            'content': dynamic_content
        }
    )


def tools_about(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'tools_about'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'tools_about.html',
        {
            'corpus_id': corpus_id,
            'content': dynamic_content
        }
    )


def tools_advanced_search(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'tools_advanced_search'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'tools_advanced_search.html',
        {
            'corpus_id': corpus_id,
            'content': dynamic_content
        }
    )


def tools_data_extraction(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'tools_data'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'tools_data.html',
        {
            'corpus_id': corpus_id,
            'content': dynamic_content
        }
    )


@api_view(['GET'])
def api_lines(request, corpus_id, starting_line_no, ending_line_no):
    context = _get_context(request)
    lines = []

    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and 'PlayLine' in corpus.content_types:
        lines = corpus.get_content('PlayLine', {'line_number__gte': starting_line_no, 'line_number__lte': ending_line_no})
        lines = lines.order_by('line_number')
        lines = [line.to_dict() for line in lines]

    return HttpResponse(
        json.dumps(lines),
        content_type='application/json'
    )


def api_search(request, corpus_id=None, play_prefix=None):
    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]
    nvs_session = get_nvs_session(request, play_prefix)

    quick_search = request.POST.get('quick_search', None)

    results = {
        'characters': {},
        'lines': [],
        'variants': [],
        'commentaries': [],
        'last_commentary_line': 0
    }

    if quick_search:
        # SEARCH PLAY LINES VIA Speech CT
        speech_query = {
            'content_type': 'Speech',
            'page': 1,
            'page_size': 1000,
            'fields_filter': {
                'play.id': str(play.id)
            },
            'only': ['act', 'scene', 'speaking'],
            'fields_highlight': ['text'],
            'highlight_num_fragments': 0
        }
        # print('SPEECHES')
        qs_results = progressive_search(corpus, speech_query, ['text'], quick_search)

        for record in qs_results['records']:
            for speaker in record['speaking']:
                sp_xml_id = speaker['xml_id']
                act_scene = float("{0}.{1}".format(record['act'], record['scene']))

                if sp_xml_id not in results['characters']:
                    results['characters'][sp_xml_id] = {}

                if act_scene not in results['characters'][sp_xml_id]:
                    results['characters'][sp_xml_id][act_scene] = 1
                else:
                    results['characters'][sp_xml_id][act_scene] += 1

            for speech in record['_search_highlights']['text']:
                lines = [l for l in speech.split('<tln_') if l]
                for line in lines:
                    matches = re.findall(r'<em>([^<]*)</em>', line)
                    if matches:
                        line_xml_id = "tln_{0}".format(line[:line.index(' />')])
                        results['lines'].append({
                            'xml_id': line_xml_id,
                            'matches': matches
                        })

        # SEARCH VARIANTS VIA TextualNote CT
        variant_query = {
            'content_type': 'TextualNote',
            'page': 1,
            'page_size': 1000,
            'fields_filter': {
                'play.id': str(play.id)
            },
            'only': ['lines.xml_id', 'variants.id'],
            'fields_highlight': ['variants.variant', 'variants.description'],
            'highlight_num_fragments': 0,
        }
        # print('VARIANTS')
        variant_results = progressive_search(corpus, variant_query, ['variants.variant', 'variants.description'], quick_search)
        variant_lines = {}
        for record in variant_results['records']:
            variant_line_id = record['lines'][0]['xml_id']
            if variant_line_id not in variant_lines:
                result = {
                    'xml_id': variant_line_id,
                    'matches': []
                }
                if 'variants.variant' in record['_search_highlights']:
                    for highlight in record['_search_highlights']['variants.variant']:
                        matches = re.findall(r'<em>([^<]*)</em>', highlight)
                        if matches:
                            result['matches'] += matches
                if 'variants.description' in record['_search_highlights']:
                    for highlight in record['_search_highlights']['variants.description']:
                        matches = re.findall(r'<em>([^<]*)</em>', highlight)
                        if matches:
                            result['matches'] += matches

                results['variants'].append(result)
                variant_lines[variant_line_id] = True

        # Search Commentary
        comm_query = {
            'content_type': 'Commentary',
            'page': 1,
            'page_size': 1000,
            'fields_filter': {
                'play.id': str(play.id)
            },
            'only': ['id', 'lines.line_number'],
            'fields_highlight': ['subject_matter', 'contents'],
        }
        # print('COMMENTARY')
        comm_results = progressive_search(corpus, comm_query, ['subject_matter', 'contents'], quick_search)

        for record in comm_results['records']:
            if 'lines' in record:
                for line in record['lines']:
                    if line['line_number'] > results['last_commentary_line']:
                        results['last_commentary_line'] = line['line_number']

                result = {
                    'comm_id': record['id'],
                    'matches': []
                }
                if 'subject_matter' in record['_search_highlights']:
                    for highlight in record['_search_highlights']['subject_matter']:
                        matches = re.findall(r'<em>([^<]*)</em>', highlight)
                        if matches:
                            result['matches'] += matches
                if 'contents' in record['_search_highlights']:
                    for highlight in record['_search_highlights']['contents']:
                        matches = re.findall(r'<em>([^<]*)</em>', highlight)
                        if matches:
                            result['matches'] += matches
                result['matches'] = list(set(result['matches']))
                results['commentaries'].append(result)

        nvs_session['search']['quick_search'] = quick_search
        nvs_session['search']['results'] = results
        set_nvs_session(request, nvs_session, play_prefix)

    return HttpResponse(
        json.dumps(results),
        content_type='application/json'
    )


def progressive_search(corpus, search_params, fields, query):
    if len(fields) > 1:
        search_params['operator'] = "or"

    fields_dict = {}
    for field in fields:
        fields_dict[field] = query

    #print('trying term...')
    search_params['fields_term'] = fields_dict
    results = corpus.search_content(**search_params)

    if not results['records']:
        #print('trying phrase...')
        del search_params['fields_term']
        search_params['fields_phrase'] = fields_dict
        results = corpus.search_content(**search_params)

    if not results['records']:
        #print('trying fields...')
        del search_params['fields_phrase']
        search_params['fields_query'] = fields_dict
        results = corpus.search_content(**search_params)

    if not results['records']:
        #print('trying no stopwords...')
        adjusted_query = query.lower().split()
        for stopword in "a an and are as at be but by for if in into is it no not of on or such that the their then there these they this to was will with".split():
            if stopword in adjusted_query:
                adjusted_query.remove(stopword)
        adjusted_query = ' '.join(adjusted_query)
        for field in fields:
            search_params['fields_query'][field] = adjusted_query
        results = corpus.search_content(**search_params)
    '''
    if not results['records']:
        print('trying general...')
        del search_params['fields_query']
        search_params['general_query'] = query
        results = corpus.search_content(**search_params)
    '''

    return results


def set_nvs_session(request, session, play_prefix):
    request.session["nvs_scholar_session_{0}".format(play_prefix)] = json.dumps(session)


def get_nvs_session(request, play_prefix, deserialize=True, reset=False):
    sess = request.session.get("nvs_scholar_session_{0}".format(play_prefix), None)

    if reset:
        sess = None

    if sess and deserialize:
        return json.loads(sess)
    elif sess:
        return sess
    else:
        default_session = {
            'search': {},
            'is_filtered': False,
            'filter': {
                'act_scene': 'all',
                'character': 'all',
                'character_lines': [],
                'no_results': False
            },
            'preferences': {
                'show_quantitative_view': False,
                'show_reader_view': True,
                'show_list_view': False
            }
        }

        if deserialize:
            return default_session
        return json.dumps(default_session)


def api_nvs_session(request, play_prefix):
    return HttpResponse(
        get_nvs_session(request, play_prefix, deserialize=False),
        content_type='application/json'
    )


def to_roman(number):
    roman = ""
    num = [1, 4, 5, 9, 10, 40, 50, 90,
           100, 400, 500, 900, 1000]
    sym = ["I", "IV", "V", "IX", "X", "XL",
           "L", "XC", "C", "CD", "D", "CM", "M"]
    i = 12
    while number:
        div = number // num[i]
        number %= num[i]

        while div:
            roman += sym[i]
            div -= 1
        i -= 1
    return roman