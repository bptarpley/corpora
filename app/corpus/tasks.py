from huey.contrib.djhuey import db_task
from elasticsearch_dsl import Index, Mapping, analyzer, Keyword
from elasticsearch_dsl.connections import get_connection
from time import sleep


REGISTRY = {
    "Reindex Content": {
        "version": "0",
        "jobsite_type": "HUEY",
        "track_provenance": False,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "collection": {
                    "value": "",
                    "type": "page_file_collection",
                    "label": "Page File Collection",
                }
            },
        },
        "module": 'manager.tasks',
        "functions": ['zip_up_page_file_collection']
    },
}


@db_task(priority=10)
def build_index(corpus_id, content_type, new=True):

    index_name = "corpus-{0}-{1}".format(corpus_id, content_type['name'].lower())
    index = Index(index_name)
    if index.exists():
        index.delete()

    corpora_analyzer = analyzer(
        'corpora_analyzer',
        tokenizer='classic',
        filter=['stop', 'lowercase', 'classic']
    )
    mapping = Mapping()
    mapping.field('_label', 'text', analyzer=corpora_analyzer, fields={'raw': Keyword()})
    mapping.field('_uri', 'keyword')

    for field in content_type.fields:
        field_type = field_type_map[field.type]
        subfields = {}

        if field.in_lists and field_type == 'text':
            subfields = {'raw': {'type': 'keyword'}}

        if field.type == 'text':
            mapping.field(field.name, field_type, analyzer=corpora_analyzer, fields=subfields)
        else:
            mapping.field(field.name, field_type, fields=subfields)

    index.mapping(mapping)
    index.save()

    print('Index {0} created.'.format(index_name))

    for content_type in indexes_to_rebuild:
        print('Rebuilding {0} index...'.format(index_name))

        items = CMS.ContentList(corpus_id, content_type, all=True)
        for item in items:
            item.index()

        print('Index {0} rebuilt.'.format(index_name))
