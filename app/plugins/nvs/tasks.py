import re
import difflib
import html as html_lib
from timeit import default_timer as timer
from dateutil.relativedelta import relativedelta
from .content import REGISTRY as NVS_CONTENT_TYPE_SCHEMA
from plugins.document.content import REGISTRY as DOCUMENT_REGISTRY
from corpus import *
from manager.utilities import _contains, _contains_any
from bs4 import BeautifulSoup
from django.utils.html import strip_tags
from django.utils.text import slugify
from string import punctuation
from random import randint
from mongoengine.queryset.visitor import Q


REGISTRY = {
    "Import NVS Data from TEI": {
        "version": "1.1",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "create_report": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "play_title": {
                    "value": "",
                    "type": "text",
                    "label": "Play Title",
                },
                "play_prefix": {
                    "value": "",
                    "type": "text",
                    "label": "Play Prefix",
                },
                "play_repo": {
                    "value": "",
                    "type": "corpus_repo",
                    "label": "Edition TEI Repository",
                    "note": "Likely named [prefix]_tei"
                },
                "basetext_siglum": {
                    "value": "",
                    "type": "text",
                    "label": "Basetext Siglum",
                    "note": "Likely \"s_f1\" (First Folio)"
                },
                "ingestion_scope": {
                    "value": "Full",
                    "type": "choice",
                    "choices": ["Full", "Playtext Only", "Textual Notes Only", "Commentary Only"],
                    "label": "Scope for Ingestion?",
                    "note": "'Full' will delete all data for play and completely re-ingest from TEI. 'Playtext Only' will also delete all play data but will only ingest playtext for testing. 'Textual Notes Only' will only delete textual note data and then re-ingest textual notes. 'Commentary Only' will only delete commentary note data and then re-ingest commentary notes. NOTE: For either 'Textual Notes Only' or 'Commentary Only', the playtext must have already been ingested."
                }
            },
        },
        "module": 'plugins.nvs.tasks',
        "functions": ['import_data']
    },
    "Perform Textual Note Transforms": {
        "version": "0.2",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "play_prefix": {
                    "value": "",
                    "type": "text",
                    "label": "Play Prefix",
                },
            }
        },
        "module": 'plugins.nvs.tasks',
        "functions": ['perform_note_transforms']
    }
}

nvs_document_fields = [
    {
        "name": "editor",
        "label": "Editor(s)",
        "type": "text",
        "in_lists": True
    },
    {
        "name": "publisher",
        "label": "Publisher",
        "type": "text",
        "in_lists": True
    },
    {
        "name": "place",
        "label": "Place of Publication",
        "type": "text",
        "in_lists": True
    },
    {
        "name": "siglum",
        "label": "Siglum",
        "type": "keyword",
        "in_lists": True
    },
    {
        "name": "siglum_label",
        "label": "Siglum Label",
        "type": "keyword",
        "in_lists": True
    },
    {
        "name": "bibliographic_entry",
        "label": "Bibliographic Entry",
        "type": "text",
        "in_lists": True
    },
    {
        "name": "bibliographic_entry_text",
        "label": "Bibliographic Entry Text",
        "in_lists": True,
        "type": "keyword",
    },
]

nvs_document_types = {
    'witness': 'primary_witness',
    'occasional': 'occasional_witness',
    'pw_primarysources': 'primary_source',
    'pw_occasional': 'occasional_source',
    'bibliography': 'bibliographic_source'
}

job_timers = {}


def import_data(job_id):
    job_timers.clear()
    time_it("Total Ingestion Time")

    job = Job(job_id)
    corpus = job.corpus
    play_repo_name = job.get_param_value('play_repo')
    play_repo = corpus.repos[play_repo_name]
    play_title = job.get_param_value('play_title')
    play_prefix = job.get_param_value('play_prefix')
    basetext_siglum = job.get_param_value('basetext_siglum')
    ingestion_scope = job.get_param_value('ingestion_scope')

    job.set_status('running')
    job.report('''Attempting play TEI ingestion using following parameters:
Play Title:         {0}
Play Repo:          {1}
Play Prefix:        {2}
Copytext Siglum:    {3}
Ingestion Scope:    {4}
    \n'''.format(
        play_title,
        play_repo.name,
        play_prefix,
        basetext_siglum,
        ingestion_scope
    ))

    try:
        es_logger = logging.getLogger('elasticsearch')
        es_log_level = es_logger.getEffectiveLevel()
        es_logger.setLevel(logging.ERROR)

        ensure_nvs_content_types(corpus)

        content_block_handles = [
            'info_about',
            'info_contributors',
            'info_print',
            'info_how_to',
            'info_faqs',
            'tools_about',
            'tools_advanced_search',
            'tools_data'
        ]
        for handle in content_block_handles:
            content_block = corpus.get_content('ContentBlock', {'handle': handle}, single_result=True)
            if not content_block:
                content_block = corpus.get_content('ContentBlock')
                content_block.handle = handle
                content_block.html = "Default content."
                content_block.save()


        time_it("Deleting Play Data")
        deletion_report = delete_play_data(corpus, play_prefix, ingestion_scope)
        time_it("Deleting Play Data", True)
        job.report("Deleted existing play data:\n{0}".format(deletion_report))

        # pull down latest commits to play repo
        play_repo.pull(corpus)

        driver_file_path = "{0}/{1}_driver.xml".format(play_repo.path, play_prefix)
        if os.path.exists(driver_file_path):

            with open(driver_file_path, 'r') as tei_in:
                tei = BeautifulSoup(tei_in, "xml")

            tei_root = tei.TEI

            namespaces = {
                'xi': "http://www.w3.org/2001/XInclude"
            }

            include_file_paths = {
                'front': '',
                'playtext': '',
                'textualnotes': '',
                'commentary': '',
                'appendix': '',
                'bibliography': '',
                'index': '',
                'endpapers': ''
            }

            for include_tag in tei_root.find('text').select('xi|include', namespaces=namespaces):
                x_pointer = include_tag['xpointer']
                href = include_tag['href']

                if x_pointer == 'front':
                    include_file_paths['front'] = href
                elif x_pointer == 'div_playtext':
                    include_file_paths['playtext'] = href
                elif x_pointer == 'div_textualnotes':
                    include_file_paths['textualnotes'] = href
                elif x_pointer == 'div_commentary':
                    include_file_paths['commentary'] = href
                elif x_pointer == 'div_appendix':
                    include_file_paths['appendix'] = href
                elif x_pointer == 'div_bibliography':
                    include_file_paths['bibliography'] = href
                elif x_pointer == 'div_index':
                    include_file_paths['index'] = href
                elif x_pointer == 'div_endpapers':
                    include_file_paths['endpapers'] = href

            job.report("Ingestion files located: \n{0}".format(json.dumps(include_file_paths, indent=4)))

            include_files_exist = True
            for include_file in include_file_paths.keys():
                full_path = os.path.join(os.path.dirname(driver_file_path), include_file_paths[include_file])
                if os.path.exists(full_path):
                    include_file_paths[include_file] = full_path
                else:
                    include_files_exist = False
                    break

            if include_files_exist:
                line_id_map = {}  # to keep track of how xml_ids map to PlayLine ObjectIDs
                ordered_line_ids = []  # PlayLine ObjectIDs in order, for building swaths of lines given start and end ids

                # retrieve/make play using play prefix
                play = corpus.get_content('Play', {'prefix': play_prefix}, single_result=True)
                if not play:
                    play = corpus.get_content('Play')

                play.title = play_title
                play.prefix = play_prefix
                play.save()
                play.reload()

                if play:
                    # PARSE FRONT MATTER
                    if ingestion_scope in ['Full', 'Playtext Only']:
                        time_it("Parsing Front Matter")
                        job.report(
                            parse_front_file(
                                corpus,
                                play,
                                include_file_paths['front']
                            )
                        )
                        time_it("Parsing Front Matter", True)
                        job.set_status('running', percent_complete=17)

                    # PARSE PLAY TEXT
                    if ingestion_scope in ['Full', 'Playtext Only']:
                        time_it("Parsing Playtext")
                        playtext_report, line_id_map, ordered_line_ids = parse_playtext_file(
                            corpus,
                            play,
                            include_file_paths['playtext'],
                            basetext_siglum
                        )
                        job.report(playtext_report)
                        time_it("Parsing Playtext", True)
                        job.set_status('running', percent_complete=34)
                    elif ingestion_scope in ['Textual Notes Only', 'Commentary Only']:
                        # make sure line_id_map and ordered_line_ids gets loaded from JSON
                        line_id_map_json = corpus.path + '/files/{0}_line_id_map.json'.format(play.prefix)
                        ordered_line_ids_json = corpus.path + '/files/{0}_ordered_line_ids.json'.format(play.prefix)

                        if os.path.exists(line_id_map_json) and os.path.exists(ordered_line_ids_json):
                            with open(line_id_map_json, 'r', encoding='utf-8') as line_info_in:
                                line_id_map = json.load(line_info_in)

                            with open(ordered_line_ids_json, 'r', encoding='utf-8') as line_info_in:
                                ordered_line_ids = json.load(line_info_in)

                    # PARSE TEXTUAL NOTES
                    if ingestion_scope in ['Full', 'Textual Notes Only']:
                        time_it("Parsing Textual Notes")
                        job.report(
                            parse_textualnotes_file(
                                corpus,
                                play,
                                include_file_paths['textualnotes'],
                                line_id_map,
                                ordered_line_ids
                            )
                        )
                        time_it("Parsing Textual Notes", True)
                        job.set_status('running', percent_complete=51)

                    # PARSE BIBLIOGRAPHY
                    if ingestion_scope == 'Full':
                        time_it("Parsing Bibliography")
                        job.report(
                            parse_bibliography(
                                corpus,
                                play,
                                include_file_paths['bibliography']
                            )
                        )
                        time_it("Parsing Bibliography", True)
                        job.set_status('running', percent_complete=68)

                    # PARSE COMMENTARY
                    if ingestion_scope in ['Full', 'Commentary Only']:
                        time_it("Parsing Commentary")
                        job.report(
                            parse_commentary(
                                corpus,
                                play,
                                include_file_paths['commentary'],
                                line_id_map,
                                ordered_line_ids
                            )
                        )
                        time_it("Parsing Commentary", True)
                        job.set_status('running', percent_complete=75)

                    # PARSE APPENDIX
                    if ingestion_scope == 'Full':
                        time_it("Parsing Appendix")
                        job.report(
                            parse_appendix(
                                corpus,
                                play,
                                play_repo_name,
                                include_file_paths['appendix']
                            )
                        )
                        time_it("Parsing Appendix", True)
                        job.set_status('running', percent_complete=85)

                    if ingestion_scope in ['Full', 'Playtext Only', 'Commentary Only']:
                        time_it("Rendering Playline HTML")
                        line_count = corpus.get_content('PlayLine', {'play': play.id}, all=True).count()
                        line_cursor = 0
                        line_chunk_size = 200
                        while line_cursor < line_count:
                            render_lines_html(corpus, play, starting_line_no=line_cursor, ending_line_no=line_cursor + line_chunk_size)
                            line_cursor += line_chunk_size + 1
                        time_it("Rendering Playline HTML", True)

        time_it("Total Ingestion Time", True)

        job.report("\n\nTEI Ingestion Stats:")
        intervals = ['days', 'hours', 'minutes', 'seconds']
        for timer_name in job_timers.keys():
            time_spent = relativedelta(seconds=int(job_timers[timer_name]['total']))
            job.report("{0}: {1}".format(
                timer_name,
                ' '.join('{0} {1}'.format(getattr(time_spent, interval), interval) for interval in intervals if getattr(time_spent, interval))
            ))

        job.complete(status='complete')
        es_logger.setLevel(es_log_level)
    except:
        job.report("\n\nA major error prevented the ingestion of play TEI:\n{0}".format(
            traceback.format_exc()
        ))
        job.complete(status='error')


def reset_nvs_content_types(corpus):
    deletion_order = [
        'ParaText',
        'Speech',
        'Character',
        'Commentary',
        'TextualNote',
        'TextualVariant',
        'PlayTag',
        'PlayLine',
        'WitnessLocation',
        'Reference',
        'DocumentCollection',
        'ContentBlock',
        'Play',
        'Document'
    ]

    for nvs_content_type in deletion_order:
        if nvs_content_type in corpus.content_types:
            corpus.delete_content_type(nvs_content_type)

    ensure_nvs_content_types(corpus)


def ensure_nvs_content_types(corpus):
    nvs_doc_schema = None
    for schema in DOCUMENT_REGISTRY:
        if schema['name'] == "Document":
            nvs_doc_schema = deepcopy(schema)
            break

    if nvs_doc_schema:
        nvs_doc_schema['fields'] += nvs_document_fields
        nvs_doc_schema['templates']['Label']['template'] = "{{ Document.siglum|safe }}"

        doc_schema_ensured = True
        if 'Document' in corpus.content_types:
            corpus_doc_ct = corpus.content_types['Document']
            for field in nvs_document_fields:
                if not corpus_doc_ct.get_field(field['name']):
                    doc_schema_ensured = False
        else:
            doc_schema_ensured = False

        if not doc_schema_ensured:
            # We shouldn't ever delete documents in case they have associated transcription projects!
            # corpus.delete_content_type('Document')
            corpus.save_content_type(nvs_doc_schema)

    for nvs_content_type in NVS_CONTENT_TYPE_SCHEMA:
        if nvs_content_type['name'] not in corpus.content_types:
            corpus.save_content_type(nvs_content_type)


def delete_play_data(corpus, play_prefix, ingestion_scope):
    report = ""
    play = corpus.get_content('Play', {'prefix': play_prefix}, single_result=True)
    if play:
        nvs_content_types = [
            'WitnessLocation',
            'PlayTag',
            'ParaText',
            'Character',
            'Commentary',
            'TextualVariant',
            'TextualNote',
            'Speech',
            'PlayLine',
            'DocumentCollection',
            'Reference'
        ]

        if ingestion_scope == 'Textual Notes Only':
            nvs_content_types = ['TextualVariant', 'TextualNote']
        elif ingestion_scope == 'Commentary Only':
            nvs_content_types = ['Commentary']

            # Also delete commentary play tags
            com_spans = corpus.get_content('PlayTag', {'play': play.id, 'name': 'comspan'})
            for com_span in com_spans:
                com_span.delete(track_deletions=False)

        for nvs_ct in nvs_content_types:
            contents = corpus.get_content(nvs_ct, {'play': play.id})
            count = contents.count()
            for content in contents:
                content.delete(track_deletions=False)
            report += '{0} {1}(s) deleted.\n'.format(count, nvs_ct)

        if ingestion_scope in ['Full', 'Playtext Only']:
            play.delete()
    return report


def parse_front_file(corpus, play, front_file_path):
    report = '''
##########################################################
FRONT MATTER INGESTION
##########################################################\n'''

    with open(front_file_path, 'r') as tei_in:
        tei_text = tei_in.read()
        text_replacements = extract_text_replacements(tei_in)

        for text, replacement in text_replacements.items():
            tei_text = tei_text.replace(text, replacement)

        front_tei = BeautifulSoup(tei_text, "xml")

    # list for tracking unhandled tags:
    unhandled = []

    # extract credits
    pt = corpus.get_content('ParaText')
    pt.play = play.id
    pt.xml_id = 'front'
    pt.section = "Front Matter"
    pt.title = "Credits"
    pt.order = 0
    pt.level = 1
    pt.html_content = ''

    title_page = front_tei.find('titlePage', type='main')
    volume_title = title_page.find('titlePart', type='volume')
    if volume_title:
        pt.html_content += '<p style="margin-top: 20px;">{0}</p>\n\n<p>Edited by<br />'.format(volume_title.string)

        primary_editors = title_page.find_all('editor', role='primary')
        if primary_editors:
            primary_editors = [pri_ed.string for pri_ed in primary_editors]
            pt.html_content += "{0}".format("<br />".join(primary_editors))

            secondary_editors = title_page.find_all('editor', role='secondary')
            if secondary_editors:
                pt.html_content += "<br />with<br />"
                secondary_editors = [sec_ed.string for sec_ed in secondary_editors]
                pt.html_content += "<br />".join(secondary_editors)

            pt.html_content += "</p>"
            pt.save()

    # extract preface
    preface = front_tei.find('div', type='preface')
    pt = corpus.get_content('ParaText')
    pt.play = play.id
    pt.xml_id = preface['xml:id']
    pt.section = "Front Matter"
    pt.order = 1
    pt.level = 1
    pt.html_content = ""

    pt_data = {
        'current_note': None,
        'unhandled': [],
        'corpus': corpus
    }

    for child in preface.children:
        pt.html_content += handle_paratext_tag(child, pt, pt_data)

    unhandled += list(set(pt_data['unhandled']))
    pt.save()

    # extract acknowledgements
    acknow = front_tei.find('div', type='acknowledgements')
    if acknow:
        pt = corpus.get_content('ParaText')
        pt.play = play.id
        pt.xml_id = acknow['xml:id']
        pt.section = "Front Matter"
        pt.order = 2
        pt.level = 1
        pt.html_content = ""

        pt_data = {
            'current_note': None,
            'unhandled': [],
            'corpus': corpus
        }

        for child in acknow.children:
            pt.html_content += handle_paratext_tag(child, pt, pt_data)

        unhandled += list(set(pt_data['unhandled']))
        pt.save()

    # extract plan of work
    plan_of_work = front_tei.find('div', type='potw')
    pt = corpus.get_content('ParaText')
    pt.play = play.id
    pt.xml_id = plan_of_work['xml:id']
    pt.section = "Front Matter"
    pt.order = 3
    pt.level = 1
    pt.html_content = ""

    pt_data = {
        'current_note': None,
        'unhandled': [],
        'corpus': corpus
    }

    for child in plan_of_work.children:
        pt.html_content += handle_paratext_tag(child, pt, pt_data)

    unhandled += list(set(pt_data['unhandled']))
    pt.save()

    if unhandled:
        report += "When ingesting the Preface and Plan of Work, the following TEI tags were not properly converted to HTML: {0}\n\n".format(
            ", ".join(unhandled)
        )

    # extract witness and reference documents
    try:
        # todo: cleanup old reference approach
        for field in ['primary_witnesses', 'occasional_witnesses', 'primary_sources', 'occasional_sources']:
            setattr(play, field, [])

        witness_collections = []
        unhandled = []

        for witness_list in plan_of_work.find_all('listWit'):
            nvs_doc_type = witness_list['xml:id'].replace("listwit_", "")
            if nvs_doc_type == "editions":
                nvs_doc_type = "witness"
            elif nvs_doc_type == "other":
                nvs_doc_type = "occasional"

            doc_type_count = 0
            for witness_tag in witness_list.find_all('witness'):
                siglum = witness_tag['xml:id']
                siglum_label = tei_to_html(witness_tag.siglum)
                if 'rend' in witness_tag.siglum.attrs and witness_tag.siglum['rend'] == 'smcaps':
                    siglum_label = "<span style='font-variant: small-caps;'>{0}</span>".format(siglum_label)

                if witness_tag.bibl:
                    pub_date = _str(witness_tag.date)
                    pub_date = re.sub(r"\D", "", pub_date)
                    pub_date = pub_date[:4]

                    witness, bibliographic_entry = handle_bibl_tag(
                        corpus,
                        witness_tag.bibl,
                        unhandled,
                        xml_id=siglum,
                        date=pub_date,
                        siglum_label=siglum_label
                    )
                    doc_type_count += 1

                    # Fix bibliographic entries for witnesses by including date
                    if not strip_tags(bibliographic_entry).strip().endswith('.'):
                        bibliographic_entry += '.'
                    bibliographic_entry += ' {0}.'.format(pub_date)

                    ref_type = nvs_document_types[nvs_doc_type]
                    reference = corpus.get_content("Reference")
                    reference.play = play.id
                    reference.document = witness.id
                    reference.ref_type = ref_type
                    reference.bibliographic_entry = bibliographic_entry
                    reference.bibliographic_entry_text = strip_tags(bibliographic_entry).strip()
                    reference.save()

                elif 'corresp' in witness_tag.attrs:
                    witness_collections.append({
                        'siglum': siglum,
                        'siglum_label': siglum_label,
                        'tag': witness_tag
                    })

            report += "{0} {1} editions ingested.\n\n".format(doc_type_count, nvs_doc_type)

        play.save()

        for witness_collection_info in witness_collections:
            witness_collection = corpus.get_content('DocumentCollection', {'play': play.id, 'siglum': witness_collection_info['siglum']}, single_result=True)
            if not witness_collection:
                witness_collection = corpus.get_content('DocumentCollection')
                witness_collection.play = play.id
                witness_collection.siglum = witness_collection_info['siglum']

            witness_collection.siglum_label = witness_collection_info['siglum_label']
            witness_tag = witness_collection_info['tag']
            witness_collection.referenced_documents = []

            referenced_witnesses = witness_tag['corresp'].split(' ')
            for reffed in referenced_witnesses:
                reffed_siglum = reffed.replace('#', '')
                reffed_doc = corpus.get_content('Document', {'siglum': reffed_siglum}, single_result=True)
                witness_collection.referenced_documents.append(reffed_doc.id)

            witness_collection.save()

        bibl_count = 0
        for bibl_list in plan_of_work.find_all('listBibl'):
            nvs_doc_type = bibl_list['xml:id'].replace("bibl_", "")
            ref_type = nvs_document_types[nvs_doc_type]

            for bibl in bibl_list.find_all('bibl'):
                doc, bibliographic_entry = handle_bibl_tag(corpus, bibl, unhandled)
                if doc and bibliographic_entry:
                    bibl_count += 1

                    reference = corpus.get_content(
                        "Reference",
                        {'play': play.id, 'document': doc.id, 'ref_type': ref_type},
                        single_result=True
                    )
                    if not reference:
                        reference = corpus.get_content("Reference")
                        reference.play = play.id
                        reference.document = doc.id
                        reference.ref_type = ref_type
                        reference.bibliographic_entry = bibliographic_entry
                        reference.bibliographic_entry_text = strip_tags(bibliographic_entry).strip()
                        reference.save()

                    #if doc not in getattr(play, play_field):
                    #    getattr(play, play_field).append(doc.id)
                else:
                    report += "Error parsing the following bibliographic entry:\n{0}\n\n".format(str(bibl))

        play.save()
        report += "{0} bibliographic entries ingested.\n\n".format(bibl_count)

        unhandled = list(set(unhandled))
        if unhandled:
            report += "When ingesting bibliographic entries from the front matter, the following TEI tags were not properly converted to HTML: {0}\n\n".format(
                ", ".join(unhandled)
            )

    except:
        report += "A error occurred preventing the full ingestion of the front matter:\n{0}\n\n".format(traceback.format_exc())

    del front_tei
    return report


def parse_playtext_file(corpus, play, playtext_file_path, basetext_siglum):
    report = '''
##########################################################
PLAY TEXT INGESTION
##########################################################\n'''
    unhandled_tags = []
    line_id_map = {}
    ordered_line_ids = []

    with open(playtext_file_path, 'r') as tei_in:
        tei_text = tei_in.read()
        text_replacements = extract_text_replacements(tei_in)

        for text, replacement in text_replacements.items():
            tei_text = tei_text.replace(text, replacement)

        lines_tei = BeautifulSoup(tei_text, "xml")

    # retrieve basetext document
    basetext = corpus.get_content("Document", {'siglum': basetext_siglum})[0]

    # get witness count
    wit_count = corpus.get_content("Reference", {'play': play.id, 'ref_type': 'primary_witness'}).count()

    try:
        # setup context info for parsing playlines
        line_info = {
            'line_number': 0,
            'line_xml_id': None,
            'line_alt_xml_ids': [],
            'line_label': None,
            'act': None,
            'scene': None,
            'witness_location_id': None,
            'witness_count': wit_count,
            'basetext_id': basetext.id,
            'unhandled_tags': [],
            'characters': [],
            'character_id_map': {},
            'current_speech': None,
            'current_speech_ended': False,
            'text': ''
        }

        # extract dramatis personae, add to context info
        cast_list = lines_tei.find("castList")
        for cast_item in cast_list.find_all("castItem"):
            current_role = None
            if hasattr(cast_item, 'roleDesc'):
                current_role = _str(cast_item.roleDesc)

            for role in cast_item.find_all("role"):
                character = corpus.get_content('Character')
                character.play = play.id
                character.xml_id = role['xml:id']
                character.name = _str(role)
                if not character.name:
                    character.name = character.xml_id
                if current_role:
                    character.role = current_role

                character.save()
                line_info['characters'].append(character)
                line_info['character_id_map'][character.xml_id] = character.id

        report += "The following characters have been ingested: {0}\n\n".format(
            ", ".join([char.name for char in line_info['characters']])
        )

        # recursively parse the playtext
        for child in lines_tei.find('div', attrs={'type': 'playtext', 'xml:id': 'div_playtext'}).children:
            handle_playtext_tag(corpus, play, child, line_info)

        fakeline = BeautifulSoup('<lb xml:id="xxxx" n="xxxx"/>', 'xml')
        handle_playtext_tag(corpus, play, fakeline.lb, line_info)

        # build line_id_map and ordered_line_ids for use by get_line_ids functions
        lines = corpus.get_content('PlayLine', {'play': play.id}, only=['id', 'xml_id', 'alt_xml_ids'])
        lines = lines.order_by('line_number')
        for line in lines:
            ordered_line_ids.append(str(line.id))

            if line.xml_id not in line_id_map:
                line_id_map[line.xml_id] = [str(line.id)]
            else:
                line_id_map[line.xml_id].append(str(line.id))

            for alt_xml_id in line.alt_xml_ids:
                if alt_xml_id not in line_id_map:
                    line_id_map[alt_xml_id] = [str(line.id)]
                else:
                    line_id_map[alt_xml_id].append(str(line.id))

        # register virtual line info in line_id_map
        links = lines_tei.find_all('link')
        for link in links:
            if _contains(link.attrs, ['xml:id', 'type', 'target']):
                xml_id = link['xml:id']
                if xml_id not in line_id_map:
                    line_id_map[xml_id] = []

                targets = link['target'].replace('#', '').split()
                for target in targets:
                    if target in line_id_map:
                        line_id_map[xml_id] += line_id_map[target]

        # output line_id_map and ordered_line_ids for debugging or standalone textual/commentary note ingestion
        with open(corpus.path + '/files/{0}_line_id_map.json'.format(play.prefix), 'w', encoding='utf-8') as line_info_out:
            json.dump(line_id_map, line_info_out, indent=4)

        with open(corpus.path + '/files/{0}_ordered_line_ids.json'.format(play.prefix), 'w', encoding='utf-8') as line_info_out:
            json.dump(ordered_line_ids, line_info_out, indent=4)

        report += "{0} lines ingested.\n\n".format(line_info['line_number'])
        line_info['unhandled_tags'] = list(set(line_info['unhandled_tags']))
        if line_info['unhandled_tags']:
            report += "When ingesting lines from the play text, the following TEI tags were not properly converted to HTML: {0}\n\n".format(
                ", ".join(line_info['unhandled_tags'])
            )

        del line_info
    except:
        report += "An error prevented full ingestion of the play text:\n\n{0}".format(traceback.format_exc())

    del lines_tei
    return report, line_id_map, ordered_line_ids


def handle_playtext_tag(corpus, play, tag, line_info):

    # if the tag has a name, it's an XML node
    if tag.name:
        # milestone
        if tag.name == 'milestone' and _contains(tag.attrs, ['unit', 'n']):
            witness_location = corpus.get_content('WitnessLocation')
            witness_location.witness = line_info['basetext_id']
            witness_location.starting_page = tag['n']
            witness_location.play = play.id
            witness_location.save()
            line_info['witness_location_id'] = witness_location.id

        # lb
        elif tag.name == 'lb' and _contains(tag.attrs, ['xml:id', 'n']):
            # make current line if appropriate
            if line_info['line_xml_id']:
                make_playtext_line(corpus, play, line_info)

            line_info['line_xml_id'] = tag['xml:id']
            line_info['line_label'] = tag['n']
            line_info['line_alt_xml_ids'] = []

            tln_matches = re.findall(r'(tln_\d\d\d\d)', tag['xml:id'])
            if tln_matches:
                for match in tln_matches:
                    if match != line_info['line_xml_id']:
                        line_info['line_alt_xml_ids'].append(match)

        # nvsSeg
        elif tag.name == 'nvsSeg':
            if 'xml:id' in tag.attrs:
                line_info['line_alt_xml_ids'].append(tag['xml:id'].strip())
                tln_matches = re.findall(r'(tln_\d\d\d\d)', tag['xml:id'])
                if tln_matches:
                    for match in tln_matches:
                        if match != line_info['line_xml_id'] and match not in line_info['line_alt_xml_ids']:
                            line_info['line_alt_xml_ids'].append(match)

            for child in tag.children:
                handle_playtext_tag(corpus, play, child, line_info)

        # todo: anchor (with marker attribute)

        # div for act/scene
        elif tag.name == 'div' and _contains(tag.attrs, ['type', 'n']):
            # if this is the first act/scene, make sure last line of DP is created
            if line_info['line_xml_id']:
                make_playtext_line(corpus, play, line_info)
                line_info['line_xml_id'] = None

            line_info[tag['type']] = tag['n']

            for child in tag.children:
                handle_playtext_tag(corpus, play, child, line_info)

            if line_info['line_xml_id']:
                make_playtext_line(corpus, play, line_info)
                line_info['line_xml_id'] = None

            if tag['type'] == "act":
                line_info['act'] = "Trailer"
                line_info['scene'] = "0"

        # all other tags handled by PlayTag convention
        else:
            playtag = None
            playtag_name = None
            playtag_classes = None

            # stage
            if tag.name == 'stage' and 'type' in tag.attrs:
                playtag_name = 'span'
                playtag_classes = 'stage {0}'.format(tag['type'])

            # sp
            elif tag.name == 'sp' and 'who' in tag.attrs:
                playtag_name = 'span'
                speaking = tag['who'].replace('#', '')
                playtag_classes = 'speech {0}'.format(speaking)

                line_info['current_speech'] = corpus.get_content('Speech')
                line_info['current_speech'].play = play.id
                line_info['current_speech'].act = line_info['act']
                line_info['current_speech'].scene = line_info['scene']
                for char_id in [line_info['character_id_map'][xml_id] for xml_id in speaking.split() if xml_id]:
                    line_info['current_speech'].speaking.append(char_id)

            # name
            elif tag.name == 'name':
                playtag_name = 'span'
                playtag_classes = 'entity'

            # head
            elif tag.name == 'head':
                playtag_name = 'h3'
                playtag_classes = 'heading'

            # speaker
            elif tag.name == 'speaker':
                playtag_name = 'span'
                playtag_classes = 'speaker-abbreviation'

            # castList
            elif tag.name == 'castList' and 'xml:id' in tag.attrs:
                playtag_name = 'span'
                playtag_classes = 'castlist {0}'.format(tag['xml:id'])

            # castGroup
            elif tag.name == 'castGroup' and 'rend' in tag.attrs:
                playtag_name = 'span'
                matches = re.findall(r'[^\(]*\(([^\)]*)\)', tag['rend'])
                if matches:
                    playtag_classes = 'castgroup {0}'.format(matches[0].replace('#', ''))

            # castItem
            elif tag.name == 'castItem':
                playtag_name = 'span'
                playtag_classes = 'castitem'

            # role
            elif tag.name == 'role' and 'xml:id' in tag.attrs:
                playtag_name = 'span'
                playtag_classes = 'role {0}'.format(tag['xml:id'])

            # roleDesc
            elif tag.name == 'roleDesc':
                playtag_name = 'span'
                playtag_classes = 'roledesc'

                if 'xml:id' in tag.attrs:
                    playtag_classes += " {0}".format(tag['xml:id'])

            # foreign
            elif tag.name == 'foreign':
                playtag_name = 'span'
                playtag_classes = 'foreign'
                if 'xml:lang' in tag.attrs:
                    playtag_classes += " {0}".format(tag['xml:lang'])

            # p rend=italic
            elif tag.name == 'p' and 'rend' in tag.attrs and tag['rend'] == 'italic':
                playtag_name = 'i'
                playtag_classes = 'italicized'

            # lg
            elif tag.name == 'lg' and 'type' in tag.attrs:
                playtag_name = 'span'
                playtag_classes = 'linegroup {0}'.format(tag['type'])
                if 'rend' in tag.attrs and tag['rend'] == 'italic':
                    playtag_classes += " italicized"

            # anchor type=marker
            elif tag.name == 'anchor' and 'type' in tag.attrs and tag['type'] == 'marker' and 'marker' in tag.attrs:
                playtag_name = 'span'

                if tag['marker'] == '[':
                    playtag_classes = 'open-bracket-marker'
                elif tag['marker'] == ']':
                    playtag_classes = 'close-bracket-marker'
                elif tag['marker'] == '⸢':
                    playtag_classes = 'open-half-bracket-marker'
                elif tag['marker'] == '⸣':
                    playtag_classes = 'close-half-bracket-marker'
                elif tag['marker'] == '*':
                    playtag_classes = 'asterix-marker'
                elif tag['marker'] == '|':
                    playtag_classes = 'pipe-marker'

            else:
                line_info['unhandled_tags'].append(tag.name)

            if playtag_name:
                playtag = corpus.get_content('PlayTag')
                playtag.play = play.id
                playtag.name = playtag_name
                playtag.classes = playtag_classes
                playtag.start_location = make_text_location(line_info['line_number'], len(line_info['text']))

            for child in tag.children:
                handle_playtext_tag(corpus, play, child, line_info)

            if playtag:
                playtag.end_location = make_text_location(line_info['line_number'], len(line_info['text']))
                playtag.save()

                if line_info['current_speech'] and 'speech' in playtag.classes:
                    line_info['current_speech_ended'] = True

                elif playtag.classes == 'speaker-abbreviation':
                    if line_info['current_speech'] and len(line_info['current_speech'].speaking) == 1:
                        char_id = line_info['current_speech'].speaking[0]
                        for char in line_info['characters']:
                            if char.id == char_id:
                                if line_info['text'] not in char.speaker_abbreviations:
                                    char.speaker_abbreviations.append(line_info['text'])
                                    char.save()

                    line_info['text'] += ' ' # <- adding a space after speaker abbrevs (not present in TEI)

    # otherwise, this is a string of the playtext to be kept track of for building the playlines
    else:
        new_words = str(tag)
        line_info['text'] += new_words.replace('\n', '')


def make_playtext_line(corpus, play, line_info):
    line = corpus.get_content('PlayLine')
    line.play = play.id
    line.xml_id = line_info['line_xml_id']
    line.line_label = line_info['line_label']
    line.line_number = line_info['line_number']

    for alt_xml_id in line_info['line_alt_xml_ids']:
        line.alt_xml_ids.append(alt_xml_id)

    if line_info['act'] and line_info['scene']:
        line.act = line_info['act']
        line.scene = line_info['scene']
    else:
        line.act = "Dramatis Personae"
        line.scene = "0"

    if line_info['witness_location_id']:
        line.witness_locations.append(line_info['witness_location_id'])
    line.text = line_info['text'].strip()
    line.witness_meter = "0" * (line_info['witness_count'] + 1)
    line.save()

    line_info['line_number'] += 1
    line_info['text'] = ''

    if line_info['current_speech']:
        line_info['current_speech'].lines.append(line)

        if line_info['current_speech_ended']:
            line_info['current_speech'].text = stitch_lines(line_info['current_speech'].lines, embed_line_markers=True)
            line_info['current_speech'].lines = [line.id for line in line_info['current_speech'].lines]
            line_info['current_speech'].save()
            line_info['current_speech'] = None
            line_info['current_speech_ended'] = False


def make_text_location(line_number, char_index):
    text_location = str(char_index)
    while len(text_location) < 3:
        text_location = '0' + text_location
    text_location = "{0}.{1}".format(line_number, text_location)
    return float(text_location)


def parse_textualnotes_file(corpus, play, textualnotes_file_path, line_id_map, ordered_line_ids, tn_xml_id=None):
    report = '''
##########################################################
TEXTUAL NOTES INGESTION
##########################################################\n'''

    try:
        # open textualnotes xml, read raw text into tei_text,
        # and perform special text replacements before feeding
        # into BeautifulSoup
        with open(textualnotes_file_path, 'r') as tei_in:
            tei_text = tei_in.read()
            text_replacements = extract_text_replacements(tei_in)

            for text, replacement in text_replacements.items():
                tei_text = tei_text.replace(text, replacement)

            notes_tei = BeautifulSoup(tei_text, "xml")

        all_sigla = []

        # get list of witnesses ordered by publication date so as
        # to handle witness ranges
        references = corpus.get_content("Reference", {'play': play.id, 'ref_type': 'primary_witness'}).order_by('+id')
        witnesses = [ref.document for ref in references]
        for witness in witnesses:
            all_sigla.append(strip_tags(witness.siglum_label).lower())

        # get "document collections" for shorthand witness groups
        witness_groups = list(corpus.get_content('DocumentCollection', {'play': play.id}))

        for witness_group in witness_groups:
            all_sigla.append(strip_tags(witness_group.siglum_label).lower())

        with open(corpus.path + '/files/' + play.prefix + '_sigla.json', 'w', encoding='utf-8') as sigla_out:
            json.dump(all_sigla, sigla_out)

        # get all "note" tags, corresponding to TexualNote content
        # type so we can iterate over and build them
        note_counter = 0
        note_attrs = {'type': 'textual'}

        # if a tn_xml_id was passed in, restrict note results to a
        # single note w/ matching id
        if tn_xml_id:
            note_attrs['xml:id'] = tn_xml_id

        notes = notes_tei.find_all("note", attrs=note_attrs)
        for note in notes:

            # create instance of TextualNote
            textual_note = corpus.get_content('TextualNote')
            textual_note.play = play.id
            textual_note.xml_id = note['xml:id']
            textual_note.witness_meter = "0" * (len(witnesses) + 1)

            textual_note.lines, line_err_msg = get_line_ids(
                note['target'],
                note.attrs.get('targetEnd', None),
                line_id_map,
                ordered_line_ids
            )
            if line_err_msg:
                report += "Error finding lines for textual note {0}: {1}\n\n".format(textual_note.xml_id, line_err_msg)

            if textual_note.lines and not line_err_msg:
                note_lemma = None
                if note.app.find('lem', recursive=False):
                    note_lemma = tei_to_html(note.app.lem)

                current_color = 1
                note_exclusions = []
                note_exclusion_formula = ''
                variants = note.app.find_all('appPart')

                for variant in variants:
                    textual_variant = corpus.get_content('TextualVariant')
                    textual_variant.play = play.id

                    references_selectively_quoted_witness = False

                    reading_description = variant.find('rdgDesc')
                    if reading_description:
                        textual_variant.description = tei_to_html(reading_description)

                    reading = variant.find('rdg')
                    if reading:
                        if 'type' in reading.attrs:
                            textual_variant.transform_type = reading['type']
                            if 'subtype' in reading.attrs:
                                textual_variant.transform_type += '_' + reading['subtype']
                        else:
                            textual_variant.transform_type = "punctuation"
                        textual_variant.transform = tei_to_html(reading)

                    if note_lemma:
                        textual_variant.lemma = note_lemma
                    else:
                        lem_tag = variant.find('lem')
                        if lem_tag:
                            textual_variant.lemma = tei_to_html(lem_tag)

                    starting_siglum = None
                    ending_siglum = None
                    next_siglum_ends = False
                    include_all_following = False
                    exclusion_started = False
                    excluding_sigla = []

                    textual_variant.witness_formula = ""
                    for child in variant.wit.children:
                        if child.name == 'siglum':
                            siglum_label = strip_tags(tei_to_html(child)).replace(';', '')
                            textual_variant.witness_formula += '''
                                <a href="#" class="ref-siglum variant-siglum" onClick="navigate_to('siglum', '{0}', this); return false;">{0}</a>
                            '''.format(siglum_label)
                            if siglum_label.lower() not in all_sigla:
                                references_selectively_quoted_witness = True

                            if not starting_siglum:
                                starting_siglum = siglum_label
                            elif next_siglum_ends:
                                ending_siglum = siglum_label
                                next_siglum_ends = False
                            elif exclusion_started:
                                excluding_sigla.append(siglum_label)

                        else:
                            if 'etc.' in str(child.string):
                                textual_variant.witness_formula += note_exclusion_formula
                            else:
                                textual_variant.witness_formula += str(child.string)

                            formula = str(child.string).strip()

                            # handle '+' ranges
                            if formula.startswith('+') or 'etc.' in formula:
                                include_all_following = True
                                if '(−' in formula:
                                    exclusion_started = True

                            # handle exclusions
                            if '(−' in formula:
                                exclusion_started = True
                            elif formula.startswith(')') and exclusion_started:
                                exclusion_started = False

                            # handle '-' ranges
                            elif formula.startswith('-'):
                                next_siglum_ends = True

                            # use ',' to delimit the need to add individual sigla or add ranges
                            if ',' in formula:
                                if starting_siglum and not exclusion_started:

                                    # the "get_witness_ids" function will handle:
                                    # '-' ranges
                                    # '+' ranges
                                    # exclusions
                                    # individual sigla
                                    textual_variant.witnesses.extend(
                                        get_witness_ids(
                                            witnesses,
                                            witness_groups,
                                            starting_siglum,
                                            ending_witness_siglum=ending_siglum,
                                            include_all_following=include_all_following,
                                            excluding_sigla=excluding_sigla + note_exclusions
                                        )
                                    )

                                    starting_siglum = None
                                    ending_siglum = None
                                    include_all_following = False
                                    excluding_sigla = []

                    # handle any further additions of sigla at the end of the formula
                    if starting_siglum:
                        textual_variant.witnesses.extend(
                            get_witness_ids(
                                witnesses,
                                witness_groups,
                                starting_siglum,
                                ending_witness_siglum=ending_siglum,
                                include_all_following=include_all_following,
                                excluding_sigla=excluding_sigla + note_exclusions
                            )
                        )

                    has_note_exclusions = False
                    try:
                        textual_variant.variant, has_note_exclusions = perform_variant_transform(corpus, textual_note, textual_variant)
                    except:
                        report += "Error when performing transform for variant in note {0}:\n{1}\n\n".format(
                            textual_note.xml_id,
                            traceback.format_exc()
                        )
                        textual_variant.has_bug = 1

                    # If this variant was of type 'lem,' then 'has_note_exclusions' will be set to True.
                    # When this is the case, there's no need to save the variant or color witness meters,
                    # as variants of type 'lem' are when the lemma matches the copy-text. Therefore, the
                    # witnesses associated with this variant will be considered note-wide exclusions.
                    if has_note_exclusions:
                        note_exclusions += [strip_tags(w.siglum_label) for w in witnesses if w.id in textual_variant.witnesses]
                        note_exclusion_formula = "+ (-{0})".format(textual_variant.witness_formula)
                    else:
                        # If the 'note_exclusions' list has entries, it means an earlier variant for this note was
                        # of type 'lem,' and therefore any witnesses pertaining to this variant need to be added
                        # to the list of exclusions
                        if note_exclusions:
                            note_exclusions += [strip_tags(w.siglum_label) for w in witnesses if w.id in textual_variant.witnesses]

                        variant_witness_indicators = get_variant_witness_indicators(witnesses, textual_variant)
                        textual_variant.witness_meter = make_witness_meter(
                            variant_witness_indicators,
                            marker=str(current_color),
                            references_selectively_quoted_witness=references_selectively_quoted_witness
                        )

                        current_color += 2
                        if current_color >= 10:
                            current_color -= 9

                        textual_note.witness_meter = collapse_indicators(textual_variant.witness_meter, textual_note.witness_meter)

                        textual_variant.save()
                        textual_note.variants.append(textual_variant.id)

                textual_note.save()
                note_counter += 1

        report += "{0} textual notes ingested.\n\n".format(note_counter)

        # Only recolor lines, variants, and notes if all textual notes were parsed (not just one)
        if not tn_xml_id:
            lines = corpus.get_content('PlayLine', {'play': play.id})
            lines = lines.order_by('line_number')
            lines = corpus.explore_content(
                left_content_type='PlayLine',
                left_content=lines,
                relationship='haslines',
                cardinality=2,
                right_content_type="TextualNote",
                order_by="right.uri"
            )
            recolored_notes = {}

            for line in lines:
                line.witness_meter = "0" * (len(witnesses) + 1)
                if hasattr(line, '_exploration') and 'haslines' in line._exploration:
                    color_offset = 0

                    for note_dict in line._exploration['haslines']:
                        note_id = note_dict['id']
                        note = corpus.get_content('TextualNote', note_id)

                        if color_offset > 0 and note_id not in recolored_notes:
                            note.witness_meter = "0" * (len(witnesses) + 1)

                            for variant in note.variants:
                                chosen_marker = max([int(i) for i in variant.witness_meter])
                                if chosen_marker:
                                    chosen_marker += color_offset
                                    while chosen_marker > 9:
                                        chosen_marker -= 10

                                    if chosen_marker <= 0:
                                        chosen_marker = randint(1, 9)

                                    variant_indicators = []
                                    for i in variant.witness_meter:
                                        if i == '0':
                                            variant_indicators.append(0)
                                        else:
                                            variant_indicators.append(chosen_marker)

                                    variant.witness_meter = "".join([str(i) for i in variant_indicators])
                                    variant.save(do_indexing=['witness_meter'], do_linking=False, relabel=False)
                                    note.witness_meter = collapse_indicators(variant.witness_meter, note.witness_meter)

                            note.save(do_indexing=['witness_meter', 'variants'], do_linking=False, relabel=False)
                            recolored_notes[note_id] = 1

                        line.witness_meter = collapse_indicators(note.witness_meter, line.witness_meter)
                        note_indicators = [int(i) for i in note.witness_meter]
                        color_offset += max(note_indicators) + 1

                    line.save(do_indexing=['witness_meter'], do_linking=False, relabel=False)

            del lines

    except:
        report += "An error prevented full ingestion of textual notes:\n{0}\n\n".format(traceback.format_exc())

    del notes_tei
    return report


def collapse_indicators(variant, base):
    collapsed = base
    if variant and base and len(variant) == len(base):
        for index in range(0, len(variant)):
            if variant[index] != "0":
                collapsed = collapsed[:index] + variant[index] + collapsed[index + 1:]
    return collapsed


def perform_note_transforms(job_id):
    job = Job(job_id)
    corpus = job.corpus
    play_prefix = job.get_param_value('play_prefix')

    try:
        play = corpus.get_content('Play', {'prefix': play_prefix})[0]

        notes = corpus.get_content('TextualNote', {'play': play.id})
        #notes = corpus.get_content('TextualNote', {'xml_id': 'tn_70-03'})

        for note in notes:
            for variant in note.variants:
                variant.variant = perform_variant_transform(corpus, note, variant)
                variant.save()
    except:
        print(traceback.format_exc())


def get_witness_ids(
        witnesses,
        witness_groups,
        starting_witness_siglum,
        ending_witness_siglum=None,
        include_all_following=False,
        excluding_sigla=[]):
    witness_ids = []

    starting_found = False
    ending_found = False
    including_sigla = []

    for witness_group in witness_groups:
        if strip_tags(witness_group.siglum_label).lower() == starting_witness_siglum.lower():
            if not ending_witness_siglum and not include_all_following:
                # starting_witness_siglum = None
                for reffed_doc in witness_group.referenced_documents:
                    if reffed_doc.siglum_label not in excluding_sigla:
                        including_sigla.append(strip_tags(reffed_doc.siglum_label))
                break
            else:
                starting_witness_siglum = strip_tags(witness_group.referenced_documents[0].siglum_label)
        elif ending_witness_siglum and strip_tags(witness_group.siglum_label).lower() == ending_witness_siglum.lower():
            ending_witness_siglum = strip_tags(witness_group.referenced_documents[-1].siglum_label)
        elif excluding_sigla:
            original_length = len(excluding_sigla)
            for ex_index in range(0, original_length):
                if excluding_sigla[ex_index].lower() == strip_tags(witness_group.siglum_label).lower():
                    for reffed_doc in witness_group.referenced_documents:
                        excluding_sigla.append(strip_tags(reffed_doc.siglum_label))

    for witness in witnesses:
        if not starting_found and strip_tags(witness.siglum_label).lower() == starting_witness_siglum.lower():
            witness_ids.append(witness.id)
            starting_found = True
        elif starting_found and (ending_witness_siglum or include_all_following) and not ending_found:
            if strip_tags(witness.siglum_label) not in excluding_sigla:
                witness_ids.append(witness.id)

                if strip_tags(witness.siglum_label) == ending_witness_siglum:
                    ending_found = True
        elif strip_tags(witness.siglum_label) in including_sigla:
            witness_ids.append(witness.id)

    return witness_ids


def get_variant_witness_indicators(witnesses, variant):
    indicators = []
    for witness in witnesses:
        witness_found = False
        for variant_witness in variant.witnesses:
            if str(witness.id) == str(variant_witness):
                witness_found = True
                break
        indicators.append(witness_found)

    return indicators


def make_witness_meter(indicators, marker="1", references_selectively_quoted_witness=False):
    witness_meter = ""
    for witness_indicator in indicators:
        if (isinstance(witness_indicator, str) and witness_indicator == '1') or witness_indicator is True:
            witness_meter += marker
        else:
            witness_meter += "0"

    if references_selectively_quoted_witness:
        witness_meter += "1"
    else:
        witness_meter += "0"

    return witness_meter


def perform_variant_transform(corpus, note, variant):
    result = ""
    original_text = ""
    embed_pipes = False

    # Handle variants of type 'lem,' which are interpreted here to mean that
    # the witnesses associated with this variant are intended to be global
    # witness exclusions for subsequent variants (the lemma for this note
    # matches the copy-text, therefore subsequent variants should exclude
    # these witnesses.
    if variant.transform_type and variant.transform_type.strip() == 'lem':
        return None, True

    if type(note.lines[0]) is ObjectId:
        lines = corpus.get_content('PlayLine', {'id__in': note.lines}, only=['text'])
        lines = lines.order_by('line_number')
        original_text = stitch_lines(lines, embed_pipes=embed_pipes)

    elif hasattr(note.lines[0], 'text'):
        original_text = stitch_lines(note.lines, embed_pipes=embed_pipes)

    if original_text:
        ellipsis = ' .\xa0.\xa0. '
        swung_dash = ' ~ '
        under_carrot = '‸'
        double_under_carrot = '‸ ‸'

        if variant.lemma and variant.transform and variant.transform_type:
            lemma = strip_tags(variant.lemma).replace(double_under_carrot, '').replace(under_carrot, '')
            transform = strip_tags(variant.transform).replace('| ', '').replace(double_under_carrot, '').replace(under_carrot, '')

            if variant.transform_type in ["replace", "insert", "insert_before"]:
                # TODO:
                '''
                    * handle under_carrots
                    * handle transforms w/ multiple swung dashes
                    * handle transforms w/ "|" characters
                    * handle where transform_type == 'lem'
                    * handle ellipsis in lemma where multiple punctuation marks follow word, i.e.: "be?) . . . vnreall"
                    * ellipsis in lemma but not in transform
                    * description: marked as aside
                    * omission w/ ellipsis
                '''

                # replace using ellipsis and swung dash
                if variant.transform_type == "replace" and _contains(lemma, [ellipsis]) and _contains(variant.transform, [ellipsis, swung_dash]):
                    result = original_text

                    lemmas = lemma.split(ellipsis)
                    transforms = transform.split(ellipsis)

                    no_punct_lemmas = []
                    for lemma in lemmas:
                        no_punct_lemma = lemma
                        for punct in punctuation:
                            no_punct_lemma = no_punct_lemma.replace(punct, '')
                        no_punct_lemmas.append(no_punct_lemma)

                    for lemma_index in range(0, len(no_punct_lemmas)):
                        if transforms[lemma_index].count(swung_dash) > 1 and ' ' in no_punct_lemmas[lemma_index]:
                            no_punct_lemma_parts = no_punct_lemmas[lemma_index].split()
                            if len(no_punct_lemma_parts) == transforms[lemma_index].count(swung_dash):
                                for part_index in range(0, len(no_punct_lemma_parts)):
                                    transforms[lemma_index] = transforms[lemma_index].replace(swung_dash, no_punct_lemma_parts[part_index], 1)
                        else:
                            transforms[lemma_index] = transforms[lemma_index].replace(swung_dash, no_punct_lemmas[lemma_index])

                        result = result.replace(lemmas[lemma_index], transforms[lemma_index], 1)

                # replace using swung_dash only
                elif variant.transform_type == "replace" and swung_dash in variant.transform:
                    no_punct_lemma = lemma
                    for punct in punctuation:
                        no_punct_lemma = no_punct_lemma.replace(punct, '')

                    if transform.count(swung_dash) > 1 and ' ' in no_punct_lemma:
                        no_punct_lemmas = no_punct_lemma.split()
                        if len(no_punct_lemmas) == transform.count(swung_dash):
                            for lemma_index in range(0, len(no_punct_lemmas)):
                                transform = transform.replace(swung_dash, no_punct_lemmas[lemma_index], 1)
                    else:
                        transform = transform.replace(swung_dash, no_punct_lemma)

                    result = original_text.replace(lemma, transform, 1)

                # replace using ellipsis
                elif variant.transform_type == "replace" and ellipsis in lemma and ellipsis in variant.transform:
                    lemmas = lemma.split(ellipsis)
                    transforms = transform.split(ellipsis)
                    if len(lemmas) == len(transforms):
                        result = original_text
                        for lemma_index in range(0, len(lemmas)):
                            result = result.replace(lemmas[lemma_index], transforms[lemma_index], 1)

                # ellipsis in lemma only
                elif ellipsis in lemma:
                    lemma_delimiters = lemma.split(ellipsis)
                    lemma_parts = []
                    adding_lemma_parts = False
                    for word in original_text.split():
                        if strip_punct(word) == lemma_delimiters[0]:
                            lemma_parts.append(word)
                            adding_lemma_parts = True
                        elif strip_punct(word) == lemma_delimiters[1]:
                            lemma_parts.append(word)
                            break
                        elif adding_lemma_parts:
                            lemma_parts.append(word)

                    lemma = " ".join(lemma_parts)

                # replacement/insertion w/ lemma
                if not result and lemma in original_text:
                    if variant.transform_type == "replace":
                        result = original_text.replace(lemma, transform, 1)
                    # insert after lemma
                    elif variant.transform_type == "insert":
                        result = "{0} {1} {2}".format(
                            original_text[:original_text.find(lemma) + len(lemma)].strip(),
                            transform,
                            original_text[original_text.find(lemma) + len(lemma):].strip()
                        )
                    # insert before lemma
                    elif variant.transform_type == "insert_before":
                        result = "{0} {1} {2}".format(
                            original_text[:original_text.find(lemma)].strip(),
                            transform,
                            original_text[original_text.find(lemma):].strip()
                        )

        # replace line altogether
        elif not variant.lemma and variant.transform_type == 'replace' and variant.transform:
            result = strip_tags(variant.transform)

        # insertions sans lemma
        elif not variant.lemma and variant.transform and variant.transform_type == "insert":
            result = "{0} {1}".format(original_text, strip_tags(variant.transform))
        elif not variant.lemma and variant.transform and variant.transform_type == "insert_before":
            result = "{0} {1}".format(strip_tags(variant.transform), original_text)

        # simple omission
        elif variant.lemma and not variant.transform and strip_tags(variant.description).lower() == "om.":
            lemma = strip_tags(variant.lemma)

            if ellipsis in lemma:
                lemma_delimiters = lemma.split(ellipsis)
                lemma_parts = []
                adding_lemma_parts = False
                for word in original_text.split():
                    if word == lemma_delimiters[0]:
                        lemma_parts.append(word)
                        adding_lemma_parts = True
                    elif word == lemma_delimiters[1]:
                        lemma_parts.append(word)
                        break
                    elif adding_lemma_parts:
                        lemma_parts.append(word)

                lemma = " ".join(lemma_parts)
                result = original_text.replace(lemma, "")

            else:
                result = original_text.replace(lemma, "")

    if original_text and result:
        differ = difflib.Differ()
        differences = list(differ.compare(original_text, result))
        difference_started = False
        difference_cursor = None
        result = ""
        for difference in differences:
            if difference.startswith('  '):
                if difference_started:
                    if len(result) == difference_cursor:
                        result += "&nbsp;"
                    result += "</span>"
                    difference_started = False

                result += difference[2:]
            else:
                if not difference_started:
                    result += "<span class='difference'>"
                    difference_started = True
                    difference_cursor = len(result)

                if difference.startswith('- '):
                    pass
                elif difference.startswith('+ '):
                    result += difference[2:]

        if difference_started:
            result += "</span>"

    if not result:
        return None, False

    return result, False


def parse_bibliography(corpus, play, bibliography_file_path):
    report = '''
##########################################################
BIBLIOGRAPHY INGESTION
##########################################################\n'''

    with open(bibliography_file_path, 'r') as tei_in:
        tei_text = tei_in.read()
        text_replacements = extract_text_replacements(tei_in)

        for text, replacement in text_replacements.items():
            tei_text = tei_text.replace(text, replacement)

        bib_tei = BeautifulSoup(tei_text, "xml")

    play.bibliographic_sources = []
    unhandled = []
    doc_count = 0
    bibls = bib_tei.div.listBibl.find_all('bibl', recursive=False)

    for bibl in bibls:
        doc, bibliographic_entry = handle_bibl_tag(corpus, bibl, unhandled)
        if doc and bibliographic_entry:
            doc_count += 1

            reference = corpus.get_content("Reference")
            reference.play = play.id
            reference.document = doc.id
            reference.ref_type = 'bibliographic_source'
            reference.bibliographic_entry = bibliographic_entry
            reference.bibliographic_entry_text = strip_tags(bibliographic_entry).strip()
            reference.save()
            # play.bibliographic_sources.append(doc.id)
        else:
            report += "Error creating bibliographic entry for this TEI representation:\n{0}\n\n".format(str(bibl).replace('<', '&lt;').replace('>', '&gt;'))

    unhandled = list(set(unhandled))
    if unhandled:
        report += "The following tags were not properly converted from TEI to HTML: {0}\n\n".format(', '.join(unhandled))

    report += "{0} bibliographic entries created.\n\n".format(doc_count)
    del bib_tei
    return report


def handle_bibl_tag(corpus, bibl, unhandled, xml_id=None, date='', siglum_label=''):
    doc = None
    doc_data = {
        'siglum_label': '',
        'author': '',
        'bibliographic_entry': '',
        'title': '',
        'pub_date': date,
        'editor': '',
        'publisher': '',
        'place': '',
        'unhandled': []
    }

    if xml_id or 'xml:id' in bibl.attrs:
        siglum = xml_id
        if not siglum:
            siglum = bibl['xml:id']

        doc = corpus.get_content('Document', {'siglum': siglum}, single_result=True)
        if not doc:
            doc = corpus.get_content('Document')
            doc.siglum = siglum

        doc_data['siglum_label'] = siglum_label if siglum_label else siglum

        for child in bibl.children:
            extract_bibl_components(child, doc_data)

        for key in doc_data.keys():
            if hasattr(doc, key) and key != 'bibliographic_entry' and doc_data[key]:
                setattr(doc, key, doc_data[key])

        #if doc.bibliographic_entry:
        #    doc.bibliographic_entry_text = strip_tags(doc.bibliographic_entry).strip()

        if doc_data['unhandled']:
            unhandled.extend(doc_data['unhandled'])

        doc.save()

    return doc, doc_data['bibliographic_entry']


def extract_bibl_components(element, doc_data, inside_note=False):
    if element.name:
        open = ""
        close = ""
        tag = "span"
        classes = [element.name]
        for attr, val in element.attrs.items():
            if attr not in ['xml', 'target', 'targType']:
                classes.append(attr + "_" + slugify(val))

        if element.name == 'author':
            if doc_data['author']:
                doc_data['author'] += ", "
            doc_data['author'] += element.text
            # doc_data['bibliographic_entry'] += author

        elif element.name == 'editor':
            if doc_data['editor']:
                doc_data['editor'] += ", "
            doc_data['editor'] += element.text

        elif element.name == 'title':
            if not doc_data['title'] and not inside_note:
                doc_data['title'] = element.text

        elif element.name == 'date':
            if not doc_data['pub_date']:
                doc_data['pub_date'] = element.text

        elif element.name == 'pubPlace':
            doc_data['place'] = element.text

        elif element.name == 'publisher':
            doc_data['publisher'] = element.text

        elif element.name in ['note', 'bibl']:
            inside_note = True
            if element.name == 'bibl':
                classes.remove('bibl')
                classes.append('inline-bibl')

        elif element.name == 'ref' and _contains(element.attrs, ['targType', 'target']):
            open = '''<a ref="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">'''.format(
                element['targType'],
                element['target']
            )
            close = "</a>"

        if not open:
            open = '<{0} class="{1}">'.format(
                tag,
                " ".join(classes)
            )
            close = "</{0}>".format(tag)

        doc_data['bibliographic_entry'] += open
        for child in element.children:
            extract_bibl_components(child, doc_data, inside_note)
        doc_data['bibliographic_entry'] += close

    else:
        doc_data['bibliographic_entry'] += str(element)


def handle_bibl_title(tag, toggle_italics=False):
    html = ""
    title_type = tag['level']
    title_open = None
    title_close = None

    if title_type == 'm' and not toggle_italics:
        title_open = "<i>"
        title_close = "</i>"
    elif title_type == 'a':
        title_open = '"'
        title_close = '"'
    elif title_type in ['s', 'j'] or toggle_italics:
        title_open = ""
        title_close = ""

    if None not in [title_open, title_close]:
        html += title_open

        for child in tag.children:
            if child.name and child.name == 'title':
                html += handle_bibl_title(child, not toggle_italics if title_type == 'm' else toggle_italics)
            elif child.name:
                html += str(child.string)
            else:
                html += str(child)

        html += title_close

    return html


def parse_commentary(corpus, play, commentary_file_path, line_id_map, ordered_line_ids):
    report = '''
##########################################################
COMMENTARY NOTE INGESTION
##########################################################\n'''

    try:
        # open commentary xml, read raw text into tei_text,
        # and perform special text replacements before feeding
        # into BeautifulSoup
        with open(commentary_file_path, 'r') as tei_in:
            tei_text = tei_in.read()
            text_replacements = extract_text_replacements(tei_in)

            for text, replacement in text_replacements.items():
                tei_text = tei_text.replace(text, replacement)

            comm_tei = BeautifulSoup(tei_text, "xml")

        note_tags = comm_tei.find_all('note', attrs={'type': 'commentary'})
        unhandled = []

        primary_witnesses = corpus.get_content("Reference", {'play': play.id, 'ref_type': 'primary_witness'}).order_by('+id')
        pw_sigla = [pw.document.siglum for pw in primary_witnesses]

        for note_tag in note_tags:
            note = corpus.get_content('Commentary')
            note.play = play.id
            note.xml_id = note_tag['xml:id']

            note.lines, line_err_msg = get_line_ids(
                note_tag['target'],
                note_tag.attrs.get('targetEnd', None),
                line_id_map,
                ordered_line_ids
            )
            if len(note.lines) < 1 or line_err_msg:
                report += "Error finding lines for commentary note w/ XML ID {0}: {1}\n\n".format(note.xml_id, line_err_msg)


            note.contents = ""
            note_data = {
                'wit_xml_ids': pw_sigla
            }

            for child in note_tag.children:
                note.contents += handle_commentary_tag(child, note_data)

            if _contains(note_data, ['line_label', 'subject_matter']):
                note.line_label = note_data['line_label']
                note.subject_matter = note_data['subject_matter']
                note.save()

                # build lemma span for line html
                try:
                    report += mark_commentary_lemma(corpus, play, note)
                except:
                    report += "An error prevented marking lemma for note {0}: {1}\n\n".format(
                        note.xml_id,
                        traceback.format_exc()
                    )

            else:
                report += "Commentary note {0} missing label or lemma\n\n".format(note.xml_id)

            if 'unhandled' in note_data:
                unhandled.extend(note_data['unhandled'])

        if unhandled:
            unhandled = list(set(unhandled))
            report += "The following TEI tags were not properly converted to HTML: {0}\n\n".format(
                ', '.join(unhandled)
            )

    except:
        report += "An error prevented full ingestion of commentary notes: {0}\n\n".format(traceback.format_exc())

    del comm_tei
    return report


def handle_commentary_tag(tag, data={}):
    html = ""

    if tag.name:

        if tag.name == 'label':
            data['line_label'] = _str(tag)

        elif tag.name == 'lem':
            data['subject_matter'] = "".join([handle_commentary_tag(child, data) for child in tag.children])

        elif tag.name == 'ref' and _contains(tag.attrs, ['targType', 'target']):
            targ_type = tag['targType']
            xml_id = tag['target'].replace('#', '').strip()

            if targ_type == 'lb' and 'targetEnd' in tag.attrs:
                xml_id += ' ' + tag['targetEnd'].replace("#", '').strip()

            if targ_type == 'bibl':
                if xml_id in data['wit_xml_ids']:
                    targ_type = 'siglum'

            html += '''<a href="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">'''.format(
                targ_type,
                xml_id
            )
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += "</a>"

        elif tag.name == "name":
            html += '''<span class="name">'''
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += '''</span>'''

        elif tag.name == "title" and tag['level'] == 'm':
            if 'italics_level' not in data:
                data['title_level'] = 0

            if data['title_level'] % 2 == 0:
                html += "<i>"

            data['title_level'] += 1

            html += "".join([handle_commentary_tag(child, data) for child in tag.children])

            data['title_level'] -= 1

            if data['title_level'] % 2 == 0:
                html += "</i>"

        elif tag.name == "quote":
            html += '''<q>'''
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += '''</q>'''

        elif tag.name == "p":
            html += '''<p>'''
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += '''</p>'''

        elif tag.name == 'hi':
            if tag['rend'] == 'italic':
                html += '''<i>'''
                html += "".join([handle_commentary_tag(child, data) for child in tag.children])
                html += '''</i>'''

            elif tag['rend'] == 'superscript':
                html += '''<sup>'''
                html += "".join([handle_commentary_tag(child, data) for child in tag.children])
                html += '''</sup>'''

            elif tag['rend'] == 'smcaps':
                html += '''<span style="font-variant: small-caps;">'''
                html += "".join([handle_commentary_tag(child, data) for child in tag.children])
                html += '''</span>'''

        elif tag.name == 'ptr' and _contains(tag.attrs, ['targType', 'target']):
            target = tag['target'].replace('#', '')
            if 'targetEnd' in tag.attrs:
                target += " " + tag['targetEnd']

            html += '''<a href="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">here</a>'''.format(
                tag['targType'],
                target
            )

        elif tag.name == 'siglum':
            siglum_label = "".join([handle_commentary_tag(child, data) for child in tag.children])
            if 'rend' in tag.attrs and tag['rend'] == 'smcaps':
                siglum_label = '''<span style="font-variant: small-caps;">{0}</span>'''.format(siglum_label)

            html += '''<a href="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">'''.format(
                'siglum',
                strip_tags(siglum_label)
            )
            html += siglum_label
            html += "</a>"

        elif tag.name == 'list':
            if 'xml:id' in tag.attrs:
                html += '''<ul id="{0}">'''.format(tag['xml:id'])
            else:
                html += '''<ul>'''

            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += "</ul>"

        elif tag.name == 'item':
            html += '''<li>'''
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += '''</li>'''

        elif tag.name == 'foreign':
            html += '''<i>'''
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += '''</i>'''

        elif tag.name == 'title':
            html_tag = "i"
            if 'level' in tag.attrs and tag.attrs['level'] == 'a':
                html_tag = "q"

            html += '''<{0}>'''.format(html_tag)
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += '''</{0}>'''.format(html_tag)

        elif tag.name == 'lemNote':
            html += '''<span class="lemma-note">'''
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += '''</span>'''

        # tags to ignore
        elif tag.name in ['rs']:
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])

        else:
            if 'unhandled' not in data:
                data['unhandled'] = []

            data['unhandled'].append(tag.name)

    else:
        html = html_lib.escape(str(tag))

        if html.strip() == ']' and 'lem_bracket_found' not in data:
            html = ""
            data['lem_bracket_found'] = True

    return html


def mark_commentary_lemma(corpus, play, note):
    report = ""
    note.reload()
    lemma_string = note.subject_matter
    if '<span class="lemma-note">' in lemma_string:
        lemma_string = lemma_string[:lemma_string.index('<span class="lemma-note">')]
    lemma_string = strip_tags(lemma_string).strip()

    all_words = ""
    char_index_map = {}
    char_cursor = 0

    line_groups = []
    lemmas = []
    current_line_group = []

    for line_index in range(0, len(note.lines)):
        this_line = note.lines[line_index]
        prev_line = None

        if line_index > 0:
            prev_line = note.lines[line_index - 1]

        if not prev_line or this_line.line_number - prev_line.line_number == 1:
            current_line_group.append(this_line)
        else:
            line_groups.append(current_line_group)
            current_line_group = [this_line]

    if current_line_group:
        line_groups.append(current_line_group)

    if len(line_groups) > 1:
        lemmas = [l.strip() for l in lemma_string.split(',') if l]
        if len(line_groups) != len(lemmas):
            return "Error building line groups and lemmas for commentary note {0} w/ lemma [{1}]\n".format(note.xml_id, lemma_string)

    else:
        lemmas.append(lemma_string)

    for group_index in range(0, len(line_groups)):
        lines = line_groups[group_index]
        lemma = lemmas[group_index]

        for line in lines:
            line_char_index = 0
            word_broken = False

            for char in line.text:
                if char == '\xad':
                    word_broken = True
                else:
                    all_words += char
                    char_index_map[char_cursor] = make_text_location(line.line_number, line_char_index)
                    line_char_index += 1
                    char_cursor += 1

            if not word_broken:
                all_words += ' '
                char_index_map[char_cursor] = make_text_location(line.line_number, line_char_index)
                char_cursor += 1

        starting_location = None
        ending_location = None

        ellipsis = ' .\xa0.\xa0. '
        if ellipsis in lemma:
            start_and_end = lemma.split(ellipsis)
            starting_char_index = all_words.find(start_and_end[0])

            if starting_char_index > -1:
                starting_location = char_index_map[starting_char_index]

                ending_char_index = all_words.rfind(start_and_end[1])
                if ending_char_index > -1 and ending_char_index + len(start_and_end[1]) in char_index_map:
                    ending_location = char_index_map[ending_char_index + len(start_and_end[1])]

        else:
            starting_char_index = all_words.find(lemma)
            if starting_char_index > -1 and starting_char_index + len(lemma) in char_index_map:
                starting_location = char_index_map[starting_char_index]
                ending_location = char_index_map[starting_char_index + len(lemma)]

        if starting_location is not None and ending_location is not None:
            lemma_span = corpus.get_content('PlayTag')
            lemma_span.play = play.id
            lemma_span.name = 'comspan'
            lemma_span.classes = "commentary-lemma-{0}".format(slugify(note.xml_id))
            lemma_span.start_location = starting_location
            lemma_span.end_location = ending_location
            lemma_span.save()

        else:
            report += "-----------------------------------------------\n"
            report += "Lemma not found for note {0} w/ lemma [{1}]\n".format(note.xml_id, lemma)
            report += "Text from play line(s): {0}\n".format(all_words)
            report += "-----------------------------------------------\n\n"

    return report


def parse_appendix(corpus, play, repo_name, appendix_file_path):
    report = '''
##########################################################
APPENDIX INGESTION
##########################################################\n'''

    try:
        # open xml, read raw text into tei_text,
        # and perform special text replacements before feeding
        # into BeautifulSoup
        with open(appendix_file_path, 'r') as tei_in:
            tei_text = tei_in.read()
            text_replacements = extract_text_replacements(tei_in)

            for text, replacement in text_replacements.items():
                tei_text = tei_text.replace(text, replacement)

            app_tei = BeautifulSoup(tei_text, "xml")

        unhandled = []
        unhandled += create_appendix_divs(corpus, play, repo_name, app_tei, None, 1)
        unhandled = list(set(unhandled))
        if unhandled:
            report += "The following TEI tags were not properly converted to HTML: {0}\n\n".format(
                ', '.join(unhandled)
            )

    except:
        report += "An error prevented full ingestion of the appendix:\n{0}\n\n".format(
            traceback.format_exc()
        )

    del app_tei
    return report


def create_appendix_divs(corpus, play, repo_name, container, parent, level):
    level_attr = "level" + str(level)
    divs = container.findAll('div', type=level_attr)
    level_counter = 0
    unhandled = []
    for div in divs:
        level_counter += 1
        pt = corpus.get_content('ParaText')
        pt.xml_id = div['xml:id']
        pt.section = "Appendix"
        pt.order = level_counter
        pt.level = level
        pt.html_content = ""
        if parent:
            pt.parent = parent.id
        pt.play = play.id

        pt_data = {
            'current_note': None,
            'unhandled': [],
            'corpus': corpus,
            'repo_name': repo_name
        }

        for child in div.children:
            pt.html_content += handle_paratext_tag(child, pt, pt_data)

        unhandled += list(set(pt_data['unhandled']))

        pt.save()

        unhandled += list(set(create_appendix_divs(corpus, play, repo_name, div, pt, level + 1)))

    return unhandled


def handle_paratext_tag(tag, pt, pt_data):
    html = ""

    simple_conversions = {
        'p': 'p',
        'hi': 'span',
        'title': 'i',
        'quote': 'q',
        'table': 'table',
        'row': 'tr',
        'cell': 'td',
        'list': 'ul',
        'item': 'li',
        'front': 'div:front',
        'floatingText': 'div:floating-text',
        'titlePage': 'span:title-page',
        'docTitle': 'span:doc-title',
        'figDesc': 'p',
        'docImprint': 'p:doc-imprint',
        'byline': 'p:byline',
        'docAuthor': 'span:doc-author',
        'lb': 'br',
        'div': 'div',
        'signed': 'div:signed',
        'lg': 'i:mt-2',
        'l': 'div',
        'milestone': 'div:milestone',
        'sp': 'div:speech',
        'speaker': 'span:speaker',
        'trailer': 'div:trailer',
        'label': 'b:label',
        'figure': 'div:figure',
        'salute': 'span:salute',
        'abbr': 'dt:abbr',
        'expan': 'dd:expan',
        'listBibl': 'div:bibl-list',
        'bibl': 'span:bibl',
        'listWit': 'div:witness-list',
        'witness': 'span:witness',
        'edition': 'q:edition',
        'date': 'span:date',
        'docDate': 'span:doc-date',
        'stage': 'span:stage',
    }

    silent = [
        'app', 'appPart', 'lem', 'wit', 'rdgDesc',
        'rdg', 'rs', 'epigraph',
        'body', 'foreign', 'cit',
    ]

    if tag.name:
        attributes = ""
        classes = []
        if 'xml:id' in tag.attrs:
            pt.child_xml_ids.append(tag['xml:id'])
            attributes += " id='{0}'".format(tag['xml:id'])
        if 'rend' in tag.attrs:
            classes += get_attr_classes('rend', tag['rend'])
        if 'display' in tag.attrs:
            classes += get_attr_classes('display', tag['display'])
        if 'type' in tag.attrs:
            classes += get_attr_classes('type', tag['type'])

        if tag.name == 'head':
            if not pt.title:
                pt_title = ""
                for child in tag.children:
                    pt_title += handle_paratext_tag(child, pt, pt_data)
                pt.title = pt_title

            else:
                if classes:
                    attributes += ' class="{0}"'.format(
                        " ".join(classes)
                    )

                h_level = pt.level + 1
                if h_level > 5:
                    h_level = 5
                html += "<h{0}{1}>".format(h_level, attributes)
                for child in tag.children:
                    html += handle_paratext_tag(child, pt, pt_data)
                html += "</h2>"

        elif tag.name == 'titlePart':
            html_tag = 'h3'

            if classes:
                attributes += ' class="{0}"'.format(
                    " ".join(classes)
                )

            html += "<{0}{1}>".format(html_tag, attributes)
            for child in tag.children:
                html += handle_paratext_tag(child, pt, pt_data)
            html += "</{0}>".format(html_tag)

        # ignore any <div type="levelX"> tags...
        elif tag.name == "div" and 'type' in tag.attrs and tag['type'].startswith("level"):
            pass

        elif tag.name == 'witness' and _contains(tag.attrs, ['corresp', 'xml:id', 'display']) and tag.attrs['display'] == 'book(suppress)':
            pass

        elif tag.name == 'siglum':
            siglum_label = "".join([handle_paratext_tag(child, pt, pt_data) for child in tag.children])
            if 'rend' in tag.attrs and tag['rend'] == 'smcaps':
                siglum_label = '''<span style="font-variant: small-caps;">{0}</span>'''.format(siglum_label)

            html += '''<a href="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">'''.format(
                'siglum',
                strip_tags(siglum_label)
            )
            html += siglum_label
            html += "</a>"

        elif tag.name == 'ptr' and _contains(tag.attrs, ['targType', 'target']):
            target = tag['target'].replace('#', '')
            if 'targetEnd' in tag.attrs:
                target += " " + tag['targetEnd']
            html += '''<a href="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">here</a>'''.format(
                tag['targType'],
                target
            )

        elif tag.name == 'ref' and _contains(tag.attrs, ['targType', 'target']):
            targ_type = tag['targType']
            xml_id = tag['target'].replace('#', '').strip()

            if targ_type == 'lb' and 'targetEnd' in tag.attrs:
                xml_id += ' ' + tag['targetEnd'].replace("#", '').strip()

            html += '''<a href="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">'''.format(
                targ_type,
                xml_id
            )
            html += "".join([handle_paratext_tag(child, pt, pt_data) for child in tag.children])
            html += "</a>"

        elif tag.name == 'note':
            curr_note = {
                'xml_id': '',
                'target_tln': ''
            }

            if 'target' in tag.attrs:
                curr_note['target_tln'] = tag['target'].replace('#', '')

            pt_data['current_note'] = curr_note

            if 'type' in tag.attrs and tag.attrs['type'] in ['textual', 'irregular', 'unadopted']:
                classes.append('pt_textual_note')

            if classes:
                attributes += ' class="{0}"'.format(
                    " ".join(classes)
                )

            html += "<div{0}>".format(attributes)
            for child in tag.children:
                html += handle_paratext_tag(child, pt, pt_data)
            html += "</div>"
            pt_data['current_note'] = None

        elif tag.name == "label" and pt_data['current_note']:
            html += '''<a href="#" class="ref-lb" onClick="navigate_to('lb', '{0}', this); return false;">'''.format(
                pt_data['current_note']['target_tln']
            )
            for child in tag.children:
                html += handle_paratext_tag(child, pt, pt_data)
            html += "</a>"

        elif tag.name == "quote" and 'rend' in tag and tag['rend'] == 'block':
            if classes:
                attributes += ' class="{0}"'.format(
                    " ".join(classes)
                )

            html += "<blockquote{0}>".format(attributes)
            for child in tag.children:
                html += handle_paratext_tag(child, pt, pt_data)
            html += "</blockquote>"

        elif tag.name == "anchor" and 'xml:id' in tag.attrs:
            html += "<a name='{0}' class='anchor'></a>".format(tag['xml:id'])

        elif tag.name == "closer":
            if classes:
                attributes += ' class="{0}"'.format(
                    " ".join(classes)
                )

            html += '''
                <div class="row">
                    <div{0} class="col-sm-6 offset-sm-6">
            '''.format(attributes)
            for child in tag.children:
                html += handle_paratext_tag(child, pt, pt_data)
            html += "</div></div>"

        elif tag.name == "space" and 'extent' in tag.attrs:
            unit = tag['extent'].replace("indent(", '').replace(")", '')
            html += '<span style="margin-left: {0};">'.format(unit)
            for child in tag.children:
                html += handle_paratext_tag(child, pt, pt_data)
            html += '</span>'

        elif tag.name == "graphic" and 'url' in tag.attrs:
            img_path = tag['url']
            if classes:
                attributes += ' class="{0}"'.format(
                    " ".join(classes)
                )

            html += "<img{0} data-repo-name='{1}' data-path='{2}' class='graphic' />".format(
                attributes,
                pt_data['repo_name'],
                img_path
            )

        elif tag.name == "name":
            classes.append("name")

            attributes += ' class="{0}"'.format(
                " ".join(classes)
            )

            html += '<span{0}>'.format(attributes)
            for child in tag.children:
                html += handle_paratext_tag(child, pt, pt_data)
            html += '</span>'

        # tags to ignore (but keep content inside)
        elif tag.name in silent:
            for child in tag.children:
                html += handle_paratext_tag(child, pt, pt_data)

        # tags with simple conversions (tei tag w/ html equivalent)
        elif tag.name in simple_conversions:
            html_tag = simple_conversions[tag.name]
            if ':' in html_tag:
                html_tag = html_tag.split(':')[0]
                classes.append(simple_conversions[tag.name].split(':')[1])

            if classes:
                attributes += ' class="{0}"'.format(
                    " ".join(classes)
                )

            html += "<{0}{1}>".format(
                html_tag,
                attributes
            )
            for child in tag.children:
                html += handle_paratext_tag(child, pt, pt_data)
            html += "</{0}>".format(html_tag)

        else:
            pt_data['unhandled'].append(tag.name)

    else:
        html = html_lib.escape(str(tag))

    return html


def get_attr_classes(attr, rend):
    return ["{0}-{1}".format(attr, slugify(r)) for r in rend.split() if r]


def get_line_ids(xml_id_start, xml_id_end, line_id_map, ordered_line_ids):
    line_ids = []
    err_msg = ""

    if xml_id_start and xml_id_end and len(xml_id_start.split()) == len(xml_id_end.split()):
        starts = xml_id_start.split()
        ends = xml_id_end.split()

        for pair_index in range(0, len(starts)):
            start_xml_id = starts[pair_index].replace('#', '')
            end_xml_id = ends[pair_index].replace('#', '')
            if _contains(line_id_map, [start_xml_id, end_xml_id]) and line_id_map[start_xml_id] and line_id_map[end_xml_id]:
                start_id_index = ordered_line_ids.index(line_id_map[start_xml_id][0])
                end_id_index = ordered_line_ids.index(line_id_map[end_xml_id][-1])

                if start_id_index < end_id_index:
                    line_ids += ordered_line_ids[start_id_index:end_id_index + 1]
            else:
                err_msg += "Lines with XML IDs {0} and/or {1} not found!".format(start_xml_id, end_xml_id)

    elif xml_id_start:
        xml_ids = xml_id_start.replace('#', '').split()

        if xml_id_end:
            xml_ids += xml_id_end.replace('#', '').split()

        for xml_id in xml_ids:
            if xml_id in line_id_map:
                for line_id in line_id_map[xml_id]:
                    if line_id not in line_ids:
                        line_ids.append(line_id)
            else:
                err_msg += "Line with XML ID {0} not found! ".format(xml_id)

    return line_ids, err_msg


def stitch_lines(lines, embed_line_markers=False, embed_pipes=False):
    stitched = ""
    marker = ""

    for line in lines:
        if embed_line_markers:
            marker = "<{0} />".format(line.xml_id)
        elif embed_pipes:
            marker = " | "

        if not stitched:
            stitched += marker + line.text
        elif stitched.endswith('\xad'):
            stitched = stitched[:-1] + marker + line.text
        elif stitched.endswith('-'):
            stitched += marker + line.text
        else:
            stitched += ' ' + marker + line.text

    return stitched


def extract_text_replacements(file):
    file.seek(0)
    pattern = re.compile(r'<!ENTITY ([^ ]*)\s*"([^"]*)"')
    text_replacements = {}

    for line in file:
        if line.strip() == ']>':
            break
        else:
            matches = pattern.findall(line)
            if matches:
                text = matches[0][0]
                replacement = matches[0][1]

                if text not in text_replacements:
                    text_replacements['&' + text + ';'] = replacement

    print("TEXT REPLACEMENTS")
    print(text_replacements)
    return text_replacements


def _str(val):
    if val and hasattr(val, 'string') and val.string:
        val = str(val.string)
        return val
    return ''


def strip_punct(text):
    stripped = text
    for punct in punctuation:
        stripped = stripped.replace(punct, '')
    return stripped


def tei_to_html(tag):
    html = ""

    simple_conversions = {
        'p': 'p',
        'hi': 'span',
        'title': 'i',
        'head': 'h3:heading',
        'quote': 'q',
        'table': 'table',
        'row': 'tr',
        'cell': 'td',
        'list': 'ul',
        'item': 'li',
        'front': 'div:front',
        'floatingText': 'div:floating-text',
        'titlePage': 'span:title-page',
        'docTitle': 'span:doc-title',
        'figDesc': 'p',
        'docImprint': 'p:doc-imprint',
        'byline': 'p:byline',
        'docAuthor': 'span:doc-author',
        'lb': 'br',
        'div': 'div',
        'signed': 'div:signed',
        'lg': 'i:mt-2',
        'l': 'div',
        'milestone': 'div:milestone',
        'sp': 'div:speech',
        'speaker': 'span:speaker',
        'trailer': 'div:trailer',
        'label': 'b:label',
        'figure': 'div:figure',
        'salute': 'span:salute',
        'abbr': 'dt:abbr',
        'expan': 'dd:expan',
        'listBibl': 'div:bibl-list',
        'bibl': 'span:bibl',
        'listWit': 'div:witness-list',
        'witness': 'span:witness',
        'edition': 'q:edition',
        'date': 'span:date',
        'docDate': 'span:doc-date',
        'stage': 'span:stage',
    }

    silent = [
        'app', 'appPart', 'lem', 'wit', 'rdgDesc',
        'rdg', 'name', 'rs', 'epigraph',
        'body', 'foreign', 'cit',
        'closer'
    ]

    if tag.name:
        if tag.name in silent:
            for child in tag.children:
                html += tei_to_html(child)
        else:
            attributes = ""
            classes = []
            if 'xml:id' in tag.attrs:
                attributes += " id='{0}'".format(tag['xml:id'])
            if 'rend' in tag.attrs:
                classes += get_attr_classes('rend', tag['rend'])

            if tag.name == 'lb' and attributes:
                html += '<br /><span{0}>&nbsp;</span>'

            elif tag.name == 'space' and 'extent' in tag.attrs:
                space_size = tag['extent']
                if 'indent(' in space_size and ')' in space_size:
                    space_size = space_size.replace('indent(', '').replace(')', '')
                html += '<span style="width: {0}; display: inline-block;">&nbsp;</span>'.format(space_size)

            elif tag.name == 'siglum':
                siglum_label = "".join([tei_to_html(child) for child in tag.children])
                if 'rend' in tag.attrs and tag['rend'] == 'smcaps':
                    siglum_label = '''<span style="font-variant: small-caps;">{0}</span>'''.format(siglum_label)

                html += '''<a href="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">'''.format(
                    'siglum',
                    strip_tags(siglum_label).replace(';', '')
                )
                html += siglum_label
                html += "</a>"

            elif tag.name == 'ptr' and _contains(tag.attrs, ['targType', 'target']):
                target = tag['target'].replace('#', '')
                if 'targetEnd' in tag.attrs:
                    target += " " + tag['targetEnd']
                html += '''<a href="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">here</a>'''.format(
                    tag['targType'],
                    target
                )

            elif tag.name == 'ref' and _contains(tag.attrs, ['targType', 'target']):
                targ_type = tag['targType']
                xml_id = tag['target'].replace('#', '').strip()

                if targ_type == 'lb' and 'targetEnd' in tag.attrs:
                    xml_id += ' ' + tag['targetEnd'].replace("#", '').strip()

                html += '''<a href="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">'''.format(
                    targ_type,
                    xml_id
                )
                html += "".join([tei_to_html(child) for child in tag.children])
                html += "</a>"

            elif tag.name in simple_conversions:
                html_tag = simple_conversions[tag.name]
                if ':' in html_tag:
                    html_tag = html_tag.split(':')[0]
                    classes.append(simple_conversions[tag.name].split(':')[1])

                if classes:
                    attributes += ' class="{0}"'.format(
                        " ".join(classes)
                    )

                html += "<{0}{1}>".format(
                    html_tag,
                    attributes
                )
                for child in tag.children:
                    html += tei_to_html(child)
                html += "</{0}>".format(html_tag)

            # tags to ignore (but keep content inside)
            elif tag.name in silent:
                for child in tag.children:
                    html += tei_to_html(child)

    else:
        html += str(tag)

    return html


def register_person(name):
    '''
    pip install viapy
    from viapy.api import ViafAPI
    api = ViafAPI()
    p = api.find_person("Bryan Tarpley")
    for pers in p:
        print(pers.label)
    '''
    return "<span class='name'>{0}</span>".format(name)


def register_anchor(anchor):
    return "<a name='{0}'></a>".format(anchor)


def reference_document(label, doc_type):
    return "<span class='{0}'>{1}</span>".format(doc_type, label)


def process_link(reffed, pointer=False):
    link_type = None
    target = None
    text = None

    if pointer:
        match = re.match(r'<ptr targType="([^"]*)" target="#([^"]*)"\/>', reffed)
        if match:
            link_type = match.group(1)
            target = match.group(2)
            text = "here"
    else:
        match = re.match(r'<ref targType="([^"]*)" target="([^"]*)">(.*?)<\/ref>', reffed, flags=re.S)
        if match:
            link_type = match.group(1)
            target = match.group(2)
            text = match.group(3)

    if link_type and target and text:
        return '''<a ref="#" class="ref-{0}" onClick="navigate_to('{0}', '{1}', this); return false;">{2}</a>'''.format(
            link_type,
            target,
            text
        )
    else:
        return reffed


def render_lines_html(corpus, play, starting_line_no=None, ending_line_no=None):
    lines = corpus.get_content('PlayLine', {'play': play.id}, exclude=['play'])
    tags = corpus.get_content('PlayTag', {'play': play.id}, exclude=['play'])

    if not starting_line_no is None:
        lines = lines.filter(Q(line_number__gte=starting_line_no) & Q(line_number__lte=ending_line_no))
        tags = tags.filter(
            (
                (Q(start_location__gte=starting_line_no) & Q(start_location__lte=ending_line_no)) |
                (Q(end_location__gte=starting_line_no) & Q(end_location__lte=ending_line_no))
            ) |
            (
                Q(start_location__lt=starting_line_no) &
                Q(end_location__gt=ending_line_no)
            )
        )

    lines = lines.order_by('line_number')
    tags = tags.order_by('+start_location', '-end_location')

    taggings = {}
    for tag in tags:
        if tag.start_location not in taggings:
            taggings[tag.start_location] = {'open': [], 'close': []}
        if tag.end_location not in taggings:
            taggings[tag.end_location] = {'open': [], 'close': []}

        open_html = tag.label.replace('[', '<').replace(']', '>')
        close_html = "</{0}>".format(open_html[1:open_html.index(" ")])

        if tag.start_location == tag.end_location:
            if 'empty' not in taggings[tag.start_location]:
                taggings[tag.start_location]['empty'] = []
            taggings[tag.start_location]['empty'].append({
                'html': open_html + close_html,
                'id': str(tag.id)
            })

        else:
            taggings[tag.start_location]['open'].append({
                'html': open_html,
                'id': str(tag.id)
            })
            taggings[tag.end_location]['close'].insert(0, {
                'html': close_html,
                'id': str(tag.id)
            })

    del tags
    open_tags = []

    for line in lines:
        line.rendered_html = ""

        for tag in open_tags:
            line.rendered_html += tag['html']

        for char_index in range(0, len(line.text)):
            location = make_text_location(line.line_number, char_index)
            place_tags(location, line, taggings, open_tags)

            char = line.text[char_index]
            if char == '\xad':
                char = '-'
            line.rendered_html += char

        location = make_text_location(line.line_number, len(line.text))
        place_tags(location, line, taggings, open_tags)

        for open_tag in reversed(open_tags):
            close_html = "</{0}>".format(open_tag['html'][1:open_tag['html'].index(" ")])
            line.rendered_html += close_html

        line.save(do_linking=False)
    del lines
    taggings.clear()


def place_tags(location, line, taggings, open_tags):
    if location in taggings:
        for closing_tag in taggings[location]['close']:
            line.rendered_html += closing_tag['html']
            remove_tag_index = -1
            for tag_index in range(0, len(open_tags)):
                if open_tags[tag_index]['id'] == closing_tag['id']:
                    remove_tag_index = tag_index
                    break
            if remove_tag_index > -1:
                open_tags.pop(remove_tag_index)

        for opening_tag in taggings[location]['open']:
            line.rendered_html += opening_tag['html']
            open_tags.append(opening_tag)

        if 'empty' in taggings[location]:
            for empty_tag in taggings[location]['empty']:
                line.rendered_html += empty_tag['html']


def time_it(timer_name, stop=False):
    if timer_name not in job_timers:
        job_timers[timer_name] = {
            'start': None,
            'total': 0
        }

    if not stop:
        job_timers[timer_name]['start'] = timer()
    elif job_timers[timer_name]['start']:
        job_timers[timer_name]['total'] += timer() - job_timers[timer_name]['start']
        job_timers[timer_name]['start'] = None
