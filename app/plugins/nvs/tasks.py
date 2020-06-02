import os
import re
import difflib
from .content import REGISTRY as NVS_CONTENT_TYPE_SCHEMA
from plugins.document.content import REGISTRY as DOCUMENT_REGISTRY
from corpus import *
from manager.tasks import run_job
from manager.utilities import _contains, parse_uri
from bs4 import BeautifulSoup
from django.utils.html import strip_tags
from string import punctuation

REGISTRY = {
    "Import NVS Data from TEI": {
        "version": "0.2",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "driver_file": {
                    "value": "",
                    "type": "corpus_file",
                    "label": "Edition Driver File",
                    "note": "Likely named [prefix]_driver.xml"
                },
                "basetext_siglum": {
                    "value": "",
                    "type": "text",
                    "label": "Basetext Siglum",
                    "note": "Likely \"s_f1\" (First Folio)"
                },
                "delete_existing": {
                    "value": "No",
                    "type": "choice",
                    "choices": ["No", "Yes"],
                    "label": "Delete existing content?",
                    "note": "Selecting 'Yes' will first delete all relevant content before importing!"
                }
            },
        },
        "module": 'plugins.nvs.tasks',
        "functions": ['import_data']
    },
    "Perform Textual Note Transforms": {
        "version": "0.1",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {}
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
        "in_lists": False
    },
    {
        "name": "nvs_doc_type",
        "label": "Document Type",
        "type": "keyword",
        "in_lists": True
    },
]

text_replacements = {}

def import_data(job_id):
    job = Job(job_id)
    corpus = job.corpus
    driver_file_key = job.configuration['parameters']['driver_file']['value']
    driver_file = corpus.files[driver_file_key]
    basetext_siglum = job.configuration['parameters']['basetext_siglum']['value']
    delete_existing = job.configuration['parameters']['delete_existing']['value'] == 'Yes'

    try:


        for nvs_content_type in NVS_CONTENT_TYPE_SCHEMA:
            if delete_existing and nvs_content_type['name'] in corpus.content_types:
                corpus.delete_content_type(nvs_content_type['name'])

            corpus.save_content_type(nvs_content_type)

        if 'Document' in corpus.content_types and delete_existing:
            corpus.delete_content_type('Document')

        nvs_doc_schema = None
        for schema in DOCUMENT_REGISTRY:
            if schema['name'] == "Document":
                nvs_doc_schema = deepcopy(schema)
                break

        if nvs_doc_schema:
            nvs_doc_schema['fields'] += nvs_document_fields
            nvs_doc_schema['templates']['Label']['template'] = "{{ Document.siglum_label|safe }}"
            corpus.save_content_type(nvs_doc_schema)


        if os.path.exists(driver_file.path):

            with open(driver_file.path, 'r') as tei_in:
                tei = BeautifulSoup(tei_in, "xml")
                extract_text_replacements(tei_in)

            print(text_replacements)

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

            print(json.dumps(include_file_paths, indent=4))
            include_files_exist = True
            for include_file in include_file_paths.keys():
                full_path = os.path.join(os.path.dirname(driver_file.path), include_file_paths[include_file])
                if os.path.exists(full_path):
                    include_file_paths[include_file] = full_path
                else:
                    include_files_exist = False
                    break

            if include_files_exist:
                parse_front_file(corpus, include_file_paths['front'])
                parse_playtext_file(corpus, include_file_paths['playtext'], basetext_siglum)
                parse_textualnotes_file(corpus, include_file_paths['textualnotes'])
                parse_bibliography(corpus, include_file_paths['bibliography'])
                parse_commentary(corpus, include_file_paths['commentary'])
    except:
        print(traceback.format_exc())


def parse_front_file(corpus, front_file_path):
    with open(front_file_path, 'r') as tei_in:
        tei = BeautifulSoup(tei_in, "xml")

    front = tei.container.front

    # extract series_title page and byline
    st_block = corpus.get_content('ContentBlock')
    st_block.handle = "series_title"
    st_block.html = ""

    series_title_page = front.find('titlePage', type='series')
    series_title = series_title_page.docTitle.find('titlePart', type='series')
    st_block.html += "<h2>{0}</h2>\n".format(_str(series_title))

    series_desc = series_title_page.docTitle.find('titlePart', type='desc')
    st_block.html += tei_to_html(series_desc)
    st_block.save()

    series_byline = series_title_page.byline
    byline_block = corpus.get_content('ContentBlock')
    byline_block.handle = "series_byline"
    byline_block.html = tei_to_html(series_byline)
    byline_block.save()

    # extract main_title page and byline
    main_block = corpus.get_content('ContentBlock')
    main_block.handle = "main_title"
    main_block.html = ""

    main_title_page = front.find('titlePage', type='main')
    main_block.html += "<h2>{0}</h2>".format(_str(main_title_page.find('titlePart', type='series')))
    main_block.html += "<h1>{0}</h1>".format(_str(main_title_page.find('titlePart', type='volume')))
    main_block.save()

    main_byline = corpus.get_content('ContentBlock')
    main_byline.handle = "main_byline"
    main_byline.html = tei_to_html(main_title_page.byline)
    main_byline.save()

    # extract imprint and copyright
    imprint = corpus.get_content('ContentBlock')
    imprint.handle = "main_imprint"
    imprint.html = tei_to_html(main_title_page.docImprint.publisher)
    imprint.save()

    copyright_div = front.find('div', type='copyright')
    copyright = corpus.get_content('ContentBlock')
    copyright.handle = "main_copyright"
    copyright.html = tei_to_html(copyright_div)
    copyright.save()

    # TODO: Parse TOC intelligently

    # extract preface
    preface_div = corpus.get_content('ContentBlock')
    preface_div.handle = "preface"
    preface_div.html = tei_to_html(front.find('div', type='preface'))
    preface_div.save()

    # TODO: Consider what to do about Plan of Work, which includes
    # witness list and band of terror explication

    # extract witness and reference documents
    plan_of_work = front.find('div', type='potw')

    try:
        witness_collections = []

        for witness_list in plan_of_work.find_all('listWit'):
            nvs_doc_type = witness_list['xml:id'].replace("listwit_", "")
            if nvs_doc_type == "editions":
                nvs_doc_type = "witness"
            elif nvs_doc_type == "other":
                nvs_doc_type = "reference"

            for witness_tag in witness_list.find_all('witness'):
                siglum = witness_tag['xml:id']
                siglum_label = tei_to_html(witness_tag.siglum)
                if 'rend' in witness_tag.siglum.attrs and witness_tag.siglum['rend'] == 'smcaps':
                    siglum_label = "<span style='font-variant: small-caps;'>{0}</span>".format(siglum_label)

                if witness_tag.bibl:
                    witness = corpus.get_content('Document')
                    witness.siglum = siglum
                    witness.siglum_label = siglum_label

                    witness.nvs_doc_type = nvs_doc_type

                    author = witness_tag.bibl.find('name')
                    if author:
                        witness.author = _str(author)
                    else:
                        witness.author = "Unknown"

                    common_title = witness_tag.bibl.find('hi')
                    if common_title:
                        witness.title = _str(common_title)
                        witness.work = _str(witness_tag.bibl.title)
                    else:
                        witness.title = _str(witness_tag.bibl.title)

                    witness.pub_date = _str(witness_tag.date)
                    witness.pub_date = re.sub(r"\D", "", witness.pub_date)
                    witness.pub_date = witness.pub_date[:4]
                    witness.save()
                elif 'corresp' in witness_tag.attrs:
                    witness_collections.append({
                        'siglum': siglum,
                        'siglum_label': siglum_label,
                        'tag': witness_tag
                    })

        for witness_collection_info in witness_collections:
            witness_collection = corpus.get_content('DocumentCollection')
            witness_collection.siglum = witness_collection_info['siglum']
            witness_collection.siglum_label = witness_collection_info['siglum_label']
            witness_tag = witness_collection_info['tag']

            referenced_witnesses = witness_tag['corresp'].split(' ')
            for reffed in referenced_witnesses:
                reffed_siglum = reffed.replace('#', '')
                reffed_doc = corpus.get_content('Document', {'siglum': reffed_siglum})[0]
                witness_collection.referenced_documents.append(reffed_doc.id)

            witness_collection.save()

        # Create Witness Collection for first folio
        # witness_collection = corpus.get_content('DocumentCollection')
        # witness_collection.siglum = "s_F"
        # witness_collection.siglum_label = "F"
        # reffed_doc = corpus.get_content('Document', {'siglum': "s_f1"})[0]
        # witness_collection.referenced_documents.append(reffed_doc.id)
        # witness_collection.save()

    except:
        print(traceback.format_exc())
    '''
    for bibl_tag in plan_of_work.listBibl.find_all('bibl'):
        biblio_id = bibl_tag['xml:id'].replace("pw_", "")

        try:
            biblio = Document(corpus.id).objects(corpus=corpus, kvp__biblio_id=biblio_id)[0]
        except:
            biblio = Document(corpus.id)()
            biblio.corpus = corpus
            biblio.kvp['biblio_id'] = biblio_id

        if biblio:
            author = bibl_tag.find('name')
            if author:
                biblio.author = _str(author)
            else:
                biblio.author = "Unknown"

            common_title = bibl_tag.find('hi')
            if common_title:
                biblio.title = _str(common_title)
                biblio.work = _str(bibl_tag.title)
            else:
                biblio.title = _str(bibl_tag.title)

            biblio.pub_date = _str(bibl_tag.date)
            biblio.pub_date = re.sub(r"\D", "", biblio.pub_date)
            biblio.pub_date = biblio.pub_date[:4]

            biblio.save()
    '''


def parse_playtext_file(corpus, playtext_file_path, basetext_siglum):
    playtext_lines = []
    unhandled_tags = []

    with open(playtext_file_path, 'r') as tei_in:
        tei = BeautifulSoup(tei_in, "xml")
        tei_in.seek(0)
        playtext_lines = tei_in.readlines()

    # retrieve basetext document
    basetext = corpus.get_content("Document", {'siglum': basetext_siglum})[0]

    # extract dramatis personae
    try:
        cast_list = tei.find("castList")
        for role_tag in cast_list.find_all("role"):
            cast_member = corpus.get_content('PlayRole')
            cast_member.xml_id = role_tag['xml:id']
            cast_member.role = " ".join([string for string in role_tag.stripped_strings])
            if not cast_member.role:
                cast_member.role = cast_member.xml_id
            cast_member.save()

        # go line by line to extract thru lines
        patterns = {
            'open_milestone': r'<milestone unit="[^"]*" n="([^"]*)">', # can be multi line
            'close_milestone': r'<\/milestone>',
            'open_stage': r'<stage type="([^"]*)"[^>]*>', # can be multi line
            'close_stage': r'<\/stage>',
            'open_speaker': r'<sp who="([^"]*)"[^>]*>', # can have multiple speakers in who attribute
            'close_speaker': r'<\/sp>',
            'open_name': r'<name>',
            'close_name': r'<\/name>',
            'line': r'<lb xml:id="([^"]*)" n="([^"]*)"[^>]*>',
            'act_scene': r'<div type="([^"]*)" n="([^"]*)"[^>]*>',
            'open_head': r'<head ?[^>]*>',
            'close_head': r'<\/head>',
            'open_sp': r'<speaker>',
            'close_sp': r'<\/speaker>',
            'open_castlist': r'<castList xml:id="([^"]*)">',
            'close_castlist': r'<\/castList>',
            'open_castgroup': r'<castGroup rend="braced_right\(#([^\)]*)\)">',
            'close_castgroup': r'<\/castGroup>',
            'open_castitem': r'<castItem>',
            'close_castitem': r'<\/castItem>',
            'self_closing_role': r'<role xml:id="([^"]*)"\/>',
            'open_role': r'<role xml:id="([^"]*)">',
            'close_role': r'<\/role>',
            'open_roledesc': r'<roleDesc>',
            'close_roledesc': r'<\/roleDesc>',
            'open_roledesc_id': r'<roleDesc xml:id="([^"]*)">',
            'open_foreign': r'<foreign xml:lang="([^"]*)" rend="italic">',
            'close_foreign': r'<\/foreign>',
            'open_italic_p': r'<p rend="italic">',
            'close_italic_p': r'<\/p>',
            'open_lg_song': r'<lg type="song" xml:id="([^"]*)" rend="italic">',
            'open_lg_stanza': r'<lg type="stanza">',
            'close_lg': r'<\/lg>',
        }

        word_info = {
            'line_number': 1,
            'word_index': 0,
            'play_line': None,
            'act': None,
            'scene': None,
            'name_start_index': None,
            'name_words': [],
            'line_group_start_index': None,
            'stage_direction_line_location': None,
            'stage_direction': None,
            'speakers': [],
            'speaker_line_location': None,
            'witness_location_id': None,
        }

        milestone_open = False

        for line in playtext_lines:
            # prepare line to be split into words by first marking open and close
            # angle brackets with '|' character (not found in playtext)
            line = line.replace('<', '|<')
            line = line.replace('>', '>|')

            # split line by '|' character so as to have a list where items are either
            # XML tags or text strings
            elements = [element for element in line.split('|') if element]
            word_chars = ""

            # iterate through elements
            for element_index in range(0, len(elements)):
                element = elements[element_index]
                # find any XML tag matches for this element
                match_found = False
                for pattern_name in patterns.keys():
                    match = None
                    match = re.search(patterns[pattern_name], element)
                    if match:
                        match_found = True

                        if element_index == len(elements) - 1 and word_chars:
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                        if pattern_name == 'open_milestone':
                            witness_location = corpus.get_content('WitnessLocation')
                            witness_location.witness = basetext.id
                            witness_location.starting_page = match.group(1)
                            witness_location.save()
                            word_info['witness_location_id'] = witness_location.id
                            milestone_open = True

                        elif pattern_name == 'close_milestone':
                            milestone_open = False

                        elif pattern_name == 'line':
                            if word_info['play_line']:
                                if word_info['play_line'].words:
                                    word_info['play_line'].save()
                                else:
                                    unhandled_tags.append('playline {0} has no words!'.format(word_info['play_line'].xml_id))
                                word_info['line_number'] += 1

                            word_info['play_line'] = corpus.get_content('PlayLine')
                            word_info['play_line'].xml_id = match.group(1)
                            word_info['play_line'].line_label = match.group(2)
                            word_info['play_line'].line_number = word_info['line_number']
                            word_info['play_line'].act = word_info['act']
                            word_info['play_line'].scene = word_info['scene']
                            word_info['play_line'].witness_locations.append(word_info['witness_location_id'])
                            word_info['play_line'].words = []

                        elif pattern_name == 'act_scene':
                            word_info[match.group(1)] = match.group(2)

                        elif pattern_name == 'open_speaker':
                            speaker_ids = match.group(1).split()
                            for speaker_id in speaker_ids:
                                speaker = corpus.get_content("PlayRole", {'xml_id': speaker_id.replace('#', '')})[0]
                                word_info['speakers'].append(speaker)

                            word_info['speaker_line_location'] = corpus.get_content('LineLocation')
                            word_info['speaker_line_location'].starting_line_number = word_info['line_number']
                            word_info['speaker_line_location'].starting_word_index = len(word_info['play_line'].words)

                        elif pattern_name == 'close_speaker':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            word_info['speaker_line_location'].ending_line_number = word_info['line_number']
                            word_info['speaker_line_location'].ending_word_index = len(word_info['play_line'].words)
                            word_info['speaker_line_location'].save()
                            for speaker in word_info['speakers']:
                                speaker.line_locations.append(word_info['speaker_line_location'].id)
                                speaker.save()

                            word_info['speakers'] = []
                            word_info['speaker_line_location'] = None

                        elif pattern_name == 'open_stage':
                            word_info['stage_direction'] = corpus.get_content('StageDirection')
                            word_info['stage_direction'].direction_type = match.group(1)
                            word_info['stage_direction_line_location'] = corpus.get_content('LineLocation')
                            word_info['stage_direction_line_location'].starting_line_number = word_info['line_number']
                            word_info['stage_direction_line_location'].starting_word_index = len(word_info['play_line'].words)

                        elif pattern_name == 'close_stage':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            word_info['stage_direction_line_location'].ending_line_number = word_info['line_number']
                            word_info['stage_direction_line_location'].ending_word_index = len(word_info['play_line'].words)
                            word_info['stage_direction_line_location'].save()
                            word_info['stage_direction'].line_location = word_info['stage_direction_line_location'].id
                            word_info['stage_direction'].save()
                            word_info['stage_direction'] = None
                            word_info['stage_direction_line_location'] = None
                            
                        elif pattern_name == 'open_head':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'header',
                            )
                            
                        elif pattern_name == 'close_head':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'header',
                                mode='close'
                            )

                        elif pattern_name == 'open_sp':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'speaker-abbreviation',
                            )

                        elif pattern_name == 'close_sp':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'speaker-abbreviation',
                                mode='close'
                            )

                        elif pattern_name == 'open_castlist':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'castlist',
                                match.group(1)
                            )
                            
                        elif pattern_name == 'close_castlist':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'castlist',
                                mode='close'
                            )
                            
                        elif pattern_name == 'open_castgroup':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'castgroup',
                                match.group(1)
                            )

                        elif pattern_name == 'close_castgroup':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'castgroup',
                                mode='close'
                            )

                        elif pattern_name == 'open_castitem':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'castitem',
                            )

                        elif pattern_name == 'close_castitem':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'castitem',
                                mode='close'
                            )

                        elif pattern_name == 'self_closing_role':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'role',
                                match.group(1)
                            )

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'role',
                                mode='close'
                            )

                        elif pattern_name == 'open_role':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'role',
                                match.group(1)
                            )

                        elif pattern_name == 'close_role':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'role',
                                mode='close'
                            )

                        elif pattern_name == 'open_roledesc':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'roledesc'
                            )

                        elif pattern_name == 'open_roledesc_id':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'roledesc',
                                match.group(1)
                            )

                        elif pattern_name == 'close_roledesc':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'roledesc',
                                mode='close'
                            )

                        elif pattern_name == 'open_foreign':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'foreign',
                                match.group(1)
                            )

                        elif pattern_name == 'close_foreign':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'foreign',
                                mode='close'
                            )

                        elif pattern_name == 'open_italic_p':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'italics',
                            )

                        elif pattern_name == 'close_italic_p' and word_info.get('italics_classes', False):
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'italics',
                                mode='close'
                            )

                        elif pattern_name == 'open_lg_song':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'song',
                                match.group(1)
                            )

                        elif pattern_name == 'open_lg_stanza':
                            handle_playstyle_tag(
                                corpus,
                                word_info,
                                'stanza',
                            )

                        elif pattern_name == 'close_lg':
                            handle_word_addition(word_info, word_chars)
                            word_chars = ""

                            if word_info.get('stanza_classes', False):
                                handle_playstyle_tag(
                                    corpus,
                                    word_info,
                                    'stanza',
                                    mode='close'
                                )
                            elif word_info.get('song_classes', False):
                                handle_playstyle_tag(
                                    corpus,
                                    word_info,
                                    'song',
                                    mode='close'
                                )

                if not milestone_open and not match_found:
                    if element.startswith('<'):
                        unhandled_tags.append(element)

                    elif word_info['play_line']:
                        for char_index in range(0, len(element)):
                            if not element[char_index].isspace():
                                word_chars += element[char_index]
                            elif element[char_index].isspace() and word_chars:
                                handle_word_addition(word_info, word_chars)
                                word_chars = ""

            handle_word_addition(word_info, word_chars)

        if word_info['play_line'].words:
            word_info['play_line'].save()

        witness_count = corpus.get_content('Document', {'nvs_doc_type': 'witness'}).count()
        line_locations = corpus.get_content('LineLocation', all=True)
        line_locations = list(
            line_locations.order_by('+starting_line_number', '-ending_line_number', '+starting_word_index',
                                    '-ending_word_index'))
        uri_pattern = "/corpus/{0}/LineLocation/{1}"
        line_location_uris = [uri_pattern.format(corpus.id, ll.id) for ll in line_locations]

        connected_tags = run_neo(
            '''
                MATCH (ll:LineLocation) <-[]- (tag)
                WHERE ll.uri IN $line_location_uris
                AND (tag:PlayRole or tag:StageDirection or tag:PlayStyle)
                RETURN tag.uri, ll.uri;
            ''', {'line_location_uris': line_location_uris}
        )

        role_ids = []
        stage_ids = []
        style_ids = []

        for connected_tag in connected_tags:
            tag_info = parse_uri(connected_tag[0])
            ll_info = parse_uri(connected_tag[1])

            tag_type = 'PlayRole'
            if 'StageDirection' in tag_info:
                tag_type = 'StageDirection'
                stage_ids.append(tag_info['StageDirection'])
            elif 'PlayStyle' in tag_info:
                tag_type = 'PlayStyle'
                style_ids.append(tag_info['PlayStyle'])
            else:
                role_ids.append(tag_info['PlayRole'])

            for ll_index in range(0, len(line_locations)):
                if str(line_locations[ll_index].id) == ll_info['LineLocation']:
                    if not hasattr(line_locations[ll_index], 'tags'):
                        line_locations[ll_index].tags = []

                    line_locations[ll_index].tags.append({
                        'type': tag_type,
                        'id': tag_info[tag_type]
                    })

        roles = corpus.get_content('PlayRole', {'id__in': role_ids})
        stages = corpus.get_content('StageDirection', {'id__in': stage_ids})
        styles = corpus.get_content('PlayStyle', {'id__in': style_ids})

        # consolidate all tags by line location key in dict
        tags = {}
        for line_location in line_locations:
            if hasattr(line_location, "tags"):
                location_start_key = "{0}:{1}".format(line_location.starting_line_number,
                                                      line_location.starting_word_index)
                location_end_key = "{0}:{1}".format(line_location.ending_line_number, line_location.ending_word_index)

                if location_start_key != location_end_key:
                    if location_start_key not in tags:
                        tags[location_start_key] = ""
                    if location_end_key not in tags:
                        tags[location_end_key] = ""

                    tags[location_start_key] += generate_line_tag_html(line_location, roles, stages, styles)
                    tags[location_end_key] += generate_line_tag_html(line_location, roles, stages, styles, "close")

        # sort tags for each location key, placing close tags before open tags
        for location_key in tags.keys():
            tags_to_sort = tags[location_key].replace('>', '>|')
            tags_to_sort = tags_to_sort.split('|')
            tags[location_key] = ''.join(sorted(tags_to_sort))

        lines = corpus.get_content('PlayLine', all=True)
        lines = lines.order_by('line_number')
        lines = list(lines)

        line_ids = []
        for line in lines:
            line_ids.append(line.id)

        # in order to make lines self-contained, we need to keep track of how to open and close any tags
        # that transcend line breaks

        line_tags = {
            'open': [],
            'close': []
        }

        for line_index in range(0, len(lines)):
            line = lines[line_index]

            html = "<a name='{0}'></a>".format(line.xml_id)
            html += ''.join(line_tags['open'])

            for word_index in range(0, len(line.words) + 1):
                location_key = "{0}:{1}".format(line.line_number, word_index)
                if location_key in tags:
                    html += tags[location_key]

                    adjust_line_tags(line_tags, tags[location_key])

                if word_index < len(line.words):
                    html += line.words[word_index] + " "

            html += ''.join(line_tags['close'])
            lines[line_index].rendered_html = html
            lines[line_index].witness_meter = "0" * witness_count
            lines[line_index].save()

        '''
        run_job(corpus.queue_local_job(task_name="Adjust Content", parameters={
            'content_type': 'LineLocation',
            'reindex': True,
            'relabel': True,
            'resave': False,
            'related_content_types': "PlayRole,StageDirection"
        }))
        '''
    except:
        print(json.dumps(unhandled_tags, indent=4))
        print(traceback.format_exc())


def handle_word_addition(word_info, word_chars):
    if word_chars:
        if word_chars.strip() in punctuation and word_info['play_line'].words:
            word_info['play_line'].words[-1] += word_chars.strip()
        else:
            word_info['play_line'].words.append(word_chars.strip())


def handle_playstyle_tag(corpus, word_info, tag_type, additional_classes="", mode="open"):
    ll_key = "{0}_line_location".format(tag_type)
    class_key = "{0}_classes".format(tag_type)
    
    if mode == 'open':
        if additional_classes:
            additional_classes = ' ' + additional_classes.strip()

        word_info[ll_key] = corpus.get_content('LineLocation')
        word_info[ll_key].starting_line_number = word_info['line_number']
        word_info[ll_key].starting_word_index = len(word_info['play_line'].words)
        word_info[class_key] = "{0}{1}".format(tag_type, additional_classes)
    else:
        word_info[ll_key].ending_line_number = word_info['line_number']
        word_info[ll_key].ending_word_index = len(word_info['play_line'].words)
        word_info[ll_key].save()
        playstyle = corpus.get_content('PlayStyle')
        playstyle.classes = word_info[class_key]
        playstyle.line_location = word_info[ll_key].id
        playstyle.save()
        word_info[ll_key] = None
        word_info[class_key] = ""


def generate_line_tag_html(line_location, roles, stages, styles, mode='open'):
    html = ""

    for tag in line_location.tags:
        if tag['type'] == 'PlayRole':
            if mode == 'open':
                for role in roles:
                    if str(role.id) == tag['id']:
                        html += "<span class='speaker {0}'>".format(role.xml_id)
                        break
            else:
                html += "</span>"

        elif tag['type'] == 'StageDirection':
            if mode == 'open':
                for stage in stages:
                    if str(stage.id) == tag['id']:
                        html += "<span class='stage_direction {0}'>".format(stage.direction_type)
                        break
            else:
                html += "</span>"

        elif tag['type'] == 'PlayStyle':
            if mode == 'open':
                for style in styles:
                    if str(style.id) == tag['id']:
                        html += "<span class='{0}'>".format(style.classes)
                        break
            else:
                html += "</span>"

    return html


def adjust_line_tags(line_tags, html):

    html_tags = html.split('>')
    html_tags = [h + '>' for h in html_tags if h]

    for html_tag in html_tags:
        # handle closing tag
        if html_tag.startswith('</'):
            del line_tags['open'][-1]
            del line_tags['close'][0]
            '''
            tag = html_tag.replace('</', '')
            tag = tag.replace('>', '')

            # remove tag from open list
            tag_index = len(line_tags['open']) - 1
            while tag_index >= 0:
                if '<' + tag in line_tags['open'][tag_index]:
                    del line_tags['open'][tag_index]
                    tag_index = -1

            # remove tag from close list
            for tag_index in range(0, len(line_tags['close'])):
                if line_tags['close'] == html_tag:
                    del line_tags['close'][tag_index]
                    break
            '''

        # handle open tag
        else:
            tag = html_tag.split()[0]
            tag = tag.replace('<', '')

            line_tags['open'].append(html_tag)
            line_tags['close'].insert(0, "</" + tag + ">")


def parse_textualnotes_file(corpus, textualnotes_file_path):
    parse_report = []

    try:

        '''
        for nvs_content_type in NVS_CONTENT_TYPE_SCHEMA:
            if nvs_content_type['name'] in ['TextualNote', 'TextualVariant']:
                corpus.delete_content_type(nvs_content_type['name'])
                corpus.save_content_type(nvs_content_type)
        '''

        # open textualnotes xml, read raw text into tei_text,
        # and perform special text replacements before feeding
        # into BeautifulSoup
        with open(textualnotes_file_path, 'r') as tei_in:
            tei_text = tei_in.read()
            for text, replacement in text_replacements.items():
                tei_text = tei_text.replace(text, replacement)

            tei = BeautifulSoup(tei_text, "xml")

        # build line_id_map to quickly match line xml_ids w/ mongodb objectids
        line_id_map = {}
        lines = corpus.get_content('PlayLine', all=True, only=['id', 'xml_id'])
        lines.order_by('line_number')
        for line in lines:
            line_id_map[line.xml_id] = line.id

        # get list of witnesses ordered by publication date so as
        # to handle witness ranges
        witnesses = corpus.get_content('Document', {'nvs_doc_type': 'witness'})
        witnesses = list(witnesses.order_by('published'))

        # get all "note" tags, corresponding to TexualNote content
        # type so we can iterate over and build them
        notes = tei.find_all("note", attrs={'type': 'textual'})
        for note in notes:

            # create instance of TextualNote
            textual_note = corpus.get_content('TextualNote')
            textual_note.xml_id = note['xml:id']

            textual_note.lines = get_line_ids(line_id_map, note['target'], note.attrs.get('targetEnd', None))

            note_lemma = None
            if note.app.find('lem', recursive=False):
                note_lemma = tei_to_html(note.app.lem)

            textual_note_witness_indicators = []

            variants = note.app.find_all('appPart')
            for variant in variants:
                textual_variant = corpus.get_content('TextualVariant')

                reading_description = variant.find('rdgDesc')
                if reading_description:
                    textual_variant.description = tei_to_html(reading_description)

                reading = variant.find('rdg')
                if reading:
                    if 'type' in reading.attrs:
                        textual_variant.transform_type = reading['type']
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
                next_siglum_ends = False
                exclusion_started = False
                excluding_sigla = []

                for child in variant.wit.children:
                    if child.name == 'siglum':
                        siglum_label = tei_to_html(child)
                        if 'rend' in child.attrs and child['rend'] == 'smcaps':
                            siglum_label = "<span style='font-variant: small-caps;'>{0}</span>".format(siglum_label)

                        if not starting_siglum:
                            starting_siglum = siglum_label
                        elif next_siglum_ends:
                            textual_variant.witnesses.extend(
                                get_witness_ids(
                                    witnesses,
                                    starting_siglum,
                                    siglum_label
                                )
                            )
                            starting_siglum = None
                        elif exclusion_started:
                            excluding_sigla.append(siglum_label)
                    else:
                        formula = str(child.string).strip()
                        if formula.startswith('+'):
                            if '(-' in formula:
                                exclusion_started = True
                            else:
                                textual_variant.witnesses.extend(
                                    get_witness_ids(
                                        witnesses,
                                        starting_siglum,
                                        include_all_following=True,
                                    )
                                )
                                starting_siglum = None
                        elif formula.startswith('-'):
                            next_siglum_ends = True
                        elif formula == ',' and not exclusion_started:
                            textual_variant.witnesses.extend(
                                get_witness_ids(
                                    witnesses,
                                    starting_siglum
                                )
                            )
                            starting_siglum = None
                        elif formula == ')' and exclusion_started and excluding_sigla:
                            textual_variant.witnesses.extend(
                                get_witness_ids(
                                    witnesses,
                                    starting_siglum,
                                    include_all_following=True,
                                    excluding_sigla=excluding_sigla
                                )
                            )
                            starting_siglum = None

                if starting_siglum:
                    textual_variant.witnesses.extend(
                        get_witness_ids(
                            witnesses,
                            starting_siglum
                        )
                    )

                variant_witness_indicators = get_variant_witness_indicators(witnesses, textual_variant)
                textual_note_witness_indicators.append(variant_witness_indicators)
                textual_variant.witness_meter = make_witness_meter(variant_witness_indicators)

                try:
                    textual_variant.variant = perform_variant_transform(corpus, textual_note, textual_variant)
                except:
                    parse_report.append("Error when performing transform for variant in note {0}".format(textual_note.xml_id))
                    parse_report.append(traceback.format_exc())
                    textual_variant.has_bug = 1

                    if len(parse_report) > 20:
                        return None

                textual_variant.save()
                textual_note.variants.append(textual_variant.id)

            combined_indicators = combine_witness_indicators(textual_note_witness_indicators)
            textual_note.witness_meter = make_witness_meter(combined_indicators)
            textual_note.save()
            textual_note.reload()

            for tn_line in textual_note.lines:
                if tn_line.witness_meter:
                    combined_indicators = combine_witness_indicators([tn_line.witness_meter, textual_note.witness_meter])
                    tn_line.witness_meter = make_witness_meter(combined_indicators)
                else:
                    tn_line.witness_meter = textual_note.witness_meter

                tn_line.save()

    except:
        print(traceback.format_exc())

    for parse_report_line in parse_report:
        print(parse_report_line)


def perform_note_transforms(job_id):
    job = Job(job_id)
    corpus = job.corpus

    try:
        notes = corpus.get_content('TextualNote', all=True)
        #notes = corpus.get_content('TextualNote', {'xml_id': 'tn_70-03'})

        for note in notes:
            for variant in note.variants:
                variant.variant = perform_variant_transform(corpus, note, variant)
                variant.save()
    except:
        print(traceback.format_exc())


def get_witness_ids(witnesses, starting_witness_siglum, ending_witness_siglum=None, include_all_following=False, excluding_sigla=[]):
    witness_ids = []

    starting_found = False
    ending_found = False

    for witness in witnesses:
        if not starting_found and witness.siglum_label == starting_witness_siglum:
            witness_ids.append(witness.id)
            starting_found = True
        elif starting_found and (ending_witness_siglum or include_all_following) and not ending_found:
            if witness.siglum_label not in excluding_sigla:
                witness_ids.append(witness.id)

                if witness.siglum_label == ending_witness_siglum:
                    ending_found = True

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


def combine_witness_indicators(indicators_list):
    print(json.dumps(indicators_list, indent=4))

    combined = []
    for indicator_index in range(0, len(indicators_list[0])):
        found = False
        for indicators in indicators_list:
            if (isinstance(indicators[indicator_index], str) and indicators[indicator_index] == '1') or indicators[indicator_index] is True:
                found = True
                break
        combined.append(found)

    print(combined)

    return combined


def make_witness_meter(indicators):
    witness_meter = ""
    for witness_indicator in indicators:
        if (isinstance(witness_indicator, str) and witness_indicator == '1') or witness_indicator is True:
            witness_meter += "1"
        else:
            witness_meter += "0"
    return witness_meter


def perform_variant_transform(corpus, note, variant):
    result = ""
    original_text = ""
    words = []

    if type(note.lines[0]) is ObjectId:
        lines = corpus.get_content('PlayLine', {'id__in': note.lines}, only=['words'])
        lines = lines.order_by('line_number')
        for line in lines:
            words.extend(line.words)
    elif hasattr(note.lines[0], 'words'):
        for line in note.lines:
            words.extend(line.words)

    if words:
        original_text = " ".join(words)
        ellipsis = ' . . . '
        swung_dash = ' ~ '
        under_carrot = '‸'
        double_under_carrot = '‸ ‸'

        if variant.lemma and variant.transform and variant.transform_type:
            lemma = strip_tags(variant.lemma).replace(double_under_carrot, '').replace(under_carrot, '')
            transform = strip_tags(variant.transform).replace('| ', '').replace(double_under_carrot, '').replace(under_carrot, '')

            if variant.transform_type == "replace":


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
                if _contains(lemma, [ellipsis]) and _contains(variant.transform, [ellipsis, swung_dash]):
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

                        result = result.replace(lemmas[lemma_index], transforms[lemma_index])

                # replace using swung_dash only
                elif swung_dash in variant.transform:
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

                    result = original_text.replace(lemma, transform)

                # replace using ellipsis
                elif ellipsis in lemma and ellipsis in variant.transform:
                    lemmas = lemma.split(ellipsis)
                    transforms = transform.split(ellipsis)
                    if len(lemmas) == len(transforms):
                        result = original_text
                        for lemma_index in range(0, len(lemmas)):
                            result = result.replace(lemmas[lemma_index], transforms[lemma_index])

                # ellipsis in lemma only
                elif ellipsis in lemma:
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
                    result = original_text.replace(lemma, transform)

                # simple replacement
                elif lemma in original_text:
                    result = original_text.replace(lemma, transform)

        # replace line altogether
        elif not variant.lemma and variant.transform_type == 'replace' and variant.transform:
            result = strip_tags(variant.transform)

        # insert at beginning of line
        elif not variant.lemma and variant.transform and variant.transform_type == "insert":
            if variant.description and strip_tags(variant.description).lower().startswith("ad."):
                result = "{0} {1}".format(original_text, strip_tags(variant.transform))
            else:
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

    return result


def parse_bibliography(corpus, bibliography_file_path):

    old_bibs = corpus.get_content('Document', {'nvs_doc_type': 'bibliography'})
    for bib in old_bibs:
        bib.delete()


    with open(bibliography_file_path, 'r') as tei_in:
        tei_text = tei_in.read()
        for text, replacement in text_replacements.items():
            tei_text = tei_text.replace(text, replacement)

        tei = BeautifulSoup(tei_text, "xml")

    unhandled = []
    bibls = tei.find_all('bibl')
    for bibl in bibls:
        if 'xml:id' in bibl.attrs:
            doc = corpus.get_content('Document')
            doc.siglum = bibl['xml:id']

            doc_data = {
                'author': '',
                'bibliographic_entry': '',
                'title': '',
                'pub_date': '',
                'editor': '',
                'publisher': '',
                'place': '',
                'unhandled': []
            }

            extract_bibl_components(bibl, doc_data)

            for key in doc_data.keys():
                if hasattr(doc, key) and doc_data[key]:
                    setattr(doc, key, doc_data[key])

            if doc_data['unhandled']:
                unhandled.extend(doc_data['unhandled'])
                unhandled = list(set(unhandled))

            doc.nvs_doc_type = 'bibliography'
            doc.save()

    print(json.dumps(unhandled, indent=4))


def extract_bibl_components(tag, doc_data, inside_note=False):
    for element in tag.children:
        if element.name:
            if element.name == 'author':
                author = _str(element.string)
                if doc_data['author']:
                    doc_data['author'] += ", "
                doc_data['author'] += author
                doc_data['bibliographic_entry'] += author

            elif element.name == 'title':
                title = handle_bibl_title(element)
                if not doc_data['title'] and not inside_note:
                    doc_data['title'] = title

                doc_data['bibliographic_entry'] += title

            elif element.name == 'date':
                if not doc_data['pub_date']:
                    doc_data['pub_date'] = _str(element.string)
                    doc_data['bibliographic_entry'] += doc_data['pub_date']

            elif element.name == 'pubPlace':
                doc_data['place'] = _str(element.string)
                doc_data['bibliographic_entry'] += doc_data['place']

            elif element.name == 'publisher':
                doc_data['publisher'] = _str(element.string)
                doc_data['bibliographic_entry'] += doc_data['publisher']

            elif element.name in ['note', 'bibl']:
                extract_bibl_components(element, doc_data, inside_note=True)

            elif element.name == 'ref' and _contains(element.attrs, ['targType', 'target']):
                doc_data['bibliographic_entry'] += '''<a ref="javascript: navigate_to('{0}', '{1}');">'''.format(
                    element['targType'],
                    element['target']
                )

                for child in element.children:
                    if child.name:
                        extract_bibl_components(child, doc_data, inside_note=True)
                    else:
                        doc_data['bibliographic_entry'] += str(child)

                doc_data['bibliographic_entry'] += "</a>"

            else:
                doc_data['unhandled'].append(element.name)
                doc_data['bibliographic_entry'] += _str(element.string)
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


def parse_commentary(corpus, commentary_file_path):
    parse_report = []

    try:

        '''
        for nvs_content_type in NVS_CONTENT_TYPE_SCHEMA:
            if nvs_content_type['name'] in ['Commentary']:
                corpus.delete_content_type(nvs_content_type['name'])
                corpus.save_content_type(nvs_content_type)
        '''


        # open commentary xml, read raw text into tei_text,
        # and perform special text replacements before feeding
        # into BeautifulSoup
        with open(commentary_file_path, 'r') as tei_in:
            tei_text = tei_in.read()
            for text, replacement in text_replacements.items():
                tei_text = tei_text.replace(text, replacement)

            tei = BeautifulSoup(tei_text, "xml")

        line_id_map = {}
        lines = corpus.get_content('PlayLine', all=True, only=['id', 'xml_id'])
        lines.order_by('line_number')
        for line in lines:
            line_id_map[line.xml_id] = line.id

        note_tags = tei.find_all('note', attrs={'type': 'commentary'})
        unhandled = []

        for note_tag in note_tags:
            note = corpus.get_content('Commentary')
            note.xml_id = note_tag['xml:id']

            note.lines = get_line_ids(line_id_map, note_tag['target'], note_tag.attrs.get('targetEnd', None))

            note.contents = ""
            note_data = {}
            for child in note_tag.children:
                note.contents += handle_commentary_tag(child, note_data)

            if _contains(note_data, ['line_label', 'subject_matter']):
                note.line_label = note_data['line_label']
                note.subject_matter = note_data['subject_matter']
                note.save()

                note_uri = "/corpus/{0}/Commentary/{1}".format(corpus.id, note.id)
                # TODO: link up items in data['references']
            else:
                parse_report.append("commentary note {0} missing label or lem".format(note.xml_id))

            if 'unhandled' in note_data:
                unhandled.extend(note_data['unhandled'])

        if unhandled:
            unhandled = list(set(unhandled))
            parse_report.append(unhandled)

    except:
        parse_report.append(traceback.format_exc())

    print(json.dumps(parse_report, indent=4))


def handle_commentary_tag(tag, data={}):
    html = ""

    if tag.name:

        if tag.name == 'label':
            data['line_label'] = _str(tag)

        elif tag.name == 'lem':
            data['subject_matter'] = "".join([handle_commentary_tag(child, data) for child in tag.children])

        elif tag.name == 'ref' and _contains(tag.attrs, ['targType', 'target']):
            if 'references' not in data:
                data['references'] = []

            data['references'].append((tag['targType'], tag['target'].replace('#', '')))

            html += '''<a href="javascript: navigate_to('{0}', '{1}');">'''.format(
                tag['targType'],
                tag['target'].replace('#', '')
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
            html += '''<span class="quote">'''
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])
            html += '''</span>'''

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

        elif tag.name == 'rs':
            html += "".join([handle_commentary_tag(child, data) for child in tag.children])

        elif tag.name == 'ptr' and _contains(tag.attrs, ['targType', 'target']):
            if 'references' not in data:
                data['references'] = []

            target = tag['target'].replace('#', '')
            if 'targetEnd' in tag.attrs:
                data['references'].append((tag['targType'], target + '-' + tag['targetEnd'].replace('#', '')))
                target += " " + tag['targetEnd']
            else:
                data['references'].append((tag['targType'], target))

            html += '''<a href="javascript: navigate_to('{0}', '{1}');">here</a>'''.format(
                tag['targType'],
                target
            )

        elif tag.name == 'siglum':
            if 'references' not in data:
                data['references'] = []

            siglum_label = "".join([handle_commentary_tag(child, data) for child in tag.children])
            if 'rend' in tag.attrs and tag['rend'] == 'smcaps':
                siglum_label = '''<span style="font-variant: small-caps;">{0}</span>'''.format(siglum_label)

            data['references'].append(('siglum', siglum_label))

            html += '''<a href="javascript: navigate_to('{0}', '{1}');">'''.format(
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

        else:
            if 'unhandled' not in data:
                data['unhandled'] = []

            data['unhandled'].append(tag.name)

    else:
        html = str(tag)

        if html.strip() == ']' and 'lem_bracket_found' not in data:
            html = ""
            data['lem_bracket_found'] = True

    return html


def get_line_ids(line_id_map, xml_id_start, xml_id_end=None):
    line_ids = []

    target_xml_ids = xml_id_start.replace('#', '').split()
    for target_xml_id in target_xml_ids:
        line_ids.append(line_id_map[target_xml_id])

    if xml_id_end:
        ending_xml_id = xml_id_end.replace('#', '')

        start_found = False
        for line_xml_id in line_id_map.keys():
            if not start_found and line_xml_id == target_xml_ids[0]:
                start_found = True

            elif start_found and line_id_map[line_xml_id] not in line_ids:
                line_ids.append(line_id_map[line_xml_id])

            if start_found and line_xml_id == ending_xml_id:
                break

    return line_ids


def extract_text_replacements(file):
    file.seek(0)
    pattern = re.compile(r'<!ENTITY ([^ ]*)\s*"([^"]*)"')

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


def _str(val):
    if val and hasattr(val, 'string'):
        val = str(val.string)
        for text, replacement in text_replacements.items():
            val = val.replace(text, replacement)
        return val
    return ''


def tei_to_html(tei):
    html = ""

    tei_conversions = [
        (r"<lb/>", "<br>"),
        (r"<name>", "<span class='name'>"),
        (r"</name>", "</span>"),
        (r"<date>", "<span class='date'>"),
        (r"</date>", "</span>"),
        (r"<editor[^>]*>", "<span class='name'>"),
        (r"</editor>", "</span>"),
        (r"<head>", "<h2>"),
        (r"</head>", "</h2>"),
        (r"<title level=\"m\">", "<i>"),
        (r"</title>", "</i>"),
        (r"<closer>", ""),
        (r"</closer>", "")
    ]

    tei_transforms = [
        (r'<name[^>]*>([^<]*)</name>', lambda name: register_person(name)),
        (r'<hi rend="smcaps">(.*?)</hi>', lambda text: "<span style='font-variant: small-caps;'>{0}</span>".format(text)),
        (r'<hi rend="italic">(.*?)</hi>', lambda text: "<i>{0}</i>".format(text)),
        (r'<lb rend="indent\(([^)]*)\)"\/>', lambda indentation: "<br><span style='width: {0}; display: inline-block;'>&nbsp;</span>".format(indentation)),
        (r'<space extent="([^"]*)"\/>', lambda space: "<span style='width: {0}; display: inline-block;'>&nbsp;</span>".format(space)),
        (r'<signed>([^<]*)<\/signed>', lambda name: "<div style='text-align: right; margin-top: 8px; margin-bottom: 8px;'>{0}</div>".format(name)),
        (r'<siglum>([^<]*)<\/siglum>', lambda siglum: reference_document(siglum, 'siglum')),
        (r'<anchor type="xref" xml:id="([^"]*)"\/>', lambda anchor: register_anchor(anchor)),
        (r'(<ref [^>]*>.*?<\/ref>)', lambda reffed: process_link(reffed)),
        (r'(<ptr targType="[^"]*" target="#[^"]*"\/>)', lambda reffed: process_link(reffed, pointer=True)),
        (r'<quote rend="block">(.*?)<\/quote>', lambda quoted: "<div style='margin: 20px 0px 20px 20px;'>{0}</div>".format(quoted)),
    ]

    for child in tei.children:
        child_html = str(child)

        for text, replacement in text_replacements.items():
            child_html = child_html.replace(text, replacement)

        for tei_conversion in tei_conversions:
            child_html = re.sub(tei_conversion[0], tei_conversion[1], child_html)

        for tei_transform in tei_transforms:
            match = re.search(tei_transform[0], child_html, flags=re.S)
            while match:
                full_match = match.group(0)
                transform_match = match.group(1)
                transformed = tei_transform[1](transform_match)
                child_html = child_html.replace(full_match, transformed)
                match = re.search(tei_transform[0], child_html)

        html += child_html

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
        return '''<a ref="javascript: navigate_to('{0}', '{1}');">{2}</a>'''.format(
            link_type,
            target,
            text
        )
    else:
        return reffed


def save_content(content):
    try:
        content.save()
    except:
        print("{0} already exists!".format(content.content_type.name))
