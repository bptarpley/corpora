import time
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
    lines = corpus.get_content('PlayLine', {'play': play.id}).order_by('line_number')

    return render(
        request,
        'design.html',
        {
            'corpus_id': corpus_id,
            'lines': lines,
            'play': play
        }
    )


def commentaries(request, corpus_id, play_prefix):
    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]
    commentaries = corpus.get_content('Commentary', {'play': play.id}).order_by('id')

    return render(
        request,
        'commentaries.html',
        {
            'corpus_id': corpus_id,
            'commentaries': commentaries
        }
    )


def play_minimap(request, corpus_id, play_prefix):
    corpus = get_corpus(corpus_id)
    play = corpus.get_content('Play', {'prefix': play_prefix})[0]
    lines = corpus.get_content('PlayLine', {'play': play.id}).order_by('line_number')
    highlight_lines = request.GET.get('h', None)
    if highlight_lines:
        highlight_lines = highlight_lines.split(',')

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
            for line in lines:
                line_color = '#9A9A99'
                if highlight_lines and line.line_label in highlight_lines:
                    line_color = '#F99B4E'

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

