import time
import re
from django.shortcuts import render, HttpResponse, redirect
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
from corpus import *
from mongoengine.queryset.visitor import Q
from manager.utilities import _get_context, get_scholar_corpus, _clean, _contains, _contains_any, parse_uri, build_search_params_from_dict
from manager.tasks import run_job
from importlib import reload
from plugins.nvs import tasks
from rest_framework.decorators import api_view
from math import floor
from PIL import Image, ImageDraw
from elasticsearch_dsl import A


@login_required
def booknlp_widget(request, corpus_id, document_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    femcon_chars = []
    booknlp_chars = {}
    existing_character_map = {}
    submitted = False

    if corpus:
        doc = corpus.get_content('Document', document_id)
        if doc:
            femcon_chars = corpus.get_content('Character', {'novels': doc.id})

            if femcon_chars and hasattr(doc, 'booknlp_dataset') and doc.booknlp_dataset and os.path.exists(doc.booknlp_dataset):
                character_map_file = "{0}/character_map.json".format(doc.booknlp_dataset)
                char_info = None
                char_info_file = None

                files = os.listdir(doc.booknlp_dataset)
                for file in files:
                    if file.endswith('.book'):
                        char_info_file = "{0}/{1}".format(doc.booknlp_dataset, file)
                        break

                with open(char_info_file, 'r', encoding='utf-8') as info_in:
                    char_info = json.load(info_in)

                if char_info and 'characters' in char_info:
                    for char in char_info['characters']:
                        if char['mentions']['proper'] and char['id'] not in booknlp_chars:
                            booknlp_chars[char['id']] = "{0} ({1})".format(
                                char['mentions']['proper'][0]['n'],
                                char['count']
                            )

                if os.path.exists(character_map_file):
                    with open(character_map_file, 'r', encoding='utf-8') as map_in:
                        existing_character_map = json.load(map_in)

            if femcon_chars and char_info and request.method == 'POST' and role in ['Admin', 'Editor']:
                booknlp_char_map = {}
                for post_var in request.POST.keys():
                    if post_var.startswith('booknlp_'):
                        booknlp_id = post_var.replace('booknlp_', '')
                        femcon_id = _clean(request.POST, post_var)

                        if femcon_id != 'ignore':
                            booknlp_char_map[booknlp_id] = femcon_id

                with open(character_map_file, 'w', encoding='utf-8') as map_out:
                    json.dump(booknlp_char_map, map_out)

                run_job(corpus.queue_local_job(content_type='Document', content_id=doc.id, scholar_id=context['scholar'].id, task_name="Associate BookNLP Keywords"))
                submitted = True

            return render(
                request,
                'BookNLPWidget.html',
                {
                    'corpus_id': corpus_id,
                    'document_id': document_id,
                    'popup': True,
                    'role': role,
                    'submitted': submitted,
                    'femcon_characters': femcon_chars,
                    'booknlp_characters': booknlp_chars,
                    'existing_character_map': existing_character_map,
                    'response': context,
                }
            )

    raise Http404("You are not authorized to view this page.")


@login_required
def api_booknlp_characters(request, corpus_id, document_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    characters = {}

    if corpus:
        doc = corpus.get_content('Document', document_id)
        if doc and hasattr(doc, 'booknlp_dataset') and doc.booknlp_dataset and os.path.exists(doc.booknlp_dataset):
            char_info = None
            char_info_file = None

            files = os.listdir(doc.booknlp_dataset)
            for file in files:
                if file.endswith('.book'):
                    char_info_file = "{0}/{1}".format(doc.booknlp_dataset, file)
                    break

            with open(char_info_file, 'r', encoding='utf-8') as info_in:
                char_info = json.load(info_in)

            if char_info and 'characters' in char_info:
                for char in char_info['characters']:
                    if char['mentions']['proper'] and char['id'] not in characters:
                        characters[char['id']] = "{0} ({1})".format(
                            char['mentions']['proper'][0]['n'],
                            char['count']
                        )

                return HttpResponse(
                    json.dumps(characters),
                    content_type='application/json'
                )

    raise Http404("Either you are not authorized to access this endpoint, or the requested content does not exist.")


