import os
import redis
import rdflib
import time
import logging
import traceback
from huey.contrib.djhuey import db_task
from datetime import datetime
from time import sleep
from .content import REGISTRY as ARC_CONTENT_TYPE_SCHEMA
from .content import Ascription
from corpus import *
from viapy.api import ViafAPI


REGISTRY = {
    "Index ARC Archive(s)": {
        "version": "0.2",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "Corpus",
        "configuration": {
            "parameters": {
                "archive_handle": {
                    "value": "",
                    "type": "text",
                    "label": "Handle for a Specific Archive to Index",
                    "note": "May be left blank if number of new archives to index specified below."
                },
                "archives_to_index": {
                    "value": "",
                    "type": "text",
                    "label": "Number of Archives to Index",
                    "note": "If no handle specified, provide number of unindexed archives to index."
                },
                "new_only": {
                    "value": "No",
                    "type": "choice",
                    "choices": ["No", "Yes"],
                    "label": "Only index new archives?",
                    "note": "Selecting 'Yes' will skip indexing for existing archives."
                }
            },
        },
        "module": 'plugins.arc.tasks',
        "functions": ['index_archives']
    },
    "Automated URI Attribution": {
        "version": "0.0",
        "jobsite_type": "HUEY",
        "track_provenance": True,
        "content_type": "ArcAgent",
        "configuration": {},
        "module": 'plugins.arc.tasks',
        "functions": ['guess_agent_uri']
    }
}

archives_dir = '/import/arc_rdf'
rdf_extensions = ['xml', 'rdf']
namespaces = {
    'role': 'http://www.loc.gov/loc.terms/relators/'
}
role_codes = {
    'ART': 'Artist',
    'AUT': 'Author',
    'EDT': 'Editor',
    'PBL': 'Publisher',
    'TRL': 'Translator',
    'ETR': 'Etcher',
    'EGR': 'Engraver',
    'OWN': 'Owner',
    'ARC': 'Architect',
    'BND': 'Binder',
    'BKD': 'Book designer',
    'BKP': 'Book producer',
    'CLL': 'Calligrapher',
    'CTG': 'Cartographer',
    'COL': 'Collector',
    'CLR': 'Colorist',
    'CWT': 'Commentator for Written Text',
    'COM': 'Compiler',
    'CMT': 'Compositor',
    'CRE': 'Creator',
    'DUB': 'Dubious Author',
    'FAC': 'Facsimilist',
    'ILU': 'Illuminator',
    'ILL': 'Illustrator',
    'LTG': 'Lithographer',
    'PRT': 'Printer',
    'POP': 'Printer of Plates',
    'PRM': 'Printmaker',
    'RPS': 'Repository',
    'RBR': 'Rubricator',
    'SCR': 'Scribe',
    'SCL': 'Sculptor',
    'TYD': 'Type Designer',
    'TYG': 'Typographer',
    'WDE': 'Wood Engraver',
    'WDC': 'Wood Cutter',
}


@db_task(priority=2)
def index_archives(job_id):
    job = Job(job_id)
    corpus = job.corpus
    archive_handle = job.configuration['parameters']['archive_handle']['value'].strip()
    num_archives_to_index = job.configuration['parameters']['archives_to_index']['value'].strip()
    new_only = job.configuration['parameters']['new_only']['value'].strip() == 'Yes'
    archives = []

    '''
    for arc_content_type in ARC_CONTENT_TYPE_SCHEMA:
        if delete_existing and arc_content_type['name'] in corpus.content_types:
            corpus.delete_content_type(arc_content_type['name'])
            corpus.save_content_type(arc_content_type)
        elif arc_content_type['name'] not in corpus.content_types:
            corpus.save_content_type(arc_content_type)
    '''

    es_logger = logging.getLogger('elasticsearch')
    es_log_level = es_logger.getEffectiveLevel()
    es_logger.setLevel(logging.WARNING)

    if archive_handle:
        archive, new = get_or_create_archive(corpus, archive_handle)
        if archive and ((new and new_only) or not new_only):
            archives.append(archive)
    elif num_archives_to_index:
        print("Indexing {0} archives...".format(num_archives_to_index))
        num_archives_to_index = int(num_archives_to_index)
        archive_dirs = [archives_dir + '/' + listed_dir for listed_dir in os.listdir(archives_dir) if listed_dir.startswith('arc_rdf_') and os.path.isdir(archives_dir + '/' + listed_dir)]
        for archive_dir in archive_dirs:
            if num_archives_to_index > 0:
                if os.path.exists(archive_dir + '/.git'):
                    archive_handle = os.path.basename(archive_dir).replace('arc_rdf_', '')
                    archive, new = get_or_create_archive(corpus, archive_handle)
                    if archive and ((new and new_only) or not new_only):
                        do_indexing = True

                        if archive.last_indexed:
                            last_modified = datetime.fromtimestamp(os.path.getmtime(archive_dir + '/.git')).date()
                            if archive.last_indexed >= last_modified:
                                print("Skipping {0}: already indexed.".format(archive.handle))
                                do_indexing = False

                        if do_indexing:
                            archives.append(archive)
                            num_archives_to_index -= 1
            else:
                break

    if archives:
        process_merged_agents(corpus)

        for archive in archives:
            huey_task = index_archive(job_id, str(archive.id))
            job.add_process(huey_task.id)

        job.set_status('running')
    else:
        print("No valid candidates for indexing found. Completing job.")
        job.complete(status='complete')

    es_logger.setLevel(es_log_level)


def get_or_create_archive(corpus, handle):
    archive = None
    new = False
    try:
        archive = corpus.get_content('ArcArchive', {'handle': handle})[0]
    except:
        archive = None

    if not archive:
        try:
            archive = corpus.get_content('ArcArchive')
            archive.handle = handle
            archive.save()
            print("Created archive for {0} ({1})".format(archive.handle, archive.id))
            new = True
        except:
            print("Error creating archive:")
            print(traceback.format_exc())

    return archive, new


def process_merged_agents(corpus):
    merge_report_dir = "{0}/files/merge_reports".format(corpus.path)
    if os.path.exists(merge_report_dir):
        merge_files = os.listdir(merge_report_dir)
        for merge_file in merge_files:
            if merge_file.startswith('ArcAgent') and '_merged_into_' in merge_file and merge_file.endswith('.json'):
                merge_file_parts = merge_file.split('_')
                target_id = merge_file_parts[4].replace('.json', '')
                merge_file = "{0}/{1}".format(merge_report_dir, merge_file)
                merged_content = None
                with open(merge_file, 'r') as merged_in:
                    merged_content = json.load(merged_in)
                if merged_content and 'entity' in merged_content and 'name' in merged_content['entity']:
                    alt_name = merged_content['entity']['name']
                    target_agent = corpus.get_content('ArcAgent', target_id, single_result=True)
                    if target_agent:
                        if alt_name not in target_agent.entity.alternate_names:
                            target_agent.entity.alternate_names.append(alt_name)
                            target_agent.entity.save()
                os.rename(merge_file, merge_file + '.processed')


@db_task(priority=1, context=True)
def index_archive(job_id, archive_id, task=None):
    job = Job(job_id)
    corpus = job.corpus
    archive = corpus.get_content('ArcArchive', archive_id)

    es_logger = logging.getLogger('elasticsearch')
    es_log_level = es_logger.getEffectiveLevel()
    es_logger.setLevel(logging.WARNING)

    print("Indexing {0} archive...".format(archive.handle))
    artifacts_indexed = 0
    indexing_started = time.time()
    try:
        cache = redis.Redis(host='redis', decode_responses=True)

        archive_dir = os.path.join(archives_dir, 'arc_rdf_' + archive.handle)
        if os.path.exists(archive_dir) and os.path.isdir(archive_dir):

            temp_file = "{0}/temp-arc-{1}.txt".format(corpus.path, archive.handle)
            if os.path.exists(temp_file):
                os.remove(temp_file)

            find_rdf_in_path(archive_dir, temp_file)

            rdf_files = []
            if os.path.exists(temp_file):
                with open(temp_file, 'r') as temp_in:
                    rdf_files = temp_in.readlines()

            num_failures = 0

            for rdf_file in rdf_files:
                if num_failures > 50:
                    break

                artifacts = parse_rdf(rdf_file.strip())
                for art in artifacts:
                    cached_art_id = get_reference(corpus, art['uri'], 'ArcArtifact', cache, make_new=False)

                    a = None
                    if cached_art_id:
                        a = corpus.get_content('ArcArtifact', cached_art_id)
                    else:
                        a = corpus.get_content('ArcArtifact')
                        a.external_uri = art['uri']

                    if a:
                        try:
                            # clear fields that are lists in case existing artifact
                            a.federations = []
                            a.types = []
                            a.disciplines = []
                            a.genres = []
                            a.agents = []
                            a.years = []
                            a.sources = []
                            a.subjects = []
                            a.coverages = []
                            a.has_parts = []
                            a.is_part_ofs = []
                            a.relateds = []

                            a.url = art['url']
                            a.title = art['title']

                            if 'language' in art:
                                a.language = art['language']
                                
                            a.free_culture = 1 if art['free_culture'] else 0

                            if 'ocr' in art:
                                a.ocr = 1 if art['ocr'] else 0

                            if 'full_text' in art:
                                a.full_text = 1 if art['full_text'] else 0

                            archive_id = get_reference(corpus, art['archive'], 'ArcArchive', cache, make_new=False)
                            if archive_id:
                                a.archive = corpus.get_content_dbref('ArcArchive', archive_id)

                            for fed in art['federations']:
                                federation_id = get_reference(corpus, fed, 'ArcFederation', cache)
                                if federation_id:
                                    a.federations.append(corpus.get_content_dbref('ArcFederation', federation_id))

                            for tp in art['types']:
                                type_id = get_reference(corpus, tp, 'ArcType', cache)
                                if type_id:
                                    a.types.append(corpus.get_content_dbref('ArcType', type_id))

                            for agt in art['people']:
                                agt_key = "{0}_|_{1}".format(agt['name'], agt['role_code'])
                                agent_id = get_reference(corpus, agt_key, 'ArcAgent', cache)
                                if agent_id:
                                    a.agents.append(corpus.get_content_dbref('ArcAgent', agent_id))

                            for dsc in art['disciplines']:
                                discipline_id = get_reference(corpus, dsc, 'ArcDiscipline', cache)
                                if discipline_id:
                                    a.disciplines.append(corpus.get_content_dbref('ArcDiscipline', discipline_id))

                            for gnr in art['genres']:
                                genre_id = get_reference(corpus, gnr, 'ArcGenre', cache)
                                if genre_id:
                                    a.genres.append(corpus.get_content_dbref('ArcGenre', genre_id))

                            for year in art['years']:
                                a.years.append(year)

                            if 'date_label' in art:
                                a.date_label = art['date_label']
                            if 'date_value' in art:
                                a.date_value = art['date_value']

                            if 'alt_title' in art:
                                a.alt_title = art['alt_title']

                            if 'date_of_edition' in art:
                                a.date_of_edition = art['date_of_edition']

                            if 'date_of_review' in art:
                                a.date_of_review = art['date_of_review']

                            if 'description' in art:
                                a.description = art['description']

                            if 'full_text_url' in art:
                                a.full_text_url = art['full_text_url']

                            if 'full_text_contents' in art:
                                a.full_text_contents = art['full_text_contents']

                            if 'image_url' in art:
                                a.image_url = art['image_url']

                            if 'thumbnail_url' in art:
                                a.thumbnail_url = art['thumbnail_url']

                            if 'source_xml' in art:
                                a.source_xml = art['source_xml']

                            if 'source_html' in art:
                                a.source_html = art['source_html']

                            if 'source_sgml' in art:
                                a.source_sgml = art['source_sgml']

                            for subject in art['subjects']:
                                a.subjects.append(subject)

                            for coverage in art['coverages']:
                                a.coverages.append(coverage)

                            for has_part in art['has_parts']:
                                a.has_parts.append(has_part)

                            for is_part_of in art['is_part_ofs']:
                                a.is_part_ofs.append(is_part_of)

                            for related in art['relateds']:
                                a.relateds.append(related)

                            a.save()

                        except:
                            print(traceback.format_exc())
                            num_failures += 1

                artifacts_indexed += len(artifacts)

            archive.last_indexed = datetime.now()
            archive.save()
    except:
        print(traceback.format_exc())

    print("Indexed {0} items in {1} seconds.".format(artifacts_indexed, time.time() - indexing_started))
    es_logger.setLevel(es_log_level)

    if task:
        job.complete_process(task.id)


def find_rdf_in_path(path, temp_file):
    child_dirs = []
    rdf_files = []

    for child_basename in os.listdir(path):
        if not child_basename.startswith('.'):
            child_path = os.path.join(path, child_basename)
            if os.path.isdir(child_path):
                child_dirs.append(child_path)
            elif '.' in child_path and child_path.split('.')[-1].lower() in rdf_extensions:
                rdf_files.append(child_path)

    with open(temp_file, 'a') as temp_out:
        for rdf_file in rdf_files:
            temp_out.write(rdf_file + '\n')

    for child_dir in child_dirs:
        find_rdf_in_path(child_dir, temp_file)


def _str(val):
    if val:
        return str(val)
    return ''


def _get_wildcard_dates(val):
    dates = []
    val = list(val)
    num_wildcards = val.count('u')
    wildcard_counters = []
    for x in range(0, num_wildcards):
        wildcard_counters.append(0)

    for y in range(0, 10 ** num_wildcards):
        dates.append(val.copy())

    for x in range(0, len(dates)):
        wildcard_index = 0
        for y in range(0, len(dates[x])):
            if dates[x][y] == 'u':
                dates[x][y] = str(wildcard_counters[wildcard_index])
                wildcard_index += 1

        counter = int("".join([str(c) for c in wildcard_counters]))
        counter += 1
        wildcard_counters = [int(c) for c in str(counter)]
        while (len(wildcard_counters) < num_wildcards):
            wildcard_counters.insert(0, 0)

    for x in range(0, len(dates)):
        dates[x] = int("".join(dates[x]))

    dates.sort()

    return dates


def _get_date_range(val):
    dates = [d.strip() for d in val.split(',') if str.isdigit(d.strip())]
    if len(dates) == 2:
        return range(int(dates[0]), int(dates[1]) + 1)
    return []


def parse_rdf(rdf_file):
    artifacts = []

    graph = rdflib.Graph()
    graph.parse(rdf_file)

    # build bnode dict
    bnode_uris = [obj for obj in graph.objects() if isinstance(obj, rdflib.term.BNode)]
    bnode_uris = list(set(bnode_uris))
    bnodes = {}
    for bnode_uri in bnode_uris:
        bnodes[str(bnode_uri)] = {
            'type': str(graph.value(bnode_uri, rdflib.term.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type'))),
            'label': str(graph.value(bnode_uri, rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#label'))),
            'value': str(graph.value(bnode_uri, rdflib.term.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#value')))
        }

    artifact_uris = [subj for subj in graph.subjects() if isinstance(subj, rdflib.term.URIRef)]
    artifact_uris = list(set(artifact_uris))

    for artifact_uri in artifact_uris:

        # DEFAULT VALUES FOR AN ARC ARCHIVE
        art = {
            'uri': str(artifact_uri),
            'free_culture': True,
            'federations': [],
            'types': [],
            'people': [],
            'disciplines': [],
            'genres': [],
            'years': [],
            'sources': [],
            'subjects': [],
            'coverages': [],
            'has_parts': [],
            'is_part_ofs': [],
            'relateds': []
        }

        for property_uri, value in graph[artifact_uri]:
            prop = str(property_uri)

            # BROWSER URL
            if prop == 'http://www.w3.org/2000/01/rdf-schema#seeAlso':
                art['url'] = str(value)

            # ARCHIVE
            elif prop == 'http://www.collex.org/schema#archive':
                art['archive'] = str(value)

            # TITLE
            elif prop == "http://purl.org/dc/elements/1.1/title":
                art['title'] = str(value)

            # FEDERATION
            elif prop == 'http://www.collex.org/schema#federation':
                art['federations'].append(str(value))

            # TYPE
            elif prop == 'http://purl.org/dc/elements/1.1/type':
                art['types'].append(str(value))

            # HANDLE ROLE CODES AND PEOPLE
            elif prop.startswith('http://www.loc.gov/loc.terms/relators/'):
                art['people'].append({
                    'name': str(value),
                    'role_code': prop.replace('http://www.loc.gov/loc.terms/relators/', '')
                })

            # DISCIPLINE
            elif prop == 'http://www.collex.org/schema#discipline':
                art['disciplines'].append(str(value))

            # GENRE
            elif prop == 'http://www.collex.org/schema#genre':
                art['genres'].append(str(value))

            # DATE
            elif prop == 'http://purl.org/dc/elements/1.1/date':
                if isinstance(value, rdflib.term.BNode) and str(value) in bnodes:
                    art['date_label'] = bnodes[str(value)]['label'].strip()
                    art['date_value'] = bnodes[str(value)]['value'].strip()
                elif isinstance(value, rdflib.term.Literal):
                    art['date_label'] = str(value).strip()
                    art['date_value'] = str(value).strip()

                if str.isdigit(art['date_value']) and len(art['date_value']) == 4:
                    art['years'].append(int(art['date_value']))
                elif 'u' in art['date_value']:
                    art['years'] += _get_wildcard_dates(art['date_value'])
                elif ',' in art['date_value']:
                    art['years'] += _get_date_range(art['date_value'])

            # ALT TITLE
            elif prop == "http://purl.org/dc/terms/alternative":
                art['alt_title'] = str(value)

            # DESCRIPTION
            elif prop == "http://purl.org/dc/elements/1.1/description":
                art['description'] = str(value)

            # DATE OF EDITION
            elif prop == 'http://www.collex.org/schema#dateofedition':
                art['date_of_edition'] = str(value)

            # DATE OF REVIEW
            elif prop == 'http://www.collex.org/schema#reviewdate':
                art['date_of_review'] = str(value)

            # LANGUAGE
            elif prop == "http://purl.org/dc/elements/1.1/language":
                art['language'] = str(value)

            # SOURCE
            elif prop == "http://purl.org/dc/elements/1.1/source":
                art['sources'].append(str(value))

            # SUBJECTS
            elif prop == "http://purl.org/dc/elements/1.1/subject":
                art['subjects'].append(str(value))

            # COVERAGES
            elif prop in ["http://purl.org/dc/terms/coverage", "http://purl.org/dc/elements/1.1/coverage"]:
                art['coverages'].append(str(value))

            # FREE CULTURE
            elif prop == "http://www.collex.org/schema#freeculture":
                art['free_culture'] = str(value).lower() != 'false'

            # OCR
            elif prop == "http://www.collex.org/schema#ocr":
                art['ocr'] = str(value).lower() != 'false'

            # FULL TEXT (y/n)
            elif prop == "http://www.collex.org/schema#fulltext":
                art['full_text'] = str(value).lower() != 'false'

            # TEXT (contents)
            elif prop == "http://www.collex.org/schema#text":
                txt = str(value).strip()
                if txt:
                    if txt.startswith('http') and ' ' not in txt:
                        art['full_text_url'] = txt
                    else:
                        art['full_text_contents'] = txt

            # SOURCE CODES
            elif prop == "http://www.collex.org/schema#source_xml":
                art['source_xml'] = str(value)
            elif prop == "http://www.collex.org/schema#source_html":
                art['source_html'] = str(value)
            elif prop == "http://www.collex.org/schema#source_sgml":
                art['source_sgml'] = str(value)

            # IMAGE URL
            elif prop == "http://www.collex.org/schema#image":
                art['image_url'] = str(value)

            # THUMBNAIL URL
            elif prop == "http://www.collex.org/schema#thumbnail":
                art['thumbnail_url'] = str(value)

            # HAS PART
            elif prop == "http://purl.org/dc/terms/hasPart":
                art['has_parts'].append(str(value))

            # IS PART OF
            elif prop == "http://purl.org/dc/terms/isPartOf":
                art['is_part_ofs'].append(str(value))

            # RELATION(s)
            elif prop == "http://purl.org/dc/elements/1.1/relation":
                art['relateds'].append(str(value))

            # IGNORE RDF TYPE OF ARTIFACT (not collex type)
            elif prop == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
                pass

            else:
                print("UNHANDLED PROPERTY in {0}".format(rdf_file))
                print("{0} ::: {1}".format(prop, value))

        artifacts.append(art)

    return artifacts


def get_reference(corpus, value, ref_type, cache, make_new=True):
    ref = None

    try:
        single_key_reference_fields = {
            'ArcFederation': {
                'handle': '{0}'
            },
            'ArcArchive': {
                'handle': '{0}'
            },
            'ArcArtifact': {
                'external_uri': '{0}'
            },
            'ArcType': {
                'name': '{0}'
            },
            'ArcDiscipline': {
                'name': '{0}'
            },
            'ArcGenre': {
                'name': '{0}'
            },
            'ArcEntity': {
                'entity_type': 'PERSON',
                'name': '{0}'
            },
            'ArcRole': {
                'name': '{0}'
            }
        }

        prefix = 'corpora_arc_plugin_'
        expiry = 3600

        if value:
            cache_key = "{0}{1}_{2}".format(prefix, ref_type, value)
            cached_ref = cache.get(cache_key)

            if cached_ref:
                return cached_ref
            else:
                ref = None

                if ref_type in single_key_reference_fields:
                    query = {}
                    for field_name in single_key_reference_fields[ref_type].keys():
                        query[field_name] = single_key_reference_fields[ref_type][field_name].format(value)

                    ref_obj = corpus.get_content(ref_type, query, single_result=True)
                    if not ref_obj:
                        if ref_type == 'ArcEntity':
                            alt_ent = corpus.search_content('ArcEntity', page_size=1, fields_filter={'alternate_names': value}, only=['id'])
                            if alt_ent and 'records' in alt_ent and len(alt_ent['records']) == 1:
                                ref = alt_ent['records'][0]['id']
                                make_new = False

                        if make_new:
                            ref_obj = corpus.get_content(ref_type)
                            for field_name in single_key_reference_fields[ref_type].keys():
                                if hasattr(ref_obj, field_name):
                                    setattr(ref_obj, field_name, single_key_reference_fields[ref_type][field_name].format(value))
                            ref_obj.save()
                        else:
                            ref_obj = None

                    if ref_obj:
                        ref = str(ref_obj.id)

                elif ref_type == 'ArcAgent': # need to speak entities instead of people
                    vals = value.split('_|_')
                    if len(vals) == 2:
                        pers_val = get_reference(corpus, vals[0], 'ArcEntity', cache)
                        role_val = get_reference(corpus, vals[1], 'ArcRole', cache)

                        if pers_val and role_val:
                            try:
                                agt = corpus.get_content(ref_type, {'entity': pers_val, 'role': role_val})[0]
                            except:
                                if make_new:
                                    agt = corpus.get_content(ref_type)
                                    agt.entity = corpus.get_content_dbref('ArcEntity', pers_val)
                                    agt.role = corpus.get_content_dbref('ArcRole', role_val)
                                    agt.save()
                                else:
                                    agt = None

                            if agt:
                                ref = str(agt.id)


                if ref:
                    cache.set(cache_key, ref, ex=expiry)
    except:
        print(traceback.format_exc())
        print('''
        ------------------------
            ref_type:   {0}
            value:      {1}
        ------------------------
        
        '''.format(ref_type, value))

    return ref

@db_task(priority=2)
def guess_agent_uri(job_id):
    job = Job(job_id)
    job.set_status('running')
    corpus = job.corpus
    agent_id = job.content_id

    agent = corpus.get_content('ArcAgent', agent_id)

    # if entity's external uri has been verified, don't attempt
    if not agent.entity.external_uri_verified:
        artifacts = corpus.get_content('ArcArtifact', {'agents': agent.id})

        # retrieve an existing attribution
        existing_attribution = None
        try:
            existing_attribution = corpus.get_content('UriAscription', {'corpora_uri': agent.entity.uri})[0]
        except:
            existing_attribution = None

        vapi = ViafAPI()
        persons = vapi.find_person(agent.entity.name)
        sleep(3) # trying to limit rate of VIAF queries

        if persons:
            people_data = []

            for person in persons:
                person_probability = 0

                # RETRIEVE NAMES
                person_names = []
                if 'mainHeadings' in person['recordData'] and 'data' in person['recordData']['mainHeadings']:
                    for name_data in person['recordData']['mainHeadings']['data']:
                        if type(name_data) == dict:
                            person_names.append(name_data['text'])

                # RETRIEVE AND PARSE BIRTH/DEATH DATES
                person_birth_year = None
                person_death_year = None

                if 'birthDate' in person['recordData']:
                    person_birth_date = parse_date_string(person['recordData']['birthDate'])
                    if person_birth_date:
                        person_birth_year = person_birth_date.year

                if 'deathDate' in person['recordData']:
                    if person['recordData']['deathDate'] != '0':
                        person_death_date = parse_date_string(person['recordData']['deathDate'])
                        if person_death_date:
                            person_death_year = person_death_date.year

                # RETRIEVE AUTHORED TITLES
                person_titles = []
                if 'titles' in person['recordData'] and person['recordData']['titles'] and 'work' in person['recordData']['titles']:
                    if type(person['recordData']['titles']['work']) == dict:
                        for work in person['recordData']['titles']['work']:
                            if work and type(work) == dict and 'title' in work:
                                person_titles.append(work['title'])

                # CALCULATE PROBABILITIES/BONUSES
                name_probability = 0
                date_probability = 0
                title_bonus = 0

                # NAME PROBABILITY
                for name in person_names:
                    name_probability += get_match_probability(agent.entity.name, name)

                if name_probability > 0:
                    name_probability = name_probability / len(person_names)

                # DATE PROBABILITY
                date_probability = 0
                for artifact in artifacts:
                    if artifact.years and person_birth_year and min(artifact.years) and in_publication_range(person_birth_year, person_death_year, min(artifact.years)):
                        date_probability += 1

                if date_probability > 0:
                    date_probability = (date_probability / len(artifacts)) * 100

                # TITLE BONUS
                potential_title_matches = []
                for artifact in artifacts:
                    highest_match_probability = 0
                    for person_title in person_titles:
                        match_probability = get_match_probability(artifact.title, person_title)
                        if match_probability > highest_match_probability:
                            highest_match_probability = match_probability

                    if highest_match_probability > 0:
                        potential_title_matches.append(highest_match_probability)

                if potential_title_matches:
                    title_bonus = sum(potential_title_matches) / len(potential_title_matches)

                person_label = "No label available."
                if person_names:
                    person_label = person_names[0]

                people_data.append({
                    'label': person_label,
                    'uri': person.uri,
                    'name_prob': name_probability,
                    'date_prob': date_probability,
                    'title_bonus': title_bonus,
                    'probability': (name_probability + date_probability / 2) + title_bonus
                })

            attribution = corpus.get_content('UriAscription')
            attribution.corpora_uri = agent.entity.uri
            people_data = sorted(people_data, reverse=True, key=lambda person: person['probability'])
            for person_data in people_data:
                asc = Ascription()
                asc.uri = person_data['uri']
                asc.label = person_data['label']
                asc.name_probability = person_data['name_prob']
                asc.date_probability = person_data['date_prob']
                asc.title_score = person_data['title_bonus']
                asc.total_score = person_data['probability']

                attribution.ascriptions.append(asc)

            use_attribution = True

            if existing_attribution:
                if existing_attribution.best_score < attribution.best_score:
                    existing_attribution.delete()
                    sleep(2)
                else:
                    use_attribution = False

            if use_attribution:
                attribution.save()
                agent.entity.external_uri = attribution.best_uri
                agent.entity.save()

    agent.uri_attribution_attempted = True
    agent.save()
    job.complete(status='complete')


def get_match_probability(str1, str2):
    probability = 0

    strip_chars = ['.', ',', ':']
    for strip_char in strip_chars:
        str1 = str1.replace(strip_char, '')
        str2 = str2.replace(strip_char, '')

    str1_parts = str1.lower().split()
    str2_parts = str2.lower().split()

    for str1_part in str1_parts:
        if str1_part in str2_parts:
            probability += 1

    if probability > 0 and len(str1_parts) > 0:
        probability = (probability / len(str1_parts)) * 100

    return probability


def in_publication_range(birth, death, pub_date):
    in_range = False

    if pub_date > birth:
        if death:
            if pub_date <= death:
                in_range = True
        else:
            in_range = True

    return in_range