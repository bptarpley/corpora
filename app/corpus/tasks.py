import os
import traceback
from huey.contrib.djhuey import db_task
from natsort import natsorted
from elasticsearch_dsl.connections import get_connection


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
