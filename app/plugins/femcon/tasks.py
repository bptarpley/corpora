import traceback

from .content import REGISTRY as femcon_content_types
from plugins.document.content import REGISTRY as document_content_types
from django.utils.text import slugify
from huey.contrib.djhuey import db_task
from corpus import *
from bs4 import BeautifulSoup
from booknlp.booknlp import BookNLP


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
    "Ingest CATMA TEI": {
        "version": "0.1",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Document",
        "configuration": {
            "parameters": {
                "catma_tei_key": {
                    "value": "",
                    "type": "document_file",
                    "label": "CATMA TEI File",
                },
                "char_tagset": {
                    "value": "",
                    "type": "text",
                    "label": "Character Tagset Name",
                    "note": "The name of the CATMA tagset to which character names belong (usually [Novel]Names). NOTE: No spaces allowed in this tagset name!"
                }
            },
        },
        "module": 'plugins.femcon.tasks',
        "functions": ['ingest_catma_tei']
    },
    "Run BookNLP": {
        "version": "0.2",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Document",
        "configuration": {
            "parameters": {
                "text_file_key": {
                    "value": "",
                    "type": "document_file",
                    "label": "Plain Text File",
                },
                "booknlp_model": {
                    "value": "Small",
                    "type": "choice",
                    "choices": ["Small", "Big"],
                    "label": "BookNLP Model",
                    "note": "The small model is more appropriate for use on laptops. Only choose the big model for use in a large memory environment."
                }
            },
        },
        "module": 'plugins.femcon.tasks',
        "functions": ['run_booknlp']
    },
    "Associate BookNLP Keywords": {
        "version": "0.1",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Document",
        "configuration": {
            "parameters": {},
        },
        "module": 'plugins.femcon.tasks',
        "functions": ['associate_booknlp_keywords']
    },
}

femcon_document_fields = [
    {
        "name": "text",
        "label": "Text",
        "type": "large_text",
        "in_lists": True
    },
    {
        "name": "booknlp_dataset",
        "label": "BookNLP Dataset",
        "type": "keyword",
        "in_lists": False
    }
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
            femcon_doc_schema['edit_widget_url'] = "/corpus/{corpus_id}/Document/{content_id}/booknlp-widget/"
            corpus.save_content_type(femcon_doc_schema)
    except:
        print(traceback.format_exc())

    job.complete(status='complete')


def parse_catma_tei(corpus, document, node, data, tei):
    if node.name:
        if node.name == 'seg':
            char_ids = []
            tag_ids = []
            tagging_keys = []

            tagging_ids = node['ana'].replace('#', '').split()
            for tagging_id in tagging_ids:
                if tagging_id in data['tagging_map']:
                    catma_id = data['tagging_map'][tagging_id]

                    if catma_id in data['chars']:
                        char_ids.append(catma_id)
                    elif catma_id in data['tags']:
                        tag_ids.append(catma_id)

            for char_id in char_ids:
                tagging_key_prefix = char_id + '|'

                for tag_id in tag_ids:
                    tagging_keys.append(tagging_key_prefix + tag_id)

            closed_taggings = [k for k in data['taggings'].keys() if k not in tagging_keys]
            for closed_tagging in closed_taggings:
                tagging = data['taggings'][closed_tagging]
                tagging.location_end = len(data['text'])
                tagging.save()
                del data['taggings'][closed_tagging]

            for tagging_key in tagging_keys:
                if tagging_key not in data['taggings']:
                    key_parts = tagging_key.split('|')
                    if len(key_parts) == 2:
                        char_catma_id = key_parts[0]
                        tag_catma_id = key_parts[1]

                        tagging = corpus.get_content('Tagging')
                        tagging.novel = document.id
                        tagging.character = data['chars'][char_catma_id]
                        tagging.tag = data['tags'][tag_catma_id]
                        tagging.location_start = len(data['text'])
                        tagging.text = ''
                        data['taggings'][tagging_key] = tagging

            for child in node.children:
                parse_catma_tei(corpus, document, child, data, tei)
    else:
        data['text'] += str(node)
        for tagging_key in data['taggings'].keys():
            data['taggings'][tagging_key].text += str(node)


@db_task(priority=2)
def ingest_catma_tei(job_id):
    job = Job(job_id)
    corpus = job.corpus
    document = job.content
    catma_tei_key = job.get_param_value('catma_tei_key')
    catma_tei = document.files[catma_tei_key]
    character_tagset = job.get_param_value('char_tagset')

    job.set_status('running')

    # PREVENT LOGGING ELASTICSEARCH INFO MSGS
    es_logger = logging.getLogger('elasticsearch')
    es_log_level = es_logger.getEffectiveLevel()
    es_logger.setLevel(logging.WARNING)

    # CLEAR ALL EXISTING TAGGINGS FOR THIS NOVEL
    deletion_count = 0
    existing_taggings = corpus.get_content('Tagging', {'novel': document.id})
    for existing_tagging in existing_taggings:
        existing_tagging.delete()
        deletion_count += 1
    print("Deleted {0} existing taggings.".format(deletion_count))

    data = {
        'chars': {},
        'tags': {},
        'taggings': {},
        'tagging_map': {},
        'text': '',
        'count': 0,
    }

    with open(catma_tei.path, 'r', encoding='utf-8') as tei_in:
        tei_text = ' '.join(tei_in.read().split())
        tei = BeautifulSoup(tei_text, "xml")

    # HANDLE ALL CHARACTERS AND TAGS DESCRIBED BY TEI HEADER
    tagset_nodes = tei.find_all('fsdDecl')
    for tagset_node in tagset_nodes:
        ts_catma_id = tagset_node['xml:id']
        ts_name_parts = tagset_node['n'].split()
        ts_name = ts_name_parts[0]

        if ts_name == character_tagset:
            char_nodes = tagset_node.find_all('fsDecl')
            for char_node in char_nodes:
                char_field_values = {
                    'catma_id': char_node['xml:id'],
                    'name': str(char_node.fsDescr.string).strip(),
                }
                character = corpus.get_or_create_content('Character', char_field_values, True)
                char_novels = [n.id for n in character.novels]
                data['chars'][character.catma_id] = character.id
                if document.id not in char_novels:
                    character.novels.append(document.id)
                    character.save()
        else:
            tagset_field_values = {
                'catma_id': ts_catma_id,
                'name': ts_name
            }
            tagset = corpus.get_or_create_content('Tagset', tagset_field_values)
            tagset_tags = [t.id for t in tagset.tags]
            tagset_updated = False

            tag_nodes = tagset_node.find_all('fsDecl')
            for tag_node in tag_nodes:
                tag_field_values = {
                    'catma_id': tag_node['xml:id'],
                    'name': str(tag_node.fsDescr.string).strip()
                }
                tag = corpus.get_or_create_content('Tag', tag_field_values, True)
                data['tags'][tag.catma_id] = tag.id
                if tag.id not in tagset_tags:
                    tagset.tags.append(tag.id)
                    tagset_updated = True

            if tagset_updated:
                tagset.save()

    # CACHE ALL TAGGING ID -> CATMA ID MAPPINGS
    map_nodes = tei.find('text').find_all('fs')
    for map_node in map_nodes:
        data['tagging_map'][map_node['xml:id'].strip()] = map_node['type'].strip()

    body = tei.find('text').body.ab
    for child in body.children:
        parse_catma_tei(corpus, document, child, data, tei)

    fake_tagging = BeautifulSoup('<seg ana="#"></seg>', 'xml')
    parse_catma_tei(corpus, document, fake_tagging.seg, data, tei)

    # SAVE PLAIN TEXT FROM TEI TO DOCUMENT
    document.text = data['text']
    document.save()

    # RESET ES LOG LEVEL
    es_logger.setLevel(es_log_level)

    corpus.queue_local_job(task_name="Adjust Content", parameters={
        'content_type': "Character",
        'reindex': True,
        'relabel': True,
        'relink': True
    })

    job.complete(status='complete')


@db_task(priority=2)
def run_booknlp(job_id):
    job = Job(job_id)
    document = job.content
    booknlp_model = job.get_param_value('booknlp_model').lower()
    text_file_key = job.get_param_value('text_file_key')
    text_file = document.files[text_file_key]

    job.set_status('running')

    book_id = slugify(document.title)
    results_path = document.path + '/files/booknlp'
    if not os.path.exists(results_path):
        os.makedirs(results_path)

    booknlp = BookNLP(
        "en",
        {
            "pipeline": "entity,quote,supersense,event,coref",
            "model": booknlp_model,
        }
    )

    booknlp.process(
        text_file.path,
        results_path,
        book_id
    )

    document.booknlp_dataset = results_path
    document.save()

    job.complete(status='complete')


@db_task(priority=2)
def associate_booknlp_keywords(job_id):
    job = Job(job_id)
    corpus = job.corpus
    document = job.content

    job.set_status('running')

    if document and \
            hasattr(document, 'booknlp_dataset') and \
            document.booknlp_dataset and \
            os.path.exists(document.booknlp_dataset + '/character_map.json'):

        es_logger = logging.getLogger('elasticsearch')
        es_log_level = es_logger.getEffectiveLevel()
        es_logger.setLevel(logging.WARNING)

        booknlp_char_map = {}
        booknlp_chars = {}
        femcon_chars = {}

        modes = ['agent', 'patient', 'mod', 'poss']

        with open(document.booknlp_dataset + '/character_map.json', 'r', encoding='utf-8') as map_in:
            booknlp_char_map = json.load(map_in)

        booknlp_chars_file = None
        files = os.listdir(document.booknlp_dataset)
        for file in files:
            if file.endswith('.book'):
                booknlp_chars_file = "{0}/{1}".format(document.booknlp_dataset, file)
                break
        with open(booknlp_chars_file, 'r', encoding='utf-8') as chars_in:
            booknlp_chars = json.load(chars_in)

        for booknlp_char in booknlp_chars['characters']:
            booknlp_id = str(booknlp_char['id'])
            if booknlp_id in booknlp_char_map:
                femcon_id = booknlp_char_map[booknlp_id]
                if femcon_id not in femcon_chars:
                    femcon_chars[femcon_id] = corpus.get_content('Character', femcon_id)

                for mode in modes:
                    for modeword in booknlp_char[mode]:
                        word = modeword['w']
                        intensity = modeword['i']

                        if intensity >= 5:
                            keyword = corpus.get_or_create_content('Keyword', {'word': word, 'mode': mode}, use_cache=True)
                            if femcon_chars[femcon_id].id not in [c.id for c in keyword.characters]:
                                keyword.characters.append(femcon_chars[femcon_id].id)

                            keyword.set_intensity(
                                'characters',
                                femcon_id,
                                keyword.get_intensity('characters', femcon_id) + intensity
                            )
                            keyword.save()

    job.complete(status='complete')
    es_logger.setLevel(es_log_level)
