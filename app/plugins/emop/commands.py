import os
from copy import deepcopy
from plugins.document.tasks import import_document
from plugins.document.content import REGISTRY as DOC_REGISTRY
from corpus import Corpus, Field

REGISTRY = {
    "import_documents": {
        "description": "This command will setup an EMOP corpus (EEBO or ECCO, as specified by first positional parameter), and then recursively import documents from any export.json files in the directory specified by the second positional parameter, i.e.: emop:import_documents EEBO /path/to/exports"
    }
}


def import_documents(emop_corpus, path):
    corpus = None

    if os.path.exists(path) and emop_corpus in ['EEBO', 'ECCO']:
        emop_doc_schema = {}
        emop_fields = [
            {
                "name": "emop_work_id",
                "label": "eMOP Work ID",
                "type": "number",
            },
            {
                "name": "publisher",
                "label": "Publisher",
                "type": "text",
                "in_lists": False
            },
            {
                "name": "estc_no",
                "label": "ESTC No.",
                "type": "keyword",
                "in_lists": False
            },
            {
                "name": "tcp_no",
                "label": "TCP No.",
                "type": "keyword",
                "in_lists": False
            },
            {
                "name": "tcp_bib_no",
                "label": "TCP Bib No.",
                "type": "number",
                "in_lists": False
            },
            {
                "name": "marc_record",
                "label": "MARC Record",
                "type": "keyword",
                "in_lists": False
            },
            {
                "name": "emop_font_id",
                "label": "eMOP Font ID",
                "type": "number",
                "in_lists": False
            },

        ]

        eebo_fields = [
            {
                "name": "eebo_no",
                "label": "EEBO No.",
                "type": "number",
                "in_lists": False
            },
            {
                "name": "eebo_image_no",
                "label": "EEBO Image No.",
                "type": "keyword",
                "in_lists": False
            },
            {
                "name": "eebo_url",
                "label": "EEBO URL",
                "type": "keyword",
                "in_lists": False
            }
        ]

        ecco_fields = [
            {
                "name": "ecco_no",
                "label": "ECCO No.",
                "type": "keyword",
                "in_lists": False
            },
        ]

        for schema in DOC_REGISTRY:
            if schema['name'] == "Document":
                emop_doc_schema = deepcopy(schema)
                break

        if emop_doc_schema:
            corpus_desc = "Early English Books Online"
            emop_doc_schema['fields'] += emop_fields

            if emop_corpus == 'EEBO':
                emop_doc_schema['fields'] += eebo_fields

            elif emop_corpus == 'ECCO':
                corpus_desc = "Eighteenth-Century Collections Online"
                emop_doc_schema['fields'] += ecco_fields

            corpus = Corpus()
            corpus.name = emop_corpus
            corpus.description = corpus_desc
            corpus.save()
            corpus.save_content_type(emop_doc_schema)

        if corpus:
            for dir_path, dir_names, files in os.walk(path):
                for file_name in files:
                    if file_name == 'export.json':
                        print("attempting to import document...")
                        import_document(str(corpus.id), os.path.join(dir_path, file_name))
