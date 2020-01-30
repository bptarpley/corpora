import os
from .content import REGISTRY as NVS_CONTENT_TYPE_SCHEMA
from corpus import *
from cms import *
from bs4 import BeautifulSoup

'''
REGISTRY = {
    "Import NVS Data from TEI": {
        "version": "0",
        "jobsite_type": "HUEY",
        "configuration": {
            "parameters": {
                "driver_file": {
                    "value": "",
                    "type": "corpus_file",
                    "label": "Edition Driver File",
                    "note": "Likely named [prefix]_driver.xml"
                }
            },
        },
        "module": 'plugins.nvs.tasks',
        "functions": ['import_data']
     }
}


def import_data(job_id):
    job = Job(job_id)
    load_content_types_from_schema(job.corpus, NVS_CONTENT_TYPE_SCHEMA)
    driver_file_path = job.configuration['parameters']['driver_file']['value']
    if os.path.exists(driver_file_path):
        edition = Document()
        edition.corpus = job.corpus

        with open(driver_file_path, 'r') as tei_in:
            tei = BeautifulSoup(tei_in, "xml")
        tei_root = tei.TEI
        tei_header = tei_root.teiHeader
        file_desc = tei_header.fileDesc
        title_stmt = file_desc.titleStmt

        edition.title = _str(title_stmt.title.string)
        edition.author = _str(title_stmt.author.string)

        for editor_tag in title_stmt.find_all('editor'):
            editor = Content(job.corpus.id, 'Editor')
            editor.fields['name']['value'] = _str(editor_tag.string)
            editor.role = editor_tag['role']
            editor.save()

        edition.work = _str(file_desc.editionStmt.edition.string)

        publication_stmt = file_desc.publicationStmt

        edition.kvp['publisher'] = _str(publication_stmt.publisher.string)
        edition.kvp['address'] = ''

        for addr_line in publication_stmt.address.find_all('addrLine'):
            edition.kvp['address'] += addr_line + '\n'

        edition.kvp['availability'] = ''

        for avail_p in publication_stmt.find_all('p'):
            edition.kvp['availability'] += avail_p + '\n'

        edition.kvp['series'] = {}
        edition.kvp['series']['title'] = _str(file_desc.seriesStmt.title.string)

        edition.save()


def _str(val):
    if val:
        return str(val)
    return ''
'''
