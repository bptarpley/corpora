import os
import json
import traceback
from datetime import datetime
from huey.contrib.djhuey import db_task
from natsort import natsorted
from elasticsearch_dsl.connections import get_connection
from django.conf import settings


@db_task(priority=0)
def index_document_pages(corpus_id, document_id, pages={}):
    body = { 'pages': [] }
    ref_nos = natsorted(list(pages.keys()))
    for ref_no in ref_nos:
        for file in pages[ref_no]['files']:
            if file['extension'] == 'txt' and file['primary_witness'] and os.path.exists(file['path']):
                contents = ""

                try:
                    with open(file['path'], 'r', encoding='utf-8') as file_in:
                        contents = file_in.read()
                except:
                    print("Error reading file {0} for indexing document {1}:".format(file['path'], document_id))
                    print(traceback.format_exc())

                body['pages'].append({
                    'ref_no': ref_no,
                    'contents': contents
                })

    get_connection().update(
        index='corpus-{0}-documents'.format(corpus_id),
        id=document_id,
        body={ 'doc': body },
    )
    # TODO: trigger upstream indexing of document if it belongs to a CorpusSet; use to_dict() to pass to task


@db_task(priority=0)
def cache_page_file_collections(corpus_id, document_id, page_file_collections):
    with settings.NEO4J.session() as neo:
        cypher = ""
        params = {}
        try:
            for slug in page_file_collections.keys():
                cypher = '''
                    MATCH (d:Document { uri: $doc_uri })
                    MERGE (d) -[:hasPageFileCollection]-> (pfc:PageFileCollection { uri: $pfc_uri })
                    SET pfc.created = $pfc_created
                    SET pfc.slug = $pfc_slug
                    SET pfc.label = $pfc_label
                    SET pfc.page_file_dict_json = $pfc_page_file_dict_json
                '''
                params = {
                    'doc_uri': "/corpus/{0}/document/{1}".format(corpus_id, document_id),
                    'pfc_uri': "/corpus/{0}/document/{1}/page-file-collection/{2}".format(corpus_id, document_id, slug),
                    'pfc_created': int(datetime.now().timestamp()),
                    'pfc_slug': slug,
                    'pfc_label': page_file_collections[slug]['label'],
                    'pfc_page_file_dict_json': json.dumps(page_file_collections[slug]['page_files'])
                }
                neo.run(cypher, **params)
        except:
            print("Error running Neo4J cypher!")
            print("Cypher: {0}".format(cypher))
            print("Params: {0}".format(json.dumps(params, indent=4)))
            print(traceback.format_exc())
        finally:
            neo.close()
