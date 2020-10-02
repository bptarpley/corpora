import csv
from huey.contrib.djhuey import db_task
from corpus import *


REGISTRY = {
    "Import Content from CSV File": {
        "version": "0",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "csv_file": {
                    "value": "",
                    "type": "corpus_file",
                    "label": "CSV File",
                    "note": "First row must contain field names corresponding to content type field names."
                },
                "content_type": {
                    "value": "",
                    "type": "content_type",
                    "label": "Content Type",
                    "note": "The content type for which you'd like to import data."
                },
                "field_keys": {
                    "value": "",
                    "type": "text",
                    "label": "Field Keys",
                    "note": "A comma separated list of field names to use as a unique key to update existing data (can be blank if only importing new data)."
                }
            },
        },
        "module": 'plugins.csv.tasks',
        "functions": ['import_csv_data']
     }
}

@db_task(priority=2)
def import_csv_data(job_id):
    job = Job(job_id)
    job.set_status('running')
    corpus = job.corpus
    csv_file_key = job.configuration['parameters']['csv_file']['value']
    content_type = job.configuration['parameters']['content_type']['value']
    field_keys = job.configuration['parameters']['field_keys']['value']
    field_keys = [fk.strip() for fk in field_keys.split(',') if fk]
    csv_file = corpus.files[csv_file_key]

    if os.path.exists(csv_file.path) and content_type in corpus.content_types:
        ct = corpus.content_types[content_type]
        with open(csv_file.path) as csv_in:
            csv_reader = csv.DictReader(csv_in)
            for row in csv_reader:
                content = None

                if field_keys:
                    query = {}
                    keys_present = True

                    for key in field_keys:
                        if ct.get_field(key) and key in row:
                            query[key] = row[key]
                        else:
                            keys_present = False

                    if keys_present and query:
                        content = corpus.get_content(content_type, query)

                if not content:
                    content = corpus.get_content(content_type)

                needs_saving = False

                for field_name in row.keys():
                    ct_field = ct.get_field(field_name)
                    if ct_field:
                        setattr(content, field_name, row[field_name])
                        needs_saving = True

                if needs_saving:
                    content.save()

    job.complete(status='complete')
