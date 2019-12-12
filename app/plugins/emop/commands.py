import os
from manager.tasks import import_document

REGISTRY = {
    "import_documents": {
        "description": "This command will recursively import documents from any export.json files in the directory specified by the first positional parameter, associating them with a corpus ID specified by the second positional parameter, i.e.: emop:import_documents /path/to/exports 5dd84532e8cd43e0212f8c98"
    }
}


def import_documents(path, corpus_id):
    if os.path.exists(path):
        for dir_path, dir_names, files in os.walk(path):
            for file_name in files:
                if file_name == 'export.json':
                    print("attempting to import document...")
                    import_document(corpus_id, os.path.join(dir_path, file_name))
