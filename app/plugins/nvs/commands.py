from .content import REGISTRY as NVS_CONTENT_TYPE_SCHEMA
from django.utils.html import strip_tags
from datetime import datetime
from dateutil import parser
from corpus import *
from manager.utilities import _contains
from cms import *
from bs4 import BeautifulSoup


REGISTRY = {
    "import_data": {
        "description": "This command takes two parameters: the path to the TEI driver file for an NVS edition, and the ID of the corpus to load it into, i.e.: nvs:import_data /path/to/driver_file.xml 5dd84532e8cd43e0212f8c98"
    }
}

text_replacements = {}


def import_data(driver_file_path, corpus_id):
    corpus = get_corpus(corpus_id)
    load_content_types_from_schema(corpus, NVS_CONTENT_TYPE_SCHEMA)

    # setup corpus document field settings
    corpus.field_settings['pub_date']['label'] = "Published"
    corpus.field_settings['kvp__witness_siglum'] = {
        "label": "Siglum",
        "es_field_name": "kvp.witness_siglum",
        "type": "keyword",
        "display": True,
        "search": True,
        "sort": True
    }
    corpus.field_settings['kvp__witness_type'] = {
        "label": "Witness Type",
        "es_field_name": "kvp.witness_type",
        "type": "keyword",
        "display": True,
        "search": True,
        "sort": True
    }
    corpus.field_settings['kvp__biblio_id'] = {
        "label": "Biblio ID",
        "es_field_name": "kvp.biblio_id",
        "type": "keyword",
        "display": True,
        "search": True,
        "sort": True
    }
    corpus.save()
    corpus.rebuild_index()

    default_date = datetime(1, 1, 1, 0, 0)

    if os.path.exists(driver_file_path):
        edition = Document(corpus_id)()
        edition.corpus = corpus

        with open(driver_file_path, 'r') as tei_in:
            tei = BeautifulSoup(tei_in, "xml")
            extract_text_replacements(tei_in)

        print(text_replacements)

        tei_root = tei.TEI
        tei_header = tei_root.teiHeader
        file_desc = tei_header.fileDesc
        title_stmt = file_desc.titleStmt

        edition.title = _str(title_stmt.title)
        edition.author = _str(title_stmt.author)

        for editor_tag in title_stmt.find_all('editor'):
            editor = Content(corpus_id, 'Editor')
            editor.fields['name']['value'] = _str(editor_tag)
            editor.fields['role']['value'] = editor_tag['role']
            save_content(editor)

        edition.work = _str(file_desc.editionStmt.edition)

        # check to see if edition already exists
        try:
            existing_edition = Document(corpus_id).objects(corpus=corpus_id, title=edition.title, author=edition.author, work=edition.work)[0]
            edition = existing_edition
            print("Using existing Document for Base Text")
        except:
            print("Creating new Document for Base Text")

        publication_stmt = file_desc.publicationStmt

        edition.kvp['publisher'] = _str(publication_stmt.publisher)
        edition.kvp['address'] = ''

        for addr_line in publication_stmt.address.find_all('addrLine'):
            edition.kvp['address'] += _str(addr_line) + '\n'

        edition.kvp['availability'] = ''

        for avail_p in publication_stmt.find_all('p'):
            edition.kvp['availability'] += _str(avail_p) + '\n'

        edition.kvp['series_title'] = _str(file_desc.seriesStmt.title)

        for name_tag in file_desc.seriesStmt.respStmt.find_all('name'):
            editor = Content(corpus_id, 'Editor')
            editor.fields['name']['value'] = _str(name_tag)
            editor.fields['role']['value'] = "series"
            save_content(editor)

        edition.kvp['project_description'] = _str(tei_header.encodingDesc.projectDesc)

        for lang_tag in tei_header.profileDesc.langUsage.find_all('language'):
            lang = Content(corpus_id, 'Language')
            lang.fields['code']['value'] = lang_tag['ident']
            lang.fields['label']['value'] = _str(lang_tag)
            save_content(lang)

        for change_tag in tei_header.revisionDesc.find_all('change'):
            revision = Content(corpus_id, 'Revision')
            revision.fields['when']['value'] = parser.parse(change_tag['when'], default=default_date)
            revision.fields['who']['value'] = change_tag['who']
            revision.fields['description']['value'] = _str(change_tag)
            save_content(revision)

        edition.save()
        driver_file = process_corpus_file(
            driver_file_path,
            desc='TEI Document Driver File',
            prov_type='NVS Import Data Command',
            prov_id=str(datetime.now().timestamp()))
        if driver_file:
            edition.save_file(driver_file)

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

        include_files_exist = True
        for include_file in include_file_paths.keys():
            full_path = os.path.join(os.path.dirname(driver_file_path), include_file_paths[include_file])
            if os.path.exists(full_path):
                include_file_paths[include_file] = full_path
            else:
                include_files_exist = False
                break

        if include_files_exist:
            parse_front_file(corpus, edition, include_file_paths['front'])
            parse_playtext_file(corpus, edition, include_file_paths['playtext'])


def parse_front_file(corpus, edition, front_file_path):
    with open(front_file_path, 'r') as tei_in:
        tei = BeautifulSoup(tei_in, "xml")

    front = tei.container.front
    plan_of_work = front.find('div', type='potw')

    for witness_list in plan_of_work.find_all('listWit'):
        witness_type = witness_list['xml:id'].replace("listwit_", "")

        for witness_tag in witness_list.find_all('witness'):
            witness_siglum = _str(witness_tag.siglum)
            witness = None

            try:
                witness = Document(corpus.id).objects(corpus=corpus, kvp__witness_siglum=witness_siglum)[0]
            except:
                witness = Document(corpus.id)()
                witness.corpus = corpus
                witness.kvp['witness_siglum'] = witness_siglum

            if witness:
                witness.kvp['witness_type'] = witness_type
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
            

def parse_playtext_file(corpus, edition, playtext_file_path):
    playtext_lines = []

    with open(playtext_file_path, 'r') as tei_in:
        tei = BeautifulSoup(tei_in, "xml")
        tei_in.seek(0)
        playtext_lines = tei_in.readlines()

    cast_list = tei.container.div.div.castList
    for role_tag in cast_list.find_all("role"):
        cast_member = Content(corpus.id, 'CastMember')
        cast_member.fields['xml_id']['value'] = role_tag['xml:id']
        cast_member.fields['role']['value'] = " ".join([string for string in role_tag.stripped_strings])
        if not cast_member.fields['role']['value']:
            cast_member.fields['role']['value'] = cast_member.fields['xml_id']['value']
        save_content(cast_member)

    thru_line_pattern = re.compile(r'<lb xml:id="(tln_[^"]*)" n="([^"]*)"[^\/]*\/>(.*)')
    for line in playtext_lines:
        matches = thru_line_pattern.findall(line)
        if matches:
            thru_line = Content(corpus.id, 'Line')
            thru_line.fields['xml_id']['value'] = matches[0][0]
            thru_line.fields['number']['value'] = matches[0][1]
            thru_line.fields['content']['value'] = matches[0][2]
            save_content(thru_line)


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
                    text_replacements[text] = "&{0};".format(replacement)


def _str(val):
    if val and hasattr(val, 'string'):
        val = str(val.string)
        for text, replacement in text_replacements.items():
            val = val.replace(text, replacement)
        return val
    return ''


def save_content(content):
    try:
        content.save()
    except:
        print("{0} already exists!".format(content.content_type.name))
