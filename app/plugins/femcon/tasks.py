import traceback

from .content import REGISTRY as femcon_content_types
from plugins.document.content import REGISTRY as document_content_types
from huey.contrib.djhuey import db_task
from corpus import *


REGISTRY = {
    "Setup FemCon Content Types": {
        "version": "0.0",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "delete_existing": {
                    "value": "No",
                    "type": "choice",
                    "choices": ["No", "Yes"],
                    "label": "Delete existing content?",
                    "note": "Selecting 'Yes' will first delete all relevant content before importing!"
                }
            },
        },
        "module": 'plugins.femcon.tasks',
        "functions": ['setup_femcon_content_types']
    },

}

femcon_document_fields = [
    {
        "name": "text",
        "label": "Text",
        "type": "large_text",
        "in_lists": True
    },
]


@db_task(priority=2)
def setup_femcon_content_types(job_id):
    job = Job(job_id)
    corpus = job.corpus
    delete_existing = job.get_param_value('delete_existing') == 'Yes'

    job.set_status('running')


    try:
        for femcon_content_type in femcon_content_types:
            if delete_existing and femcon_content_type['name'] in corpus.content_types:
                corpus.delete_content_type(femcon_content_type['name'])

            corpus.save_content_type(femcon_content_type)

        if 'Document' in corpus.content_types and delete_existing:
            corpus.delete_content_type('Document')

        femcon_doc_schema = None
        for schema in document_content_types:
            if schema['name'] == "Document":
                femcon_doc_schema = deepcopy(schema)
                break

        if femcon_doc_schema:
            femcon_doc_schema['fields'] += femcon_document_fields
            corpus.save_content_type(femcon_doc_schema)
    except:
        print(traceback.format_exc())

    job.complete(status='complete')

