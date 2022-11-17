import time
import re
from django.shortcuts import render, HttpResponse, redirect
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
from corpus import *
from mongoengine.queryset.visitor import Q
from manager.utilities import _get_context, get_scholar_corpus, _contains, _contains_any, parse_uri, build_search_params_from_dict
from importlib import reload
from plugins.nvs import tasks
from rest_framework.decorators import api_view
from math import floor
from PIL import Image, ImageDraw
from elasticsearch_dsl import A


# TEMPORARY FIX FOR SOFT LAUNCH
editors = {
    'wt': "ROBERT KEAN TURNER, VIRGINIA WESTLING HAAS, with ROBERT A. JONES, ANDREW J. SABOL, PATRICIA E. TATSPAUGH",
    'mnd': "Judith M. Kennedy and Richard Kennedy, with Susan May, Roberta Barker, David Nicol",
    'lr': "Richard Knowles, Kevin Donovan, with Paula Glatzer"
}

def splash(request):
    return render(
        request,
        'splash.html',
        {}
    )


def playviewer(request, corpus_id=None, play_prefix=None):
    start_time = time.time()

    nvs_page = "variorum-viewer"
    site_request = False
    corpora_url = 'https://' if settings.USE_SSL else 'http://'
    corpora_url += settings.ALLOWED_HOSTS[0]
    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    on_mobile = False
    user_agent = request.META['HTTP_USER_AGENT']
    if _contains_any(user_agent, ['Mobile', 'Opera Mini', 'Android']):
        on_mobile = True

    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]
    nvs_session = get_nvs_session(request, play_prefix, reset='reset' in request.GET)

    # HANDLE GET PARAMS
    act_scene = request.GET.get('scene', nvs_session['filter']['act_scene'])
    character = request.GET.get('character', nvs_session['filter']['character'])

    # BUILD LINES
    lines = []
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

        filter_session_lines_by_character(corpus, play, nvs_session)
        set_nvs_session(request, nvs_session, play_prefix)

    lines = get_session_lines(corpus, nvs_session)

    # LINE NOTE MAP
    line_note_map = {}
    note_results = corpus.search_content(
        'TextualNote',
        page_size=10000,
        fields_filter={
            'play.id': str(play.id)
        },
        fields_sort=[{'lines.line_number': {'order': 'asc'}}],
        only=['id', 'xml_id', 'lines.xml_id']
    )
    if note_results and 'records':
        for note in note_results['records']:
            #notes[note['xml_id']] = note
            for line in note['lines']:
                if line['xml_id'] not in line_note_map:
                    line_note_map[line['xml_id']] = [{
                        'id': note['id'],
                        'xml_id': note['xml_id']
                    }]
                else:
                    line_note_map[line['xml_id']].append({
                        'id': note['id'],
                        'xml_id': note['xml_id']
                    })

    # COMMENTARY IDS
    comm_ids = []
    comm_search = {
        'content_type': 'Commentary',
        'page': 1,
        'page_size': 10000,
        'fields_filter': {
            'play.id': str(play.id)
        },
        'fields_sort': [
            {'lines.line_number': {'order': 'asc'}},
            {'xml_id': {'order': 'asc'}}
        ],
        'only': ['id', 'xml_id'],
    }
    comm_results = corpus.search_content(**comm_search)
    for comm_result in comm_results['records']:
        comm_ids.append({'xml_id': comm_result['xml_id'], 'id': comm_result['id']})

    # CHARACTERS
    characters = []
    char_search = {
        'page-size': 0,
        'f_play.id': str(play.id),
        'a_terms_chars': 'speaking.xml_id,speaking.label.raw',
    }
    char_search_params = build_search_params_from_dict(char_search)
    char_results = corpus.search_content('Speech', **char_search_params)
    if char_results and 'aggregations' in char_results['meta'] and 'chars' in char_results['meta']['aggregations']:
        for char_info, num_speeches in char_results['meta']['aggregations']['chars'].items():
            char_id, char_name = char_info.split('|||')
            characters.append({
                'xml_id': char_id,
                'name': char_name,
                'speeches': num_speeches
            })

    # ACT SCENES
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
                # act_label = to_roman(int(act))
                act_scene_label = "{0}.{1}".format(act, scene)
                act_scenes[act_scene_label] = "{0}.{1}".format(act, scene)

        if 'Trailer|||0' in as_results['meta']['aggregations']['act_scenes']:
            act_scenes['TR'] = "Trailer.0"

    # WITNESSES
    witnesses, wit_counter, witness_centuries = get_nvs_witnesses(corpus, play)

    print(time.time() - start_time)

    return render(
        request,
        'playviewer.html',
        {
            'site_request': site_request,
            'on_mobile': on_mobile,
            'corpora_url': corpora_url,
            'corpus_id': corpus_id,
            'lines': lines,
            'act_scenes': act_scenes,
            'characters': characters,
            'comm_ids': comm_ids,
            'line_note_map': line_note_map,
            'play': play,
            'editors': editors[play_prefix],
            'witnesses': json.dumps(witnesses),
            'witness_centuries': witness_centuries,
            'witness_count': wit_counter,
            'nvs_session': nvs_session,
            'nvs_page': nvs_page
        }
    )


def get_session_lines(corpus, session, only_ids=False):
    if session['filter']['no_results']:
        return []

    line_criteria = {
        'play': session['play_id'],
    }

    if session['filter']['character_lines']:
        line_criteria['id__in'] = session['filter']['character_lines']

    lines = corpus.get_content('PlayLine', line_criteria).order_by('line_number')

    if session['filter']['act_scene'] != 'all':
        act_scenes = session['filter']['act_scene'].split(',')
        condition = None
        for act_scene in act_scenes:
            act, scene = act_scene.split('.')

            if not condition:
                condition = (Q(act=act) & Q(scene=scene))
            else:
                condition = condition | (Q(act=act) & Q(scene=scene))
        lines = lines.filter(condition)

    if only_ids:
        lines = lines.only('id', 'xml_id')
    return lines


def paratext(request, corpus_id=None, play_prefix=None, section=None):
    corpora_url = 'https://' if settings.USE_SSL else 'http://'
    corpora_url += settings.ALLOWED_HOSTS[0]
    site_request = False
    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix}, single_result=True)
    nvs_page = ""

    section_toc = ""
    section_html = ""

    if section in ['Appendix', 'Front Matter']:
        top_paratexts = corpus.get_content('ParaText', {
            'play': play.id,
            'section': section,
            'level': 1
        }).order_by('order')

        for pt in top_paratexts:
            section_toc += pt.toc_html
            section_html += pt.full_html.replace('/file/uri/', "{0}/file/uri/".format(corpora_url))

        nvs_page = "{0}-frontmatter".format(play_prefix)
        if section == "Appendix":
            nvs_page = "{0}-appendix".format(play_prefix)
    elif section == "Bibliography":
        marker_map = {
            'ABC': 'A-C',
            'DEF': 'D-F',
            'GHI': 'G-I',
            'JKL': 'J-L',
            'MNO': 'M-O',
            'PQR': 'P-R',
            'STU': 'S-U',
            'VWX': 'V-X',
            'YZ': 'Y-Z'
        }

        for letters in marker_map.keys():
            section_toc += '<li class="anchor-link is-level-1"><a href="#{0}">{0}</a></li>'.format(
                marker_map[letters]
            )

        last_marker = ""
        bibs = corpus.get_content("Reference", {'play': play.id, 'ref_type': 'bibliographic_source'}).order_by('+id')
        for bib in bibs:
            marker = last_marker
            if bib.bibliographic_entry_text:
                entry_text = bib.bibliographic_entry_text
                if entry_text.startswith('The '):
                    entry_text = entry_text[4:]
                for letters in marker_map.keys():
                    if _contains_any(entry_text[0], letters):
                        marker = marker_map[letters]
                        break

            if marker != last_marker:
                if section_html:
                    section_html += '</ul>'
                section_html += '<h3 class="bibliography-section">{0}</h3>'.format(marker)
                section_html += '<ul id="{0}" class="anchor">'.format(marker)
                last_marker = marker

            section_html += '<a name="{0}" class="anchor"></a><li class="bibl">{1}</li>'.format(
                bib.document.siglum,
                bib.bibliographic_entry
            )

        nvs_page = "{0}-bibliography".format(play_prefix)

    witnesses, wit_counter, witness_centuries = get_nvs_witnesses(corpus, play)

    return render(
        request,
        'paratext.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'nvs_page': nvs_page,
            'corpora_url': corpora_url,
            'play': play,
            'witnesses': json.dumps(witnesses),
            'section': section,
            'toc': section_toc,
            'html': section_html
        }
    )


def witness_meter(request, witness_flags, height, width, inactive_color_hex, label_buffer):
    if height.isdigit() and width.isdigit() and label_buffer.isdigit():
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
            'x': '#2a69a1'
        }
        selectively_quoted_width = 20 + int(label_buffer)
        indicator_width = (width - selectively_quoted_width) / (len(witness_flags) - 1)
        img = Image.new('RGBA', (width, height), (255, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        for flag_index in range(0, len(witness_flags) - 1):
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

        if witness_flags[-1] != '0':
            indicator_color = color_map['3']
            if witness_flags[-1] == 'x':
                indicator_color = color_map['x']

            start_x = width - 10 - indicator_width
            end_x = start_x + indicator_width

            start_y = 0
            while start_y + 1 < height:
                draw.rectangle(
                    [(start_x, start_y), (end_x, start_y + 1)],
                    fill=indicator_color,
                    outline=None,
                    width=0
                )

                start_y += 4


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


def home(request, corpus_id=None):
    nvs_page = "home"
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'nvs_home'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'nvs_home.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content,
            'nvs_page': nvs_page
        }
    )


def frontmatter(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'nvs_frontmatter'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'nvs_frontmatter.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content
        }
    )


def appendix(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'nvs_appendix'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'nvs_appendix.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content
        }
    )


def bibliography(request, corpus_id=None):
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'nvs_bibliography'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'nvs_bibliography.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content
        }
    )


def info_about(request, corpus_id=None):
    nvs_page = "info-about"
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_about'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_about.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content,
            'nvs_page': nvs_page
        }
    )


def info_contributors(request, corpus_id=None):
    nvs_page = "info-contributors"
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_contributors'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_contributors.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content,
            'nvs_page': nvs_page
        }
    )


def info_print_editions(request, corpus_id=None):
    nvs_page = "info-print-editions"
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_print'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_print.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content,
            'nvs_page': nvs_page
        }
    )


def info_how_to(request, corpus_id=None):
    nvs_page = "info-how-to"
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_how_to'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_how_to.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content,
            'nvs_page': nvs_page
        }
    )


def info_faqs(request, corpus_id=None):
    nvs_page = "info-faqs"
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'info_faqs'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'info_faqs.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content,
            'nvs_page': nvs_page
        }
    )


def tools_about(request, corpus_id=None):
    nvs_page = "tools-about"
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'tools_about'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'tools_about.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content,
            'nvs_page': nvs_page
        }
    )


def tools_advanced_search(request, corpus_id=None):
    nvs_page = "tools-advanced-search"
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'tools_advanced_search'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'tools_advanced_search.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content,
            'nvs_page': nvs_page
        }
    )


def tools_data_extraction(request, corpus_id=None):
    nvs_page = "tools-data-extraction"
    dynamic_content = "Some <i>dynamically</i> generated content!"
    site_request = False

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id
        site_request = True

    corpus = get_corpus(corpus_id)
    content_block = corpus.get_content('ContentBlock', {'handle': 'tools_data'}, single_result=True)
    if content_block:
        dynamic_content = content_block.html

    return render(
        request,
        'tools_data.html',
        {
            'corpus_id': corpus_id,
            'site_request': site_request,
            'content': dynamic_content,
            'nvs_page': nvs_page
        }
    )


def api_lines(request, corpus_id=None, play_prefix=None, starting_line_id=None, ending_line_id=None):
    lines = []

    if not corpus_id and hasattr(request, 'corpus_id'):
        corpus_id = request.corpus_id

    if corpus_id and play_prefix:
        corpus = get_corpus(corpus_id)
        play = corpus.get_content('Play', {'prefix': play_prefix})[0]

        if starting_line_id:
            all_lines = corpus.get_content('PlayLine', {'play': play.id}).order_by('line_number')
            started_collecting = False
            for line in all_lines:
                if line.xml_id == starting_line_id:
                    lines.append(line.to_dict())
                    if ending_line_id:
                        started_collecting = True
                    else:
                        break
                elif line.xml_id == ending_line_id:
                    lines.append(line.to_dict())
                    break
                elif started_collecting:
                    lines.append(line.to_dict())

        elif _contains_any(request.GET, ['character', 'scene']):
            nvs_session = get_nvs_session(request, play_prefix, True, True)
            nvs_session['play_id'] = str(play.id)
            nvs_session['filter']['character'] = request.GET.get('character', 'all')
            nvs_session['filter']['character_lines'] = []
            nvs_session['filter']['act_scene'] = request.GET.get('scene', 'all')
            filter_session_lines_by_character(corpus, play, nvs_session)
            lines = get_session_lines(corpus, nvs_session, only_ids='only_ids' in request.GET)
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
    results = {}

    quick_search = request.POST.get('quick_search', None)
    search_type = request.POST.get('search_type', None)
    search_contents = request.POST.get('search_contents', None)

    if 'clear' in request.GET:
        nvs_session['search'] = {}
        set_nvs_session(request, nvs_session, play_prefix)
    else:
        results = {
            'characters': {},
            'lines': [],
            'variants': [],
            'commentaries': [],
            'last_commentary_line': 0
        }

        line_filter = {}
        if nvs_session['filter']['character'] != 'all' or nvs_session['filter']['act_scene'] != 'all':
            filtered_lines = get_session_lines(corpus, nvs_session, only_ids=True)
            for filtered_line in filtered_lines:
                line_filter[filtered_line.xml_id] = None

        if quick_search:
            if 'playtext' in search_contents:
                lines_found = {}

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
                    'highlight_num_fragments': 0,
                    'only_highlights': 'y'
                }
                print('SPEECHES')
                qs_results = progressive_search(corpus, speech_query, ['text'], quick_search, search_type)

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

                            if matches and search_type == 'exact':
                                exact_terms = quick_search.lower().split()
                                matches = [m for m in matches if _contains_any(m.lower(), exact_terms)]

                            if matches:
                                line_xml_id = "tln_{0}".format(line[:line.index(' />')])
                                if (not line_filter) or line_xml_id in line_filter:
                                    lines_found[line_xml_id] = True
                                    results['lines'].append({
                                        'xml_id': line_xml_id,
                                        'matches': matches
                                    })

                # SEARCH PLAY LINES VIA PlayLine CT
                lines_query = {
                    'content_type': 'PlayLine',
                    'page': 1,
                    'page_size': 1000,
                    'fields_filter': {
                        'play.id': str(play.id)
                    },
                    'only': ['act', 'scene', 'xml_id', 'text'],
                    'fields_highlight': ['text'],
                    'highlight_num_fragments': 0,
                    'only_highlights': 'y'
                }
                print('LINES')
                qs_results = progressive_search(corpus, lines_query, ['text'], quick_search, search_type)

                for record in qs_results['records']:
                    line_xml_id = record['xml_id']
                    if line_xml_id not in lines_found and ((not line_filter) or line_xml_id in line_filter):
                        for hit in record['_search_highlights']['text']:
                            matches = re.findall(r'<em>([^<]*)</em>', hit)

                            if matches and search_type == 'exact':
                                exact_terms = quick_search.lower().split()
                                matches = [m for m in matches if _contains_any(m.lower(), exact_terms)]

                            if matches:
                                results['lines'].append({
                                    'xml_id': line_xml_id,
                                    'matches': matches
                                })

                if results['lines']:
                    results['lines'] = sorted(results['lines'], key=lambda l: len(l['matches']), reverse=True)

            if 'variants' in search_contents:
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
                    'only_highlights': 'y'
                }
                print('VARIANTS')
                variant_results = progressive_search(corpus, variant_query, ['variants.variant', 'variants.description'], quick_search, search_type)
                variant_lines = {}
                for record in variant_results['records']:
                    variant_line_id = record['lines'][0]['xml_id']
                    if variant_line_id not in variant_lines and ((not line_filter) or variant_line_id in line_filter):
                        result = {
                            'xml_id': variant_line_id,
                            'matches': []
                        }
                        if 'variants.variant' in record['_search_highlights']:
                            for highlight in record['_search_highlights']['variants.variant']:
                                matches = re.findall(r'<em>([^<]*)</em>', highlight)

                                if matches and search_type == 'exact':
                                    exact_terms = quick_search.lower().split()
                                    matches = [m for m in matches if _contains_any(m.lower(), exact_terms)]

                                if matches:
                                    result['matches'] += matches
                        if 'variants.description' in record['_search_highlights']:
                            for highlight in record['_search_highlights']['variants.description']:
                                matches = re.findall(r'<em>([^<]*)</em>', highlight)

                                if matches and search_type == 'exact':
                                    exact_terms = quick_search.lower().split()
                                    matches = [m for m in matches if _contains_any(m.lower(), exact_terms)]

                                if matches:
                                    result['matches'] += matches

                        if result['matches']:
                            results['variants'].append(result)
                            variant_lines[variant_line_id] = True

            if 'commentary' in search_contents:
                # Search Commentary
                comm_query = {
                    'content_type': 'Commentary',
                    'page': 1,
                    'page_size': 1000,
                    'fields_filter': {
                        'play.id': str(play.id)
                    },
                    'only': ['xml_id', 'lines.line_number', 'lines.xml_id'],
                    'fields_highlight': ['subject_matter', 'contents'],
                    'only_highlights': 'y'
                }
                print('COMMENTARY')
                comm_results = progressive_search(corpus, comm_query, ['subject_matter', 'contents'], quick_search, search_type)

                for record in comm_results['records']:
                    if 'lines' in record:
                        has_relevant_line = False

                        for line in record['lines']:
                            if (not line_filter) or line['xml_id'] in line_filter:
                                has_relevant_line = True
                                if line['line_number'] > results['last_commentary_line']:
                                    results['last_commentary_line'] = line['line_number']

                        if has_relevant_line:
                            result = {
                                'comm_id': record['xml_id'],
                                'matches': []
                            }
                            if 'subject_matter' in record['_search_highlights']:
                                for highlight in record['_search_highlights']['subject_matter']:
                                    matches = re.findall(r'<em>([^<]*)</em>', highlight)

                                    if matches and search_type == 'exact':
                                        exact_terms = quick_search.lower().split()
                                        matches = [m for m in matches if _contains_any(m.lower(), exact_terms)]

                                    if matches:
                                        result['matches'] += matches
                            if 'contents' in record['_search_highlights']:
                                for highlight in record['_search_highlights']['contents']:
                                    matches = re.findall(r'<em>([^<]*)</em>', highlight)

                                    if matches and search_type == 'exact':
                                        exact_terms = quick_search.lower().split()
                                        matches = [m for m in matches if _contains_any(m.lower(), exact_terms)]

                                    if matches:
                                        result['matches'] += matches

                            if result['matches']:
                                result['matches'] = list(set(result['matches']))
                                results['commentaries'].append(result)

            nvs_session['search']['quick_search'] = quick_search
            nvs_session['search']['results'] = results
            set_nvs_session(request, nvs_session, play_prefix)

    return HttpResponse(
        json.dumps(results),
        content_type='application/json'
    )


def progressive_search(corpus, search_params, fields, query, search_type):
    if len(fields) > 1:
        search_params['operator'] = "or"

    results = []
    fields_dict = {}
    for field in fields:
        fields_dict[field] = query

    if search_type in ['fuzzy', 'exact']:
        print('trying term...')
        search_params['fields_term'] = fields_dict
        results = corpus.search_content(**search_params)

        if not results['records'] and search_type in ['fuzzy', 'exact']:
            print('trying phrase...')
            del search_params['fields_term']
            search_params['fields_phrase'] = fields_dict
            results = corpus.search_content(**search_params)

        if not results['records'] and search_type == 'fuzzy':
            print('trying fields...')
            del search_params['fields_phrase']
            search_params['fields_query'] = fields_dict
            results = corpus.search_content(**search_params)

        if not results['records'] and search_type == 'fuzzy':
            print('trying no stopwords...')
            adjusted_query = query.lower().split()
            for stopword in "a an and are as at be but by for if in into is it no not of on or such that the their then there these they this to was will with".split():
                if stopword in adjusted_query:
                    adjusted_query.remove(stopword)
            adjusted_query = ' '.join(adjusted_query)
            for field in fields:
                search_params['fields_query'][field] = adjusted_query
            results = corpus.search_content(**search_params)

    elif search_type == 'wildcard':
        search_params['fields_wildcard'] = fields_dict
        results = corpus.search_content(**search_params)

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


def filter_session_lines_by_character(corpus, play, nvs_session):
    if nvs_session['filter']['character'] != 'all':
        char_line_results = corpus.search_content(
            content_type='Speech',
            page=1,
            page_size=5000,
            fields_filter={'play.id': str(play.id), 'speaking.xml_id': '__'.join(nvs_session['filter']['character'].split(','))},
            fields_sort=[{'lines.line_number': {'order': 'ASC'}}],
            only=['lines.id']
        )
        if char_line_results['records']:
            for record in char_line_results['records']:
                for line in record['lines']:
                    nvs_session['filter']['character_lines'].append(line['id'])
        else:
            nvs_session['filter']['no_results'] = True


def get_nvs_witnesses(corpus, play):
    witnesses = {}
    witness_centuries = {}

    wit_counter = 0
    wit_refs = corpus.get_content("Reference", {'play': play.id, 'ref_type': 'primary_witness'}).order_by('+id')
    for wit_ref in wit_refs:
        witnesses[wit_ref.document.siglum] = {
            'slots': [wit_counter],
            'document_id': str(wit_ref.document.id),
            'bibliographic_entry': "{0} {1}".format(wit_ref.document.siglum_label, wit_ref.bibliographic_entry),
            'occasional': False
        }

        century = wit_ref.document.pub_date[:2] + "00"
        if century in witness_centuries:
            witness_centuries[century] += 1
        else:
            witness_centuries[century] = 1

        wit_counter += 1

    wit_refs = corpus.get_content("Reference", {'play': play.id, 'ref_type': 'occasional_witness'}).order_by('+id')
    for wit_ref in wit_refs:
        witnesses[wit_ref.document.siglum] = {
            'slots': [wit_counter],
            'document_id': str(wit_ref.document.id),
            'bibliographic_entry': wit_ref.bibliographic_entry,
            'occasional': True
        }

    document_collections = corpus.get_content('DocumentCollection', {'play': play.id})
    for collection in document_collections:
        slots = []
        bib_entry = ""

        for reffed_doc in collection.referenced_documents:
            if reffed_doc.siglum in witnesses:
                slots += witnesses[reffed_doc.siglum]['slots']
                if bib_entry:
                    bib_entry += "<br /><br />"
                bib_entry += "{0}".format(witnesses[reffed_doc.siglum]['bibliographic_entry'])

        witnesses[collection.siglum] = {
            'slots': slots,
            'bibliographic_entry': bib_entry,
            'occasional': False
        }

    return witnesses, wit_counter, witness_centuries


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