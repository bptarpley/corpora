import requests
import json
import traceback
from corpus import *
from bs4 import BeautifulSoup
from django.utils.text import slugify
from timeit import default_timer as timer
from .content import REGISTRY as MELP_CONTENT_TYPE_SCHEMA
from manager.utilities import _contains

REGISTRY = {
    "Import MELP Data from TEI Repo": {
        "version": "0.1",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "create_report": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "tei_repo": {
                    "value": "",
                    "type": "corpus_repo",
                    "label": "MELP TEI Repository",
                    "note": "Likely named me_tei"
                },
                "delete_existing": {
                    "value": "Yes",
                    "type": "choice",
                    "choices": ["Yes", "No"],
                    "label": "Delete existing content?",
                    "note": "Selecting 'Yes' will result in a full refresh of corpus data."
                }
            },
        },
        "module": 'plugins.melp.tasks',
        "functions": ['import_data']
    },
}


def import_data(job_id):
    time_start = timer()

    job = Job(job_id)
    corpus = job.corpus
    tei_repo_name = job.get_param_value('tei_repo')
    tei_repo = corpus.repos[tei_repo_name]
    delete_existing = job.get_param_value('delete_existing') == 'Yes'

    job.set_status('running')
    job.report('''Attempting MELP TEI ingestion using the following parameters:
TEI Repo:          {0}
Delete Existing:   {1}
    \n'''.format(
        tei_repo.name,
        delete_existing
    ))

    try:
        es_logger = logging.getLogger('elasticsearch')
        es_log_level = es_logger.getEffectiveLevel()
        es_logger.setLevel(logging.WARNING)

        # pull down latest commits to play repo
        job.report("Pulling down latest commits to TEI repo...")
        tei_repo.pull(corpus)

        # ensure content types exist
        for melp_content_type in MELP_CONTENT_TYPE_SCHEMA:
            if melp_content_type['name'] not in corpus.content_types:
                corpus.save_content_type(melp_content_type)

        # delete existing content
        if delete_existing:
            job.report("Deleting existing letters and entities...")
            letters = corpus.get_content('Letter', all=True)
            for letter in letters:
                letter.delete()

            entities = corpus.get_content('Entity', all=True)
            for ent in entities:
                ent.delete()

        # ingest people from personography
        personography_path = tei_repo.path + '/People_Places_Works/Personography.xml'
        tei = None
        with open(personography_path, 'r', encoding='utf-8') as tei_in:
            tei = BeautifulSoup(tei_in, 'xml')

        people = tei.find('text').body.listPerson.find_all('person')
        for person in people:
            xml_id = person['xml:id']
            entity = corpus.get_content('Entity', {'xml_id': xml_id}, single_result=True)
            if entity:
                entity.uris = []
            else:
                entity = corpus.get_content('Entity')
                entity.xml_id = xml_id

            entity.entity_type = 'PERSON'
            entity.name = person.persName.get_text()

            uris = person.find_all('idno')
            for uri in uris:
                entity.uris.append(uri.get_text())

            entity.save()

        # ingest letters
        job.set_status('running', percent_complete=10)
        letter_path = tei_repo.path + '/Encoded Letters'
        letter_files = [letter_path + '/' + filename for filename in os.listdir(letter_path)]

        for letter_index in range(0, len(letter_files)):
            letter_file = letter_files[letter_index]
            letter_identifier = os.path.basename(letter_file)
            letter = corpus.get_content('Letter', {'identifier': letter_identifier}, single_result=True)
            if letter:
                letter.images = []
                letter.entities_mentioned = []
            else:
                letter = corpus.get_content('Letter')
                letter.identifier = letter_identifier

            job.report("\n\n##### Parsing TEI for {0}:".format(os.path.basename(letter_file)))
            tei = None
            with open(letter_file, 'r', encoding='utf-8') as tei_in:
                tei = BeautifulSoup(tei_in, 'xml')

            if tei:
                file_desc = tei.teiHeader.fileDesc

                # --------------------------------- #
                # title                             #
                # --------------------------------- #
                title_tag = file_desc.titleStmt.find('title')
                if title_tag:
                    letter.title = title_tag.get_text()

                if not letter.title:
                    job.report("Unable to determine title of letter.")

                # --------------------------------- #
                # author and recipient              #
                # --------------------------------- #
                interlocutors = file_desc.sourceDesc.find_all("persName")
                sender_id = None
                recip_id = None
                if len(interlocutors) == 2:
                    sender_uri = interlocutors[0].attrs.get('ref')
                    if sender_uri:
                        sender_id, log = register_entity(corpus, 'PERSON', sender_uri)
                        if log == "found":
                            letter.author = corpus.get_content_dbref('Entity', sender_id)

                    recip_uri = interlocutors[1].attrs.get('ref')
                    if recip_uri:
                        recip_id, log = register_entity(corpus, 'PERSON', recip_uri)
                        if log == "found":
                            letter.recipient = corpus.get_content_dbref('Entity', recip_id)

                if not letter.author:
                    job.report("Unable to determine author.")

                if not letter.recipient:
                    job.report("Unable to determine recipient.")

                # --------------------------------- #
                # date of composition               #
                # --------------------------------- #
                date_tag = file_desc.sourceDesc.find("date")
                if date_tag and hasattr(date_tag, 'attrs') and 'when' in date_tag.attrs:
                    letter.date_composed = parser.parse(date_tag['when'])

                if not letter.date_composed:
                    job.report("Unable to determine date of composition.")

                # --------------------------------- #
                # letter body                       #
                # --------------------------------- #
                letter_body = tei.find('text').body

                # images
                images = letter_body.find_all('pb')
                for image in images:
                    if 'facs' in image.attrs:
                        letter.images.append(image['facs'])

                # parse letter body
                entities = []
                info = []
                letter.html = parse_letter_tei(corpus, letter_body, entities, info)

                # add log entries to report
                if info:
                    job.report("\n".join(info))

                # associate entities
                entities = list(set(entities))
                for ent_id in entities:
                    if not ent_id in [sender_id, recip_id]:
                        letter.entities_mentioned.append(corpus.get_content_dbref('Entity', ent_id))

                job.report("{0} entities now referenced by letter.".format(len(letter.entities_mentioned)))
                letter.save()

                job.set_status('running', percent_complete=int(((letter_index + 1) / len(letter_files)) * 100))

        time_stop = timer()
        job.report("\n\nMELP TEI ingestion completed in {0} seconds.".format(int(time_stop - time_start)))
        job.complete(status='complete')
        es_logger.setLevel(es_log_level)
    except:
        job.report("\n\nA major error prevented the ingestion of MELP TEI:\n{0}".format(
            traceback.format_exc()
        ))
        job.complete(status='error')


def register_entity(corpus, entity_type, uri):

    # REFERENCE TO PERSONOGRAPHY
    if entity_type == "PERSON" and 'Personography.xml' in uri:
        uri_parts = uri.split('#')
        if len(uri_parts) == 2:
            xml_id = uri_parts[1]
            entity = corpus.get_content('Entity', {'entity_type': entity_type, 'xml_id': xml_id}, single_result=True)
            if entity:
                return str(entity.id), "found"
            else:
                return None, "Error referencing PERSON with URI {0}: XML ID {1} not found in Personography.xml".format(uri, xml_id)
        else:
            return None, "Error referencing PERSON with URI {0}: Personography.xml URI malformed".format(uri)

    else:
        entity = corpus.get_content('Entity', {'entity_type': entity_type, 'uris__contain': uri}, single_result=True)
        if entity:
            return str(entity.id), "found"
        else:
            entity = corpus.get_content('Entity')
            entity.entity_type = entity_type
            entity.uris.append(uri)

        # MINT NEW ENTITY
        if entity_type == "PERSON":
            return None, "Error referencing PERSON with URI {0}: not registered in Personography.xml"

        elif entity_type == "PLACE":

            if 'vocab.getty.edu' in uri and uri[-1].isdigit():
                try:
                    resp = requests.get(url=uri + '.json')
                    data = resp.json()

                    if 'results' in data and 'bindings' in data['results'] and data['results']['bindings']:
                        for triple in data['results']['bindings']:
                            if _contains(triple, ['Subject', 'Predicate', 'Object']):
                                if triple['Predicate']['value'].endswith('rdf-schema#label') and \
                                        'xml:lang' in triple['Object'] and \
                                        triple['Object']['xml:lang'] == 'en':

                                    entity.name = triple['Object']['value']
                                    entity.xml_id = slugify(entity.name)
                                    entity.save()
                                    return str(entity.id), "Entity minted with XML ID {0} and URI {1}".format(entity.xml_id, uri)

                except:
                    return None, "Error referencing PLACE with URI {0}: Unable to determine name using Getty URI".format(uri)

            elif 'geonames.org' in uri:
                if not uri[-1].isdigit():
                    uri_parts = uri.split('/')
                    uri = '/'.join(uri_parts[:-1]) + '/about.rdf'

                try:
                    resp = requests.get(url=uri)
                    rdf = BeautifulSoup(resp.content, 'xml')
                    entity.name = rdf.Feature.find('name').get_text()
                    entity.xml_id = slugify(entity.name)
                    entity.save()
                    return str(entity.id), "Entity minted with XML ID {0} and URI {1}".format(entity.xml_id, uri)

                except:
                    return None, "Error referencing PLACE with URI {0}: Unable to determine name using Geonames URI".format(uri)

    return None, "Error referencing {0} with URI {1}: Source for URI not recognized".format(entity_type, uri)


def log_tag(tag):
    log = ""
    if tag.name:
        log = "[{0}]".format(tag.name)
        if tag.attrs:
            log += " {"
            for attr in tag.attrs.keys():
                log += " {0}={1}".format(attr, tag.attrs[attr])
            log += " }"
    return log


def parse_letter_tei(corpus, tag, entities=[], info=[]):
    html = ""

    simple_conversions = {
        'hi': 'span',
        'opener': 'div:opener',
        'dateline': 'div:dateline',
        'date': 'span:date',
        'salute': 'span:salutation',
        'p': 'p',
        'lb': 'br/',
        'unclear': 'span:unclear',
        'del': 'span:deletion',
        'add': 'span:addition',
        'closer': 'div:closer',
        'postscript': 'div:postscript',
        'note': 'span:note',
        'address': 'span:address',
        'addrLine': 'br/',
        'quote': 'quote',
        'roleName': 'span:role',
        'abbr': 'span:abbreviation',
    }

    silent = [
        'body', 'div', 'orig', 'reg', 'title', 'name', 'forename', 'surname'
    ]

    if tag.name:
        if tag.name in silent:
            for child in tag.children:
                html += parse_letter_tei(corpus, child, entities, info)

        else:
            attributes = ""
            classes = []

            if 'rend' in tag.attrs:
                classes += ["rend-{0}".format(slugify(r)) for r in tag['rend'].split() if r]

            if tag.name == 'pb' and _contains(tag.attrs, ['n', 'facs']):
                html += '''<a name="page-break-{page}" class="page-break" data-page="{page}" data-image="{image}"><i class="fas fa-image"></i></a>'''.format(
                    page=tag['n'],
                    image=tag['facs']
                )

            elif tag.name == 'choice':
                original = tag.find('orig')
                if original:
                    original = original.get_text().strip().replace('"', '\"')
                else:
                    original = ""

                regularized = tag.find('reg')
                if regularized:
                    html += '''<span class="regularized" data-original="{0}">'''.format(original)
                    html += "".join([parse_letter_tei(corpus, child, entities, info) for child in regularized.children])
                    html += "</span>"

            elif tag.name in ['persName', 'placeName'] and 'ref' in tag.attrs:
                entity_type = 'PERSON' if tag.name == 'persName' else 'PLACE'
                entity_id, log = register_entity(corpus, entity_type, tag['ref'])
                html += '''<span class="entity" data-entity-type="{entity_type}" data-entity-uri="{uri}" data-entity-id="{id}">'''.format(
                    entity_type=entity_type,
                    uri=tag['ref'],
                    id=entity_id
                )
                html += "".join([parse_letter_tei(corpus, child, entities, info) for child in tag])
                html += "</span>"

                if entity_id:
                    entities.append(entity_id)
                    if log != 'found':
                        info.append(log)

            elif tag.name in simple_conversions:
                html_tag = simple_conversions[tag.name]
                self_closing = html_tag.endswith('/')
                if self_closing:
                    html_tag = html_tag[:-1]

                if ':' in html_tag:
                    html_tag = html_tag.split(':')[0]
                    classes.append(simple_conversions[tag.name].split(':')[1])

                if classes:
                    attributes += ' class="{0}"'.format(" ".join(classes))
                    if self_closing:
                        attributes += ' /'

                html += "<{0}{1}>".format(
                    html_tag,
                    attributes
                )
                html += "".join([parse_letter_tei(corpus, child, entities, info) for child in tag])
                if not self_closing:
                    html += "</{0}>".format(html_tag)

            # tags to ignore (but keep content inside)
            elif tag.name in silent:
                html += "".join([parse_letter_tei(corpus, child, entities, info) for child in tag])

            else:
                info.append("Unhandled tag: {0}".format(log_tag(tag)))
                html += "".join([parse_letter_tei(corpus, child, entities, info) for child in tag])

    else:
        html += tag.get_text()

    return html
