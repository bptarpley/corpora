import os
import redis
from bs4 import BeautifulSoup
from .content import REGISTRY as ARC_CONTENT_TYPE_SCHEMA
from corpus import *
import time
import logging

REGISTRY = {
    "Index ARC Archive(s)": {
        "version": "0.0",
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
            },
        },
        "module": 'plugins.arc.tasks',
        "functions": ['index_archives']
    },
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


def index_archives(job_id):
    job = Job(job_id)
    corpus = job.corpus
    archive_handle = job.configuration['parameters']['archive_handle']['value']
    num_archives_to_index = job.configuration['parameters']['archives_to_index']['value']
    archives = []

    # FOR TESTING ONLY! REMOVE IN PROD
    for arc_content_type in ARC_CONTENT_TYPE_SCHEMA:
        if arc_content_type['name'] in corpus.content_types:
            corpus.delete_content_type(arc_content_type['name'])

        corpus.save_content_type(arc_content_type)

    es_logger = logging.getLogger('elasticsearch')
    es_log_level = es_logger.getEffectiveLevel()
    es_logger.setLevel(logging.WARNING)


    if archive_handle:
        archive = get_or_create_archive(corpus, archive_handle)
        if archive:
            archives.append(archive)
    elif num_archives_to_index:
        num_archives_to_index = int(num_archives_to_index)
        archive_dirs = [archives_dir + '/' + listed_dir for listed_dir in os.listdir(archives_dir) if listed_dir.startswith('arc_rdf_') and os.path.isdir(archives_dir + '/' + listed_dir)]
        for archive_dir in archive_dirs:
            if num_archives_to_index > 0:
                if os.path.exists(archive_dir + '/.git'):
                    archive_handle = os.path.basename(archive_dir).replace('arc_rdf_', '')
                    archive = get_or_create_archive(corpus, archive_handle)
                    if archive:
                        do_indexing = True

                        if archive.last_indexed:
                            last_modified = datetime.fromtimestamp(os.path.getmtime(archive_dir + '/.git')).date()
                            if archive.last_indexed >= last_modified:
                                do_indexing = False

                        if do_indexing:
                            archives.append(archive)
                            num_archives_to_index -= 1
            else:
                break

    for archive in archives:
        index_archive(corpus, archive)

    es_logger.setLevel(es_log_level)


def get_or_create_archive(corpus, handle):
    archive = None
    archive_path = archives_dir + '/arc_rdf_' + handle
    if os.path.exists(archive_path):
        try:
            archive = corpus.get_content('ArcArchive', {'handle': handle})[0]
        except:
            archive = None

        if not archive:
            archive = corpus.get_content('ArcArchive')
            archive.handle = handle
            archive.save()
    return archive


def index_archive(corpus, archive):
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

                artifacts = parse_rdf_file(rdf_file.strip())
                for art in artifacts:
                    cached_art_id = get_reference(corpus, art['uri'], 'ArcArtifact', cache, make_new=False)

                    a = None
                    if cached_art_id:
                        a = corpus.get_content('ArcArtifact', cached_art_id)
                    else:
                        a = corpus.get_content('ArcArtifact')
                        a.permanent_uri = art['uri']

                    if a:
                        try:
                            # clear fields that are lists
                            a.federations = []
                            a.types = []
                            a.disciplines = []
                            a.genres = []
                            a.agents = []
                            a.years = []
                            a.sources = []
                            a.subjects = []
                            a.coverages = []
                            a.source_codes = []

                            a.url = art['url']
                            a.title = art['title']
                            a.language = art['language']
                            a.free_culture = 1 if art['free_culture'] else 0
                            a.ocr = 1 if art['ocr'] else 0
                            a.full_text = 1 if art['full_text'] else 0

                            archive_id = get_reference(corpus, art['archive'], 'ArcArchive', cache)
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

                            if 'image_url' in art:
                                a.image_url = art['image_url']

                            if 'thumbnail_url' in art:
                                a.thumbnail_url = art['thumbnail_url']

                            for source in art['sources']:
                                a.sources.append(source)

                            for subject in art['subjects']:
                                a.subjects.append(subject)

                            for coverage in art['coverages']:
                                a.coverages.append(coverage)

                            for sc_type in art['source_code'].keys():
                                a.source_codes.append("{0}::{1}".format(sc_type, art['source_code'][sc_type]))

                            a.save()

                        except:
                            print(traceback.format_exc())
                            num_failures += 1

                artifacts_indexed += len(artifacts)
    except:
        print(traceback.format_exc())

    print("Indexed {0} items in {1} seconds.".format(artifacts_indexed, time.time() - indexing_started))


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


def parse_rdf_file(rdf_file):
    entry_data = []
    if os.path.exists(rdf_file):
        with open(rdf_file, 'r') as rdf_in:
            rdf = BeautifulSoup(rdf_in, "xml")

        rdf_root = rdf.RDF
        item_tag = None
        unique_child_tags = list(set([item.name for item in rdf_root.contents if item.name]))

        if len(unique_child_tags) == 1:
            item_tag = unique_child_tags[0]

        if item_tag:
            for entry in rdf_root.find_all(item_tag):
                try:
                    data = {}

                    # REQUIRED FIELDS
                    data['uri'] = entry['rdf:about']

                    see_also = entry.seeAlso
                    if see_also:
                        if 'rdf:resource' in see_also.attrs:
                            data['url'] = entry.seeAlso['rdf:resource']
                        else:
                            data['url'] = _str(see_also.string)

                    data['archive'] = _str(entry.archive.string)
                    data['title'] = _str(entry.title.string)

                    data['federations'] = []
                    for federation in entry.find_all('federation'):
                        data['federations'].append(_str(federation.string))

                    data['types'] = []
                    for tipe in entry.find_all('type'):
                        data['types'].append(_str(tipe.string))

                    data['people'] = []
                    for role in entry.select('role|*', namespaces=namespaces):
                        data['people'].append({
                            'name': _str(role.string),
                            'role_code': _str(role.name),
                        })

                    data['disciplines'] = []
                    for discipline in entry.find_all('discipline'):
                        data['disciplines'].append(_str(discipline.string))

                    data['genres'] = []
                    for genre in entry.find_all('genre'):
                        data['genres'].append(_str(genre.string))

                    data['years'] = []
                    for date in entry.find_all('date'):
                        date_string = None
                        if date.string:
                            date_string = _str(date.string).strip()
                        elif date.date and date.date.value:
                            date_string = _str(date.date.value.string).strip()

                        if date_string:
                            if str.isdigit(date_string) and len(date_string) == 4:
                                data['years'].append(int(date_string))
                            elif 'u' in date_string:
                                data['years'] += _get_wildcard_dates(date_string)
                            elif ',' in date_string:
                                data['years'] += _get_date_range(date_string)

                    # OPTIONAL FIELDS
                    if entry.alternative:
                        data['alt_title'] = _str(entry.alternative.string)

                    if entry.dateofedition:
                        data['date_of_edition'] = _str(entry.dateofedition.string)

                    if entry.reviewdate:
                        data['date_of_review'] = _str(entry.reviewdate.string)

                    if entry.description:
                        data['description'] = _str(entry.description.string)

                    data['language'] = 'English'
                    if entry.language:
                        data['language'] = _str(entry.language.string)

                    data['sources'] = []
                    for source in entry.find_all('source'):
                        data['sources'].append(_str(source.string))

                    data['subjects'] = []
                    for subject in entry.find_all('subject'):
                        data['subjects'].append(_str(subject.string))

                    data['coverages'] = []
                    for coverage in entry.find_all('coverage'):
                        data['coverages'].append(_str(coverage.string))

                    data['free_culture'] = True
                    if entry.freeculture:
                        data['free_culture'] = _str(entry.freeculture.string).lower() != 'false'

                    data['ocr'] = False
                    if entry.ocr:
                        data['ocr'] = _str(entry.ocr.string).lower() == 'true'

                    data['full_text'] = False
                    if entry.fulltext:
                        data['full_text'] = _str(entry.fulltext.string).lower() == 'true'

                    data['source_code'] = {}
                    if entry.source_xml:
                        data['source_code']['xml'] = _str(entry.source_xml.string)
                    if entry.source_html:
                        data['source_code']['html'] = _str(entry.source_html.string)
                    if entry.source_html:
                        data['source_code']['sgml'] = _str(entry.source_sgml.string)

                    if entry.text and 'rdf:resource' in entry.text:
                        data['full_text_url'] = entry.text['rdf:resource']

                    if entry.image and 'rdf:resource' in entry.image:
                        data['image_url'] = entry.image['rdf:resource']

                    if entry.thumbnail and 'rdf:resource' in entry.thumbnail:
                        data['thumbnail_url'] = entry.thumbnail['rdf:resource']

                    # LINKED DATA
                    data['lod'] = []
                    for hasPart in entry.find_all('hasPart'):
                        if 'rdf:resource' in hasPart:
                            data['lod'].append({
                                'predicate': 'hasPart',
                                'object': hasPart['rdf:resource']
                            })

                    for isPartOf in entry.find_all('isPartOf'):
                        if 'rdf:resource' in isPartOf:
                            data['lod'].append({
                                'predicate': 'isPartOf',
                                'object': isPartOf['rdf:resource']
                            })

                    for relation in entry.find_all('relation'):
                        if 'rdf:resource' in relation:
                            data['lod'].append({
                                'predicate': 'relation',
                                'object': relation['rdf:resource']
                            })

                    entry_data.append(data)
                except:
                    print(traceback.format_exc())
                    print(entry)

    return entry_data


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
                'permanent_uri': '{0}'
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
                if ref_type in single_key_reference_fields:
                    query = {}
                    for field_name in single_key_reference_fields[ref_type].keys():
                        query[field_name] = single_key_reference_fields[ref_type][field_name].format(value)

                    try:
                        ref_obj = corpus.get_content(ref_type, query)[0]
                    except:
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

                elif ref_type == 'ArcAgent': # need to speak entitites instead of people
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
                                    agt.entity = corpus.get_content_dbref('ArcPerson', pers_val)
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