import csv
import chardet
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

        # attempt to detect file encoding
        file_encoding = 'utf-8'
        detection = None
        with open(csv_file.path, 'rb') as csv_in:
            detection = chardet.detect(csv_in.read())

        if detection:
            file_encoding = detection['encoding']

        with open(csv_file.path, 'r', encoding=file_encoding) as csv_in:
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
                        try:
                            content = corpus.get_content(content_type, query)[0]
                        except:
                            content = None

                if not content:
                    content = corpus.get_content(content_type)

                needs_saving = False

                for field_name in row.keys():
                    ct_field = ct.get_field(field_name.strip())
                    if ct_field:
                        if row[field_name].strip():
                            setattr(content, field_name.strip(), row[field_name].strip())
                        else:
                            setattr(content, field_name.strip(), None)
                        needs_saving = True

                if needs_saving:
                    try:
                        content.save()
                    except:
                        print("Error importing data from CSV row!")
                        print(content.to_json())
                        print(traceback.format_exc())

    job.complete(status='complete')
