import time
import re
from django.shortcuts import render, HttpResponse, redirect
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
from corpus import *
from mongoengine.queryset.visitor import Q
from manager.utilities import _get_context, get_scholar_corpus, _contains, _clean, parse_uri
from importlib import reload
from plugins.nvs import tasks
from rest_framework.decorators import api_view
from PIL import Image, ImageDraw


@login_required
def lines(request, corpus_id, starting_line_no, ending_line_no=None):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])
    lines = None
    textual_notes = None
    line_mode = request.GET.get('line_mode', False) == 'y'
    perf_note_id = request.GET.get('note-id', None)
    perf_variant_id = request.GET.get('variant-id', None)
    perf_line_id = request.GET.get('line-id', None)
    perf_mark_bug = request.GET.get('mark-as-bug', None)

    if corpus and starting_line_no:
        if perf_note_id and perf_variant_id:
            perf_note = corpus.get_content('TextualNote', perf_note_id)
            perf_variant = corpus.get_content('TextualVariant', perf_variant_id)
            reload(tasks)

            try:
                perf_variant.variant = tasks.perform_variant_transform(corpus, perf_note, perf_variant)
            except:
                perf_variant.has_bug = 1

            if perf_mark_bug:
                perf_variant.has_bug = 1

            perf_variant.save()
            return redirect("/corpus/{0}/NVSLines/{1}/{2}/?line_mode=y#{3}".format(
                corpus_id,
                starting_line_no,
                ending_line_no,
                perf_line_id
            ))

        if not ending_line_no or not ending_line_no > starting_line_no:
            ending_line_no = starting_line_no

        line_numbers = range(starting_line_no, ending_line_no + 1)

        line_locations = corpus.get_content('LineLocation', all=True)
        line_locations = line_locations.filter(
            (Q(starting_line_number__in=line_numbers) | Q(ending_line_number__in=line_numbers)) |
            (Q(starting_line_number__lt=starting_line_no) & Q(ending_line_number__gt=ending_line_no))
        )
        line_locations = list(line_locations.order_by('+starting_line_number', '-ending_line_number', '+starting_word_index', '-ending_word_index'))
        uri_pattern = "/corpus/{0}/LineLocation/{1}"
        line_location_uris = [uri_pattern.format(corpus_id, ll.id) for ll in line_locations]

        connected_tags = run_neo(
            '''
                MATCH (ll:LineLocation) <-[]- (tag)
                WHERE ll.uri IN $line_location_uris
                AND (tag:PlayRole or tag:StageDirection or tag:PlayStyle)
                RETURN tag.uri, ll.uri;
            ''', {'line_location_uris': line_location_uris}
        )

        role_ids = []
        stage_ids = []
        style_ids = []

        for connected_tag in connected_tags:
            tag_info = parse_uri(connected_tag[0])
            ll_info = parse_uri(connected_tag[1])

            tag_type = 'PlayRole'
            if 'StageDirection' in tag_info:
                tag_type = 'StageDirection'
                stage_ids.append(tag_info['StageDirection'])
            elif 'PlayStyle' in tag_info:
                tag_type = 'PlayStyle'
                style_ids.append(tag_info['PlayStyle'])
            else:
                role_ids.append(tag_info['PlayRole'])

            for ll_index in range(0, len(line_locations)):
                if str(line_locations[ll_index].id) == ll_info['LineLocation']:
                    if not hasattr(line_locations[ll_index], 'tags'):
                        line_locations[ll_index].tags = []

                    line_locations[ll_index].tags.append({
                        'type': tag_type,
                        'id': tag_info[tag_type]
                    })

        # sort tags in each line_location to get correct rendering order
        # for ll_index in range(0, len(line_locations)):
        #    if hasattr(line_locations[ll_index], 'tags'):
        #        line_locations[ll_index].tags = sorted(line_locations[ll_index].tags, key=lambda t: t['type'])

        roles = corpus.get_content('PlayRole', {'id__in': role_ids})
        stages = corpus.get_content('StageDirection', {'id__in': stage_ids})
        styles = corpus.get_content('PlayStyle', {'id__in': style_ids})

        # consolidate all tags by line location key in dict
        tags = {}
        for line_location in line_locations:
            if hasattr(line_location, "tags"):
                location_start_key = "{0}:{1}".format(line_location.starting_line_number, line_location.starting_word_index)
                location_end_key = "{0}:{1}".format(line_location.ending_line_number, line_location.ending_word_index)

                if location_start_key != location_end_key:
                    if location_start_key not in tags:
                        tags[location_start_key] = ""
                    if location_end_key not in tags:
                        tags[location_end_key] = ""

                    tags[location_start_key] += generate_tags_html(line_location, roles, stages, styles)
                    tags[location_end_key] += generate_tags_html(line_location, roles, stages, styles, "close")

        # sort tags for each location key, placing close tags before open tags
        for location_key in tags.keys():
            tags_to_sort = tags[location_key].replace('>', '>|')
            tags_to_sort = tags_to_sort.split('|')
            tags[location_key] = ''.join(sorted(tags_to_sort))

        lines = corpus.get_content('PlayLine', {'line_number__gte': starting_line_no, 'line_number__lte': ending_line_no})
        lines = lines.order_by('line_number')
        lines = list(lines)

        line_ids = []
        for line in lines:
            line_ids.append(line.id)

        textual_notes = corpus.get_content('TextualNote', all=True)
        textual_notes = list(textual_notes.filter(lines__in=line_ids))

        witness_meter_length = 0
        for tn_index in range(0, len(textual_notes)):
            if not witness_meter_length:
                witness_meter_length = len(textual_notes[tn_index].witness_meter)

            textual_notes[tn_index].line_nos = [line.line_number for line in textual_notes[tn_index].lines]

        # in order to make lines self-contained, we need to keep track of how to open and close any tags
        # that transcend line breaks

        line_tags = {
            'open': [],
            'close': []
        }

        html = ""

        for location_key in tags.keys():
            location_line = int(location_key.split(':')[0])
            if location_line < starting_line_no:
                if line_mode:
                    adjust_line_tags(line_tags, tags[location_key])
                else:
                    html += tags[location_key]
            else:
                break

        for line_index in range(0, len(lines)):
            line = lines[line_index]

            if line_mode:
                html = "<a name='{0}'></a>".format(line.xml_id)
                html += ''.join(line_tags['open'])
            else:
                html += "<a name='{0}'></a>".format(line.xml_id)

            for word_index in range(0, len(line.words) + 1):
                location_key = "{0}:{1}".format(line.line_number, word_index)
                if location_key in tags:
                    html += tags[location_key]

                    if line_mode:
                        adjust_line_tags(line_tags, tags[location_key])

                if word_index < len(line.words):
                    html += line.words[word_index] + " "

            if line_mode:
                html += ''.join(line_tags['close'])
                lines[line_index].rendered_html = html
                lines[line_index].notes = []
                lines[line_index].has_bug = False

                for textual_note in textual_notes:
                    if line.line_number in textual_note.line_nos:
                        lines[line_index].notes.append(textual_note)
                        if not lines[line_index].has_bug:
                            for variant in textual_note.variants:
                                if variant.has_bug or not variant.variant:
                                    line.has_bug = True

                lines[line_index].witness_meter = ""
                if lines[line_index].notes:
                    for meter_index in range(0, witness_meter_length):
                        witness_found = False
                        for note in lines[line_index].notes:
                            if note.witness_meter[meter_index] == "1":
                                witness_found = True
                                break
                        if witness_found:
                            lines[line_index].witness_meter += "1"
                        else:
                            lines[line_index].witness_meter += "0"
                else:
                    lines[line_index].witness_meter = "0" * witness_meter_length

            else:
                html += "<br />"

        if not line_mode:
            for location_key in tags.keys():
                location_line = int(location_key.split(':')[0])
                if location_line > ending_line_no:
                    html += tags[location_key]
                else:
                    break

    return render(
        request,
        'nvs_lines.html',
        {
            'response': response,
            'corpus': corpus,
            'lines': lines,
            'html': html,
            'line_mode': line_mode,
        }
    )


def generate_tags_html(line_location, roles, stages, styles, mode='open'):
    html = ""

    for tag in line_location.tags:
        if tag['type'] == 'PlayRole':
            if mode == 'open':
                for role in roles:
                    if str(role.id) == tag['id']:
                        html += "<span class='speaker {0}'>".format(role.xml_id)
                        break
            else:
                html += "</span>"

        elif tag['type'] == 'StageDirection':
            if mode == 'open':
                for stage in stages:
                    if str(stage.id) == tag['id']:
                        html += "<span class='stage_direction {0}'>".format(stage.direction_type)
                        break
            else:
                html += "</span>"

        elif tag['type'] == 'PlayStyle':
            if mode == 'open':
                for style in styles:
                    if str(style.id) == tag['id']:
                        html += "<span class='{0}'>".format(style.classes)
                        break
            else:
                html += "</span>"

    return html


def adjust_line_tags(line_tags, html):

    html_tags = html.split('>')
    html_tags = [h + '>' for h in html_tags if h]

    for html_tag in html_tags:
        # handle closing tag
        if html_tag.startswith('</'):
            del line_tags['open'][-1]
            del line_tags['close'][0]
            '''
            tag = html_tag.replace('</', '')
            tag = tag.replace('>', '')

            # remove tag from open list
            tag_index = len(line_tags['open']) - 1
            while tag_index >= 0:
                if '<' + tag in line_tags['open'][tag_index]:
                    del line_tags['open'][tag_index]
                    tag_index = -1

            # remove tag from close list
            for tag_index in range(0, len(line_tags['close'])):
                if line_tags['close'] == html_tag:
                    del line_tags['close'][tag_index]
                    break
            '''

        # handle open tag
        else:
            tag = html_tag.split()[0]
            tag = tag.replace('<', '')

            line_tags['open'].append(html_tag)
            line_tags['close'].insert(0, "</" + tag + ">")


def design(request, corpus_id, play_prefix):
    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]
    nvs_session = get_nvs_session(request, play_prefix, reset='reset' in request.GET)

    # GET params
    act_scene = request.GET.get('act-scene', nvs_session['filter']['act_scene'])
    character = request.GET.get('character', nvs_session['filter']['character'])

    lines = []

    session_changed = False

    if 'play_id' not in nvs_session:
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

    cached_template_path = "{0}/plugins/nvs/templates/{1}_playviewer_cached.html".format(settings.BASE_DIR, play_prefix)
    playviewer_template_path = "{0}/plugins/nvs/templates/playviewer.html".format(settings.BASE_DIR)

    if nvs_session['is_filtered'] or not os.path.exists(cached_template_path):
        lines = get_session_lines(corpus, nvs_session)

        # TODO: ensure preferences don't get inadvertently cached or ignored due to templating
        if not nvs_session['is_filtered'] and not os.path.exists(cached_template_path):
            playviewer_template = None
            with open(playviewer_template_path, 'r') as playviewer_template_in:
                playviewer_template = playviewer_template_in.read()

            django_template = Template(playviewer_template)
            context = Context({
                'corpus_id': corpus_id,
                'lines': lines,
                'play': play,
                'nvs_session': nvs_session
            })
            rendered_playviewer_template = django_template.render(context)
            with open(cached_template_path, 'w') as playviewer_template_out:
                playviewer_template_out.write(rendered_playviewer_template)

            return render(request, '{0}_playviewer_cached.html'.format(play_prefix), {})

        return render(
            request,
            'playviewer.html',
            {
                'corpus_id': corpus_id,
                'lines': lines,
                'play': play,
                'nvs_session': nvs_session
            }
        )
    else:
        return render(request, '{0}_playviewer_cached.html'.format(play_prefix), {})


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


def commentaries(request, corpus_id, play_prefix):
    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]
    nvs_session = get_nvs_session(request, play_prefix)
    commentary_filter = {'play': play.id}

    cached_template_path = "{0}/plugins/nvs/templates/{1}_commentary_cached.html".format(settings.BASE_DIR, play_prefix)
    commentary_template_path = "{0}/plugins/nvs/templates/commentaries.html".format(settings.BASE_DIR)

    if nvs_session['is_filtered'] or not os.path.exists(cached_template_path):
        if nvs_session['is_filtered']:
            line_ids = [line.id for line in get_session_lines(corpus, nvs_session, only_ids=True)]
            commentary_filter['lines__in'] = line_ids

        commentaries = corpus.get_content('Commentary', commentary_filter).order_by('id')

        if not nvs_session['is_filtered'] and not os.path.exists(cached_template_path):
            commentary_template = None
            with open(commentary_template_path, 'r') as commentary_template_in:
                commentary_template = commentary_template_in.read()

            django_template = Template(commentary_template)
            context = Context({'corpus_id': corpus_id, 'commentaries': commentaries})
            rendered_commentary_template = django_template.render(context)
            with open(cached_template_path, 'w') as commentary_template_out:
                commentary_template_out.write(rendered_commentary_template)

            return render(request, '{0}_commentary_cached.html'.format(play_prefix), {})

        return render(
            request,
            'commentaries.html',
            {
                'corpus_id': corpus_id,
                'commentaries': commentaries
            }
        )
    else:
        return render(request, '{0}_commentary_cached.html'.format(play_prefix), {})


def play_minimap(request, corpus_id, play_prefix):
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

            img = Image.new('RGB', (min_img_width, min_img_height), '#FFFFFF')
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


def api_search(request, corpus_id, play_prefix):
    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]
    nvs_session = get_nvs_session(request, play_prefix)

    quick_search = request.POST.get('quick_search', None)

    results = {
        'characters': {},
        'lines': []
    }

    if quick_search:
        qs_query = {
            'content_type': 'Speech',
            'page': 1,
            'page_size': 1000,
            'fields_term': {
                'text': quick_search
            },
            'fields_filter': {
                'play.id': str(play.id)
            },
            'only': ['act', 'scene', 'speaking'],
            'fields_highlight': ['text'],
            'highlight_num_fragments': 0
        }

        qs_results = corpus.search_content(**qs_query)

        if not qs_results['records']:
            print('no term found. trying phrase...')
            del qs_query['fields_term']
            qs_query['fields_phrase'] = {
                'text': quick_search
            }
            qs_results = corpus.search_content(**qs_query)

        if not qs_results['records']:
            print('no phrase found. trying query...')
            del qs_query['fields_phrase']
            qs_query['fields_query'] = {
                'text': quick_search
            }
            qs_results = corpus.search_content(**qs_query)

        if not qs_results['records']:
            print('no query found. trying adjusted search...')
            adjusted_search = quick_search
            for stopword in "a an and are as at be but by for if in into is it no not of on or such that the their then there these they this to was will with".split():
                adjusted_search = adjusted_search.replace(stopword, '')

            qs_query['fields_query']['text'] = ' '.join(adjusted_search.split())
            qs_results = corpus.search_content(**qs_query)

        if not qs_results['records']:
            print('no query found. trying general query')
            del qs_query['fields_query']
            qs_query['general_query'] = quick_search

        num_pages = qs_results['meta']['num_pages']
        while qs_query['page'] < num_pages:
            qs_query['page'] += 1
            qs_results['records'] += corpus.search_content(**qs_query)['records']

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

        nvs_session['search']['quick_search'] = quick_search
        nvs_session['search']['results'] = results
        set_nvs_session(request, nvs_session, play_prefix)

    return HttpResponse(
        json.dumps(results),
        content_type='application/json'
    )


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
