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

        aggs['ArcFederation'] = A('nested', path='federations')
        aggs['ArcFederation'].bucket('names', 'terms', size=10000, field='federations.id')

        aggs['ArchiveParent'] = A('nested', path='archive')
        aggs['ArchiveParent'].bucket('names', 'terms', size=10000, field='archive.parent_path')

        aggs['ArcArchive'] = A('nested', path='archive')
        aggs['ArcArchive'].bucket('names', 'terms', size=10000, field='archive.id')

        aggs['ArcType'] = A('nested', path='types')
        aggs['ArcType'].bucket('names', 'terms', size=10000, field='types.id')

        aggs['ArcGenre'] = A('nested', path='genres')
        aggs['ArcGenre'].bucket('names', 'terms', size=10000, field='genres.id')

        aggs['ArcDiscipline'] = A('nested', path='disciplines')
        aggs['ArcDiscipline'].bucket('names', 'terms', size=10000, field='disciplines.id')

        aggs['decades'] = A('histogram', field='years', interval=10)

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


def bigdiva(request, corpus_id):
    response = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, response['scholar'])

    return render(
        request,
        'bigdiva.html',
        {
            'corpus_id': corpus_id,
            'role': role,
            'response': response,
        }
    )


def uri_ascription(request, corpus_id, content_type, content_id):
    context = _get_context(request)
    corpus, role = get_scholar_corpus(corpus_id, context['scholar'])
    ascription = None

    if corpus:
        content_uri = '/corpus/{0}/{1}/{2}'.format(
            corpus_id,
            content_type,
            content_id
        )

        try:
            ascription = corpus.get_content('UriAscription', {'corpora_uri': content_uri})[0]
        except:
            ascription = None

    return render(
        request,
        'AscriptionWidget.html',
        {
            'corpus_id': corpus_id,
            'popup': True,
            'role': role,
            'attribution': ascription,
            'response': context,
        }
    )