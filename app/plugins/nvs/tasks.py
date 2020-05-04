import os
import re
from .content import REGISTRY as NVS_CONTENT_TYPE_SCHEMA
from plugins.document.content import REGISTRY as DOCUMENT_REGISTRY
from corpus import *
from manager.tasks import run_job
from bs4 import BeautifulSoup
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
     }
}

nvs_document_fields = [
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

    '''
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
    '''

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
            #parse_front_file(corpus, include_file_paths['front'])
            #parse_playtext_file(corpus, include_file_paths['playtext'], basetext_siglum)
            parse_textualnotes_file(corpus, include_file_paths['textualnotes'])


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
            'open_head': r'<head>',
            'close_head': r'<\/head>',
            'open_sp': r'<speaker>',
            'close_sp': r'<\/speaker>',
            #'open_castlist': r'<castList xml:id="([^"]*)">',
            #'close_castlist': r'<\/castList>'
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
            'head_line_location': None,
            'head_classes': "",
            'sp_line_location': None,
            'sp_classes': ""
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
                            word_info['play_line'].words.append(word_chars)
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
                                word_info['play_line'].save()
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
                            if word_chars:
                                word_info['play_line'].words.append(word_chars)
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
                            if word_chars:
                                word_info['play_line'].words.append(word_chars)
                                word_chars = ""

                            word_info['stage_direction_line_location'].ending_line_number = word_info['line_number']
                            word_info['stage_direction_line_location'].ending_word_index = len(word_info['play_line'].words)
                            word_info['stage_direction_line_location'].save()
                            word_info['stage_direction'].line_location = word_info['stage_direction_line_location'].id
                            word_info['stage_direction'].save()
                            word_info['stage_direction'] = None
                            word_info['stage_direction_line_location'] = None
                            
                        elif pattern_name == 'open_head':
                            word_info['head_line_location'] = corpus.get_content('LineLocation')
                            word_info['head_classes'] = "header"
                            word_info['head_line_location'].starting_line_number = word_info['line_number']
                            word_info['head_line_location'].starting_word_index = len(word_info['play_line'].words)
                            
                        elif pattern_name == 'close_head':
                            if word_chars:
                                word_info['play_line'].words.append(word_chars)
                                word_chars = ""

                            word_info['head_line_location'].ending_line_number = word_info['line_number']
                            word_info['head_line_location'].ending_word_index = len(word_info['play_line'].words)
                            word_info['head_line_location'].save()
                            head_tag = corpus.get_content('PlayStyle')
                            head_tag.classes = word_info['head_classes']
                            head_tag.line_location = word_info['head_line_location'].id
                            head_tag.save()
                            word_info['head_line_location'] = None
                            word_info['head_classes'] = ""

                        elif pattern_name == 'open_sp':
                            word_info['sp_line_location'] = corpus.get_content('LineLocation')
                            word_info['sp_classes'] = "speaker-abbreviation"
                            word_info['sp_line_location'].starting_line_number = word_info['line_number']
                            word_info['sp_line_location'].starting_word_index = len(word_info['play_line'].words)

                        elif pattern_name == 'close_sp':
                            if word_chars:
                                word_info['play_line'].words.append(word_chars)
                                word_chars = ""

                            word_info['sp_line_location'].ending_line_number = word_info['line_number']
                            word_info['sp_line_location'].ending_word_index = len(word_info['play_line'].words)
                            word_info['sp_line_location'].save()
                            sp_tag = corpus.get_content('PlayStyle')
                            sp_tag.classes = word_info['sp_classes']
                            sp_tag.line_location = word_info['sp_line_location'].id
                            sp_tag.save()
                            word_info['sp_line_location'] = None
                            word_info['sp_classes'] = ""

                if not milestone_open and not match_found:
                    if element.startswith('<'):
                        unhandled_tags.append(element)

                    elif word_info['play_line']:
                        for char_index in range(0, len(element)):
                            if not element[char_index].isspace():
                                word_chars += element[char_index]
                            elif element[char_index].isspace() and word_chars:
                                word_info['play_line'].words.append(word_chars)
                                word_chars = ""

            if word_chars:
                word_info['play_line'].words.append(word_chars)



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
    ''' WTF WTF WTF
    <name>
    Bohe­
    <lb xml:id="tln_25" n="25" rend="print_tln" />
    mia
    </name>
    
    <sp who="#Autolicus">
<lg type="song" xml:id="lg_pt_song01" rend="italic">
<lg type="stanza">
<lb xml:id="tln_1669" n="1669"/>
<l>When Daffadils begin to peere,</l>
<lb xml:id="tln_1670" n="1670" rend="print_tln"/>
<l>With heigh the Doxy ouer the dale,</l>
<lb xml:id="tln_1671" n="1671"/>
<l>Why then comes in the sweet o’the yeere,</l>
<lb xml:id="tln_1672" n="1672"/>
<l>
For the red blood raigns in y
<hi rend="superscript">e</hi>
winters pale.
</l>
</lg>
<lg type="stanza">
<lb xml:id="tln_1673" n="1673"/>
<l>The white sheete bleaching on the hedge,</l>
<lb xml:id="tln_1674" n="1674"/>
<l>With hey the sweet birds, O how they sing:</l>
<lb xml:id="tln_1675" n="1675" rend="print_tln"/>
<l>Doth set my pugging tooth an edge,</l>
<lb xml:id="tln_1676" n="1676"/>
<l>For a quart of Ale is a dish for a King.</l>
</lg>
<lg type="stanza">
<lb xml:id="tln_1677" n="1677"/>
<l>The Larke, that tirra-Lyra chaunts,</l>
<lb xml:id="tln_1678" n="1678"/>
<l>With heigh, the Thrush and the Iay:</l>
<lb xml:id="tln_1679" n="1679"/>
<l>Are Summer songs for me and my Aunts</l>
<lb xml:id="tln_1680" n="1680" rend="print_tln"/>
<l>While we lye tumbling in the hay.</l>
</lg>
</lg>
<lb xml:id="tln_1681" n="1681"/>
<p>
I haue seru’d Prince
<name>Florizell</name>
, and in my time wore three
<lb xml:id="tln_1682" n="1682"/>
pile, but now I am out of seruice.
</p>
<lg type="song" xml:id="lg_pt_song02" rend="italic">
<lb xml:id="tln_1683" n="1683"/>
<l>But shall I go mourne for that (my deere)</l>
<lb xml:id="tln_1684" n="1684"/>
<l>the pale Moone shines by night:</l>
<lb xml:id="tln_1685" n="1685" rend="print_tln"/>
<l>And when I wander here, and there</l>
<lb xml:id="tln_1686" n="1686"/>
<l>I then do most go right.</l>
<lb xml:id="tln_1687" n="1687"/>
<l>If Tinkers may haue leaue to liue,</l>
<lb xml:id="tln_1688" n="1688"/>
<l>and beare the Sow-skin Bowget,</l>
<lb xml:id="tln_1689" n="1689"/>
<l>Then my account I well may giue,</l>
<lb xml:id="tln_1690" n="1690" rend="print_tln"/>
<l>and in the Stockes auouch-it.</l>
</lg>
    '''

    '''
    thru_line_pattern = re.compile(r'<lb xml:id="(tln_[^"]*)" n="([^"]*)"[^\/]*\/>(.*)')
    for line in playtext_lines:
        matches = thru_line_pattern.findall(line)
        if matches:
            thru_line = Content(corpus.id, 'Line')
            thru_line.fields['xml_id']['value'] = matches[0][0]
            thru_line.fields['number']['value'] = matches[0][1]
            thru_line.fields['content']['value'] = matches[0][2]
            save_content(thru_line)
    '''


def parse_textualnotes_file(corpus, textualnotes_file_path):
    parse_report = []

    try:
        for nvs_content_type in NVS_CONTENT_TYPE_SCHEMA:
            if nvs_content_type['name'] in ['TextualNote', 'TextualVariant']:
                corpus.delete_content_type(nvs_content_type['name'])
                corpus.save_content_type(nvs_content_type)

        with open(textualnotes_file_path, 'r') as tei_in:
            tei_text = tei_in.read()
            for text, replacement in text_replacements.items():
                tei_text = tei_text.replace(text, replacement)

            tei = BeautifulSoup(tei_text, "xml")

        witnesses = corpus.get_content('Document', {'nvs_doc_type': 'witness'})
        witnesses = witnesses.order_by('published')

        notes = tei.find_all("note")
        for note in notes:
            textual_note = corpus.get_content('TextualNote')
            textual_note.xml_id = note['xml:id']

            starting_line = None
            ending_line = None

            starting_line_xml_id = note['target'].replace('#', '')
            ending_line_xml_id = None
            if 'targetEnd' in note.attrs:
                ending_line_xml_id = note['targetEnd'].replace('#', '')

            starting_line_query = corpus.get_content('PlayLine', {'xml_id': starting_line_xml_id})
            if starting_line_query:
                textual_note.starting_line = starting_line_query[0].id
            else:
                parse_report.append("{0} can't find start line {1}".format(textual_note.xml_id, starting_line_xml_id))
            if ending_line_xml_id:
                ending_line_query = corpus.get_content('PlayLine', {'xml_id': ending_line_xml_id})
                if ending_line_query:
                    textual_note.ending_line = ending_line_query[0].id
                else:
                    parse_report.append("{0} can't find end line {1}".format(textual_note.xml_id, ending_line_xml_id))

            lemma = None
            if note.app.lem:
                lemma = tei_to_html(note.app.lem)

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

                if not lemma:
                    lem_tag = variant.find('lem')
                    if lem_tag:
                        lemma = tei_to_html(lem_tag)

                if lemma:
                    textual_variant.lemma = lemma

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

                if starting_siglum:
                    textual_variant.witnesses.extend(
                        get_witness_ids(
                            witnesses,
                            starting_siglum
                        )
                    )

                textual_variant.save()
                textual_note.variants.append(textual_variant.id)

            textual_note.save()
    except:
        print(traceback.format_exc())

    for parse_report_line in parse_report:
        print(parse_report_line)



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
