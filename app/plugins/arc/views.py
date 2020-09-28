import json

from rest_framework.decorators import api_view
from manager.utilities import _get_context, get_scholar_corpus, _contains, _clean
from django.shortcuts import render, HttpResponse, redirect
from django.http import Http404
from elasticsearch_dsl import A

@api_view(['GET'])
def query(request, corpus_id):
    context = _get_context(request)
    content = {}

    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])

    if corpus and 'ArcArtifact' in corpus.content_types:

        aggs = {}

        aggs['federations'] = A('nested', path='federations')
        aggs['federations'].bucket('names', 'terms', size=10000, field='federations.handle')

        aggs['archives'] = A('nested', path='archive')
        aggs['archives'].bucket('names', 'terms', size=10000, field='archive.handle')

        aggs['types'] = A('nested', path='types')
        aggs['types'].bucket('names', 'terms', size=10000, field='types.name')

        aggs['genres'] = A('nested', path='genres')
        aggs['genres'].bucket('names', 'terms', size=10000, field='genres.name')

        aggs['disciplines'] = A('nested', path='disciplines')
        aggs['disciplines'].bucket('names', 'terms', size=10000, field='disciplines.name')

        if context['search']:
            content = corpus.search_content(content_type='ArcArtifact', excludes=['full_text_contents'], aggregations=aggs, **context['search'])
        else:
            content = corpus.search_content(content_type='ArcArtifact', excludes=['full_text_contents'], aggregations=aggs, general_query="*")

    else:
        raise Http404("You are not authorized to access this endpoint.")

    return HttpResponse(
        json.dumps(content),
        content_type='application/json'
    )