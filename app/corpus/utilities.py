import re
import json
import traceback
import requests
import mongoengine
from math import ceil
from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING
from elasticsearch_dsl import Search, Q
from elasticsearch_dsl.query import SimpleQueryString
from elasticsearch_dsl.connections import get_connection
from django.conf import settings
from dateutil import parser


if TYPE_CHECKING:
    from .corpus import Corpus


def get_corpus(corpus_id, only=[]):
    try:
        from .corpus import Corpus
        corpus = Corpus.objects(id=corpus_id)
        if only:
            corpus = corpus.only(*only)
        return corpus[0]
    except:
        return None


def search_corpora(
        search_dict,
        ids=[],
        open_access_only=False
):
    results = {
        'meta': {
            'content_type': 'Corpus',
            'total': 0,
            'page': search_dict['page'],
            'page_size': search_dict['page_size'],
            'num_pages': 1,
            'has_next_page': False
        },
        'records': []
    }

    start_index = (search_dict['page'] - 1) * search_dict['page_size']
    end_index = search_dict['page'] * search_dict['page_size']

    index = "corpora"
    should = []
    must = []
    if search_dict['general_query']:
        should.append(SimpleQueryString(query=search_dict['general_query']))

    if 'fields_query' in search_dict and search_dict['fields_query']:
        for search_field in search_dict['fields_query'].keys():
            must.append(Q('match', **{search_field: search_dict['fields_query'][search_field]}))

    if ids:
        must.append(Q('terms', _id=ids) | Q('match', open_access=True))
    elif open_access_only:
        must.append(Q('match', open_access=True))

    if should or must:
        search_query = Q('bool', should=should, must=must)
        search_cmd = Search(using=get_connection(), index=index, extra={'track_total_hits': True}).query(search_query)
        search_cmd = search_cmd.sort({'name.raw': 'asc'})

        search_cmd = search_cmd[start_index:end_index]
        search_results = search_cmd.execute().to_dict()
        results['meta']['total'] = search_results['hits']['total']['value']
        results['meta']['num_pages'] = ceil(results['meta']['total'] / results['meta']['page_size'])
        results['meta']['has_next_page'] = results['meta']['page'] < results['meta']['num_pages']

        for hit in search_results['hits']['hits']:
            record = deepcopy(hit['_source'])
            record['id'] = hit['_id']
            record['_search_score'] = hit['_score']
            results['records'].append(record)

    return results


def search_scholars(search_dict):
    page = search_dict.get('page', 1)
    page_size = search_dict.get('page_size', 50)
    general_query = search_dict.get('general_query', '*')
    fields_query = search_dict.get('fields_query', None)
    fields_sort = search_dict.get('fields_sort', None)

    results = {
        'meta': {
            'content_type': 'Scholar',
            'total': 0,
            'page': page,
            'page_size': page_size,
            'num_pages': 1,
            'has_next_page': False
        },
        'records': []
    }

    start_index = (page - 1) * page_size
    end_index = page * page_size

    index = "scholar"
    should = []
    must = []
    if general_query:
        should.append(SimpleQueryString(query=general_query))

    if fields_query:
        for search_field in fields_query.keys():
            must.append(Q('match', **{search_field: fields_query[search_field]}))

    if should or must:
        search_query = Q('bool', should=should, must=must)
        search_cmd = Search(using=get_connection(), index=index, extra={'track_total_hits': True}).query(search_query)

        if fields_sort:
            search_cmd = search_cmd.sort(*fields_sort)

        search_cmd = search_cmd[start_index:end_index]
        search_results = search_cmd.execute().to_dict()
        results['meta']['total'] = search_results['hits']['total']['value']
        results['meta']['num_pages'] = ceil(results['meta']['total'] / results['meta']['page_size'])
        results['meta']['has_next_page'] = results['meta']['page'] < results['meta']['num_pages']

        for hit in search_results['hits']['hits']:
            record = deepcopy(hit['_source'])
            record['id'] = hit['_id']
            record['_search_score'] = hit['_score']
            results['records'].append(record)

    return results


def run_neo(cypher, params={}, tries=0):
    results = None
    with settings.NEO4J.session() as neo:
        try:
            results = list(neo.run(cypher, **params))
        except:
            error = traceback.format_exc()
            if 'defunct connection' in error and tries < 3:
                print("Attempting to recover from stale Neo4J connection...")
                neo.close()
                return run_neo(cypher, params, tries + 1)

            print("Error running Neo4J cypher!")
            print("Cypher: {0}".format(cypher))
            print("Params: {0}".format(json.dumps(params, indent=4)))
            print(error)
        finally:
            neo.close()
    return results


def get_network_json(cypher):
    net_json = {
        'nodes': [],
        'edges': [],
    }

    node_id_to_uri_map = {}
    rel_ids = []

    results = run_neo(cypher)

    for result in results:
        graph = result.items()[0][1].graph

        for node in graph.nodes:
            if node.id not in node_id_to_uri_map:
                node_props = {}
                for key, val in node.items():
                    node_props[key] = val

                uri = node_props.get('uri', str(node.id))
                label = node_props.get('label', str(node.id))
                node_type = list(node.labels)[0]

                if node_type == 'Corpus':
                    label = node_props.get('name', str('Corpus'))

                net_json['nodes'].append({
                    'id': uri,
                    'group': node_type,
                    'label': label
                })

                node_id_to_uri_map[node.id] = uri

        for rel in graph.relationships:
            if rel.id not in rel_ids and rel.start_node.id in node_id_to_uri_map and rel.end_node.id in node_id_to_uri_map:
                edge_dict = {
                    'id': str(rel.id),
                    'title': rel.type,
                    'from': node_id_to_uri_map[rel.start_node.id],
                    'to': node_id_to_uri_map[rel.end_node.id],
                }

                intensity = rel.get('intensity')
                if intensity:
                    edge_dict['value'] = intensity

                net_json['edges'].append(edge_dict)

                rel_ids.append(rel.id)

    return net_json


def ensure_neo_indexes(node_names):
    existing_node_indexes = [row['labelsOrTypes'][0] for row in run_neo("SHOW INDEXES", {}) if row['labelsOrTypes']]
    for node_name in node_names:
        if node_name not in existing_node_indexes:
            run_neo("CREATE CONSTRAINT IF NOT EXISTS FOR (ct:{0}) REQUIRE ct.uri IS UNIQUE".format(node_name), {})
            run_neo("CREATE INDEX IF NOT EXISTS FOR (ct:{0}) ON (ct.corpus_id)".format(node_name), {})


def ensure_connection():
    try:
        from .corpus import Corpus
        c = Corpus.objects.count()
    except:
        mongoengine.disconnect_all()
        mongoengine.connect(
            settings.MONGO_DB,
            host=settings.MONGO_HOST,
            username=settings.MONGO_USER,
            password=settings.MONGO_PWD,
            authentication_source=settings.MONGO_AUTH_SOURCE,
            maxpoolsize=settings.MONGO_POOLSIZE
        )


def parse_date_string(date_string):
    default_date = datetime(1, 1, 1, 0, 0)
    date_obj = None

    try:
        date_obj = parser.parse(date_string, default=default_date)
    except:
        pass

    return date_obj

def parse_graph_steps(corpus, graph_path):
    graph_steps = {}

    # check graph path string for any database write keywords
    # which would immediately invalidate the graph path
    write_keywords = [r'\bCREATE\b', r'\bMERGE\b', r'\bDELETE\b', r'\bDETACH\b', r'\bSET\b', r'\bREMOVE\b', r'\bDROP\b', r'\bCALL\b', r'\bLOAD\s+CSV\b', r'\bFOREACH\b']
    test_string = graph_path.upper()
    is_read_only = not any(re.search(pattern, test_string, re.IGNORECASE) for pattern in write_keywords)

    if is_read_only:
        ct_pattern = re.compile(r'\(([a-zA-Z]*)')
        ids_pattern = re.compile(r'\[([^\]]*)\]')

        graph_step_specs = [step for step in graph_path.split(' ') if step]

        for step_index in range(0, len(graph_step_specs)):
            step_spec = graph_step_specs[step_index]
            step_direction = '-->'
            step_ct = None
            step_ids = []

            if '<--' in step_spec:
                step_direction = '<--'

            ct_match = re.search(ct_pattern, step_spec)
            if ct_match:
                step_ct = ct_match.group(1)

            ids_match = re.search(ids_pattern, step_spec)
            if ids_match:
                step_ids = [ct_id for ct_id in ids_match.group(1).split(',') if ct_id]

            if step_ct and step_ct in corpus.content_types:
                graph_steps[step_index] = {
                    'direction': step_direction,
                    'ct': step_ct,
                    'ids': step_ids
                }
            else:
                return {}

    return graph_steps

def build_cypher_from_graph_steps(corpus_id, target_ct, graph_steps):
    cypher = "MATCH (target:{0})".format(target_ct)
    where_clauses = []

    for step_index, step_info in graph_steps.items():
        cypher += " {0} (ct{1}:{2})".format(step_info['direction'], step_index, step_info['ct'])
        if step_info['ids']:
            step_uris = ['/corpus/{0}/{1}/{2}'.format(corpus_id, step_info['ct'], ct_id) for ct_id in
                         step_info['ids']]
            where_clauses.append("ct{0}.uri in ['{1}']".format(
                step_index,
                "','".join(step_uris)
            ))

    if where_clauses:
        cypher += "\nWHERE {0}".format(" AND ".join(where_clauses))

    return cypher

def is_valid_long_lat(longitude, latitude):
    if longitude < -180 or longitude > 180:
        return False
    if latitude < -90 or latitude > 90:
        return False
    return True


def get_field_value_from_path(obj, path):
    path = path.replace('__', '.')
    path_parts = path.split('.')
    value = obj

    for part in path_parts:
        if hasattr(value, part):
            value = getattr(value, part)
        elif part in value:
            value = value[part]
        else:
            return None

    return value


def publish_message(corpus_id, message_type, data={}):
    r = requests.get(f'http://nginx/api/publish/{corpus_id}/{message_type}/', params=data)