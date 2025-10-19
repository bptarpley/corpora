import os
import shutil
import json
import logging
import traceback
import mongoengine
import redis
from math import ceil
from datetime import datetime
from datetime import datetime, timedelta
from copy import deepcopy
from typing import TYPE_CHECKING
from bson import ObjectId, DBRef
from elasticsearch_dsl import (
    Index, Mapping, analyzer,
    GeoPoint, GeoShape, Nested,
    Q, A, Search
)
from elasticsearch_dsl.connections import get_connection
from django.conf import settings
from .utilities import run_neo, parse_date_string, is_valid_long_lat, ensure_neo_indexes
from .field_types.file import File
from .field_types.gitrepo import GitRepo
from .content_type import ContentType, ContentTypeGroup, ContentTemplate
from .content import Content, ContentView
from .field import Field
from .job import Job, JobSite, Task, CompletedTask


# to avoid circular dependency between Scholar and Corpus classes:
if TYPE_CHECKING:
    from .scholar import Scholar


class Corpus(mongoengine.Document):
    """
    Primary container for content, analogous to a database in traditional RDBMS.

    A Corpus contains multiple ContentTypes and manages their schemas, relationships,
    and storage across MongoDB, Elasticsearch, and Neo4j. It provides methods for
    content CRUD operations, searching, and schema management.

    Attributes:
        name (str): Unique name for the corpus.
        description (str): Human-readable description.
        uri (str): Unique resource identifier, auto-generated as /corpus/{id}.
        path (str): File system path for corpus data storage.
        kvp (dict): Key-value pairs for arbitrary metadata.
        files (dict[str, File]): Files attached to the corpus itself.
        repos (dict[str, GitRepo]): Git repositories associated with the corpus.
        open_access (bool): Whether the corpus is publicly accessible.
        content_types (dict[str, ContentType]): Content type definitions by name.
        content_type_groups (list[ContentTypeGroup]): Groupings for UI organization.
        provenance (list[CompletedTask]): Audit trail of completed tasks.

    Examples:
        >>> # Create a new corpus
        >>> corpus = Corpus(
        ...     name="Digital Library",
        ...     description="Repository of academic papers and books"
        ... )
        >>> corpus.save()

        >>> # Define a content type
        >>> schema = {
        ...     'name': 'Book',
        ...     'plural_name': 'Books',
        ...     'fields': [
        ...         {'name': 'title', 'type': 'text', 'label': 'Title'},
        ...         {'name': 'isbn', 'type': 'keyword', 'label': 'ISBN', 'unique': True}
        ...     ]
        ... }
        >>> corpus.save_content_type(schema)
    """

    name = mongoengine.StringField(unique=True)
    description = mongoengine.StringField()
    uri = mongoengine.StringField(unique=True)
    path = mongoengine.StringField()
    kvp = mongoengine.DictField()
    files = mongoengine.MapField(mongoengine.EmbeddedDocumentField(File))
    repos = mongoengine.MapField(mongoengine.EmbeddedDocumentField(GitRepo))
    open_access = mongoengine.BooleanField(default=False)
    content_types = mongoengine.MapField(mongoengine.EmbeddedDocumentField(ContentType))
    content_type_groups = mongoengine.ListField(mongoengine.EmbeddedDocumentField(ContentTypeGroup))
    provenance = mongoengine.EmbeddedDocumentListField(CompletedTask)

    def save_file(self, file):
        self.modify(**{'set__files__{0}'.format(file.key): file})
        file._do_linking(content_type='Corpus', content_uri=self.uri)

    def get_content(self, content_type, content_id_or_query={}, only=[], exclude=[], all=False, single_result=False):
        """Retrieve one or more instances of content of a specific Content Type.

        Args:
            content_type (str): A string representing the name of a Content Type in your corpus.
            content_id_or_query (str | ObjectId | dict): A string representation of a BSON ObjectId, a BSON ObjectId, or a dictionary specifying your content query.
            only (list): A list of content field names (strings) to exclusively return.
            exclude (list): A list of content field names (strings) to exclude.
            all (bool): A flag specifying whether you want all content for this content type.
            single_result (bool): A flag specifying whether you expect a single instance of content.

        Returns:
            A MongoEngine QuerySet if multiple results, a MongoEngine Document if a single result, or `None` if no matching content found.

        Examples:
            Create an instance of content:

            >>> content = my_corpus.get_content('Document')
            >>> content.title = "On Beauty"
            >>> content.author = "Zadie Smith"
            >>> content.save()

            Query for a single piece of content with the ID known:

            >>> content = my_corpus.get_content('Document', '5f623f2a52023c009d73108e')
            >>> print(content.title)
            "On Beauty"

            Query for a single piece of content by field value:

            >>> content = my_corpus.get_content('Document', {'title': "On Beauty"}, single_result=True)

            Query for multiple pieces of content by field value:

            >>> contents = my_corpus.get_content('Document', {'author': "Zadie Smith"})
            >>> for content in contents:
            >>>     print(content.title)
            "White Teeth"
            "On Beauty"

            Query for all content with this Content Type:

            >>> contents = my_corpus.get_content('Document', all=True)
        """

        content = None

        if content_type in self.content_types:
            content_obj = self.content_types[content_type].get_mongoengine_class(self)

            if content_id_or_query or all:
                if type(content_id_or_query) is str or type(content_id_or_query) is ObjectId:
                    single_result = True
                    content_id_or_query = {'id': content_id_or_query}

                try:
                    content = content_obj.objects(**content_id_or_query)
                    if only:
                        content = content.only(*only)
                    if exclude:
                        content = content.exclude(*exclude)
                    if single_result:
                        content = content[0]
                except:
                    return None
            else:
                content = content_obj()
                content.corpus_id = str(self.id)
                content.content_type = content_type

        return content

    def get_or_create_content(self, content_type, fields={}, use_cache=False):
        """
        Retrieve existing content or create new if not found.

        Useful for ensuring unique content based on field values, with optional
        Redis caching for performance.

        Args:
            content_type (str): Name of the Content Type.
            fields (dict): Field values to match or set.
            use_cache (bool): Whether to use Redis cache. Defaults to False.

        Returns:
            Content: Existing or newly created content instance.
        """

        content = None
        cache_key = None

        if use_cache:
            cache_key = "/corpus/{0}/cached-{1}:{2}".format(
                self.id,
                content_type,
                json.dumps(fields)
            )
            content_id = self.redis_cache.get(cache_key)
            if content_id:
                content = self.get_content(content_type, content_id)

        if not content:
            content = self.get_content(content_type, fields, single_result=True)
            if content and cache_key:
                self.redis_cache.set(cache_key, str(content.id), ex=settings.REDIS_CACHE_EXPIRY_SECONDS)
            elif not content:
                content = self.get_content(content_type)
                content.from_dict(fields)
                content.save()
                content._newly_created = True

                if cache_key:
                    self.redis_cache.set(cache_key, str(content.id), ex=settings.REDIS_CACHE_EXPIRY_SECONDS)

        return content

    def make_link(self, source_uri, target_uri, link_label, link_attrs={}, cardinality=3):
        """
        Creates a labelled edge between two content nodes in Neo4J.

        Useful for creating relationships manually between two arbitrary pieces of content.
        NOTE: Currently, all outbound relationships for a node are deleted and recreated
        when the content it represents is saved/modified somehow using the Corpus API.
        Arbitrary links are NOT recreated at this time, thus it is recommended that these
        links have a "cardinality" of either 0 (undirected) or 3 (bidirectional) so they
        aren't unintentionally deleted when either piece of content in the relationship
        is modified.

        Args:
            source_uri (str): The URI for a piece of content to be considered the source.
            target_uri (str): The URI for a piece of content to be considered the target.
            link_label (str): The label to be affixed to the edge created.
            link_attrs (dict): A dictionary of attributes to add to the edge created (all values must be serializable).
            cardinality (int): A value from 0-3, defaults to 3. Value 0 makes edge undirected, 1 makes it directed from source to target, 2 makes it directed from target to source, and 3 makes it bidirectional.

        Returns:
            None
        """

        # cardinality values:
        # 0: source --- target
        # 1: source --> target
        # 2: source <-- target
        # 3: source <-> target

        source_uri_parts = [part for part in source_uri.split('/') if part]
        target_uri_parts = [part for part in target_uri.split('/') if part]

        if len(source_uri_parts) == 4 and len(target_uri_parts) == 4:
            if source_uri_parts[1] == str(self.id) and target_uri_parts[1] == source_uri_parts[1]:

                source_content_type = source_uri_parts[2]
                target_content_type = target_uri_parts[2]

                if source_content_type in self.content_types and target_content_type in self.content_types:

                    relationship_start = '-'
                    relationship_end = '->'

                    if cardinality == 0:
                        relationship_end = '-'
                    elif cardinality == 2:
                        relationship_start = '<-'
                        relationship_end = '-'
                    elif cardinality == 3:
                        relationship_start = '<-'

                    link_attr_string = ""
                    if link_attrs:
                        first_attr = True
                        link_attr_string = " { "
                        for key in link_attrs.keys():
                            if not first_attr:
                                link_attr_string += ", "
                            else:
                                first_attr = False

                            link_attr_string += "{0}: ".format(key)
                            if hasattr(link_attrs[key], 'append'):
                                link_attr_string += json.dumps(link_attrs[key])
                            else:
                                link_attr_string += link_attrs[key]
                        link_attr_string += " }"

                    cypher = '''
                        MATCH (src:{source_content_type} {{ uri: $source_uri }})
                        MATCH (trg:{target_content_type} {{ uri: $target_uri }})
                        MERGE (src) {rel_start}[rel:{link_label}{link_props}]{rel_end} (trg)
                    '''.format(
                        source_content_type=source_content_type,
                        target_content_type=target_content_type,
                        rel_start=relationship_start,
                        rel_end=relationship_end,
                        link_label=link_label,
                        link_props=link_attr_string
                    )

                    run_neo(
                        cypher,
                        {
                            'source_uri': source_uri,
                            'target_uri': target_uri
                        }
                    )

    def get_content_dbref(self, content_type, content_id):
        """
        Retrieves a MongoDB-friendly ObjectID reference to a document in a collection.

        Useful for setting the value of a cross-reference field without having to first obtain
        an instance of the content. Particularly useful when bulk creating large amounts of content.

        Args:
            content_type (str): Name of the Content Type.
            content_id (str | ObjectId): A string representation of a BSON ObjectId or a BSON ObjectId.

        Returns:
            A MongoDB DBRef: https://www.mongodb.com/docs/manual/reference/database-references/

        Examples:
           >>> # Avoid having to query the database for content of type Author before setting it as
           >>> # the value of a cross-reference field:
           >>> author = my_corpus.get_content_dbref('Author', '5f623f2a52023c009d73108e')
           >>> book.author = author
           >>> book.save()
        """

        if not type(content_id) == ObjectId:
            content_id = ObjectId(content_id)
        return DBRef(
            "corpus_{0}_{1}".format(self.id, content_type),
            content_id
        )

    def get_referencing_content_type_fields(self, content_type):
        """
        Retrieve any fields (and the content types they belong to) of type cross-reference
        that reference a particular content type.

        Useful for determining how exactly other content may be referencing content of this type.

        Args:
            content_type (str): Name of the Content Type.

        Returns:
            A dictionary where the keys are the names of content types and the values are a list
            of field objects of type cross-reference that reference this content type, or an empty list.
        """

        referencing = {}
        for ct in self.content_types.keys():
            for field in self.content_types[ct].fields:
                if field.type == 'cross_reference' and field.cross_reference_type == content_type:
                    if ct not in referencing:
                        referencing[ct] = []
                    referencing[ct].append(field)
        return referencing

    def search_content(
            self,
            content_type,
            page=1,
            page_size=50,
            general_query="",
            fields_query={},
            fields_term={},
            fields_phrase={},
            fields_wildcard={},
            fields_filter={},
            fields_range={},
            fields_highlight=[],
            fields_exist=[],
            fields_sort=[],
            only=[],
            excludes=[],
            content_view=None,
            grouped_searches=[],
            operator="and",
            highlight_num_fragments=5,
            highlight_fragment_size=100,
            only_highlights=False,
            aggregations={},
            next_page_token=None,
            es_debug=False,
            es_debug_query=False,
            generate_query_only=False
    ):
        """
        Perform advanced search on content using Elasticsearch.

        Supports full-text search, field-specific queries, filtering, sorting,
        highlighting, and aggregations. Results are paginated and include metadata. This function
        is generally called after translating GET param style key/value pairs formatted according
        to the search REST API, but can of course be called directly.

        Args:
            content_type (str): Name of the Content Type to search.
            page (int): Page number for results (1-based). Defaults to 1.
            page_size (int): Results per page. Defaults to 50.
            general_query (str): A generalized, field-type aware search across all indexed fields.
            fields_query (dict): Field-specific, type-aware searches.
            fields_term (dict): Field-specific exact term matching.
            fields_phrase (dict): Field-specific exact phrase matching.
            fields_wildcard (dict): Field-specific wildcard pattern matching.
            fields_filter (dict): Field-specific filtering without scoring.
            fields_range (dict): Field-specific range queries (numeric, date, geo).
            fields_highlight (list): Fields to highlight matches in.
            fields_exist (list): Fields that must have values.
            fields_sort (list): Field sort specifications.
            only (list): Fields to include in results (excluding all others).
            excludes (list): Fields to exclude from results.
            content_view (str): The ID of a ContentView to use for filtering results.
            grouped_searches (list): Sub-queries for combining with boolean logic.
            operator (str): Boolean operator for entire query ('and' or 'or').
            highlight_num_fragments (int): Number of fragments in results to highlight (for use with fields_highlight).
            highlight_fragment_size (int): The max character length of any highlighted fragments.
            only_highlights (bool): Whether to restrict results to matches that have highlights. Defaults to False.
            aggregations (dict): Elasticsearch aggregations to perform.
            next_page_token (str): Token for deep pagination.
            es_debug (bool): Whether to print out both the Elasticsearch query and the results to stdout inside the Corpora container. Defaults to False.
            es_debug_query (bool): Whether to print to stdout only the Elasticsearch query. Defaults to False.
            generate_query_only (bool): Whether to only return the Elasticsearch query without running it. Defaults to False.

        Returns:
            dict: Search results with structure:
                {
                    'meta': {
                        'total': int,
                        'page': int,
                        'page_size': int,
                        'num_pages': int,
                        'has_next_page': bool,
                        'aggregations': dict
                    },
                    'records': list[dict]
                }

        Examples:
            >>> # Simple text search
            >>> results = corpus.search_content(
            ...     'Article',
            ...     general_query="machine learning",
            ...     page_size=20
            ... )

            >>> # Complex field-specific search with aggregations
            >>> results = corpus.search_content(
            ...     'Article',
            ...     fields_filter={'status': 'published'},
            ...     fields_range={'date': '2020-01-01to2023-12-31'},
            ...     fields_sort=[{'date': {'order': 'desc'}}],
            ...     aggregations={
            ...         'by_author': A('terms', field='author.label.raw', size=10)
            ...     }
            ... )
        """

        results = {
            'meta': {
                'content_type': content_type,
                'total': 0,
                'page': page,
                'page_size': page_size,
                'num_pages': 1,
                'has_next_page': False,
                'aggregations': {}
            },
            'records': []
        }

        if content_type in self.content_types:

            start_index = (page - 1) * page_size
            end_index = page * page_size

            index_name = "corpus-{0}-{1}".format(self.id, content_type.lower())
            index = Index(index_name)
            should = []
            must = []
            must_not = []
            filter = []

            if grouped_searches:
                for grouped_search_params in grouped_searches:
                    grouped_search_params['generate_query_only'] = True
                    grouped_search = self.search_content(
                        content_type=content_type,
                        **grouped_search_params
                    )

                    if grouped_search:
                        if operator == 'and':
                            must.append(grouped_search)
                        elif operator == 'or':
                            should.append(grouped_search)

            # HELPER FUNCTIONS
            def determine_local_operator(search_field, operator):
                if search_field.endswith('+') or search_field.endswith(' '):
                    return search_field[:-1], "and"
                elif search_field.endswith('|'):
                    return search_field[:-1], "or"
                elif search_field.endswith('-'):
                    return search_field[:-1], "exclude"
                return search_field, operator

            def generate_default_queries(query, query_ct, field=None, nested_prefix=''):
                # Since we want the general query to search all fields (including nested ones),
                # we need to break out nested fields from top level ones so we can search them.
                # We must also separate out date/timespan fields since they need to be treated differently.

                top_fields = []
                numeric_fields = []
                date_fields = []
                timespan_fields = []
                nested_fields = []
                keyword_fields = []
                general_queries = []
                final_query = None

                # make sure labels are searched
                if not field:
                    top_fields.append('label')

                # determine what kinds of fields this search is eligible for
                valid_field_types = ['text', 'large_text', 'html']

                # try date
                date_query_value = parse_date_string(query)
                date_query_end_value = None
                if date_query_value:
                    date_query_value = date_query_value.isoformat()
                    # see if we're dealing with just a year so we
                    # can include the beginning and end of year as a range
                    if len(query) == 4 and query.isdecimal():
                        date_query_end_value = parse_date_string(f"12/31/{query}").isoformat()

                if field and field in ['label', 'uri', 'id']:
                    top_fields.append(f"{nested_prefix}{field}")
                else:
                    candidate_fields = [f for f in self.content_types[query_ct].fields if
                                        (not field) or f.name == field]
                    for f in candidate_fields:
                        if f.in_lists:
                            # we shouldn't include xref fields if nested_prefix exists (this indicates we're already in a nested context)
                            if f.type == 'cross_reference' and not nested_prefix:
                                nested_fields.append(f.name)

                            elif f.type in ['number', 'decimal'] and (
                                    query.isdecimal() or query.replace('.', '').isdecimal()):
                                numeric_fields.append(f.name)

                            elif f.type == 'date':
                                date_fields.append(f"{nested_prefix}{f.name}")

                            elif f.type == 'timespan':
                                timespan_fields.append(f"{nested_prefix}{f.name}")

                            elif f.type == 'keyword':
                                keyword_fields.append(f"{nested_prefix}{f.name}")

                            elif f.type in valid_field_types:
                                top_fields.append(f"{nested_prefix}{f.name}")

                # top level fields can be handled by a single simple query string search
                if top_fields:
                    general_queries.append(
                        {'simple_query_string': {'query': query.strip() + '*', 'fields': top_fields}})
                    general_queries.append({'simple_query_string': {'query': query.strip(), 'fields': top_fields}})

                # numeric fields can be similarly handled, but can't have a wildcard appended to the query
                if numeric_fields:
                    general_queries.append({'simple_query_string': {'query': query.strip(), 'fields': numeric_fields}})

                # keyword fields can only be searched using term and wildcard queries because they're not analyzed
                for keyword_field in keyword_fields:
                    general_queries.append({'term': {keyword_field: query.strip()}})
                    general_queries.append({'wildcard': {keyword_field: query.strip() + '*'}})

                # nested fields, however, must each receive their own nested query.
                for nested_field in nested_fields:
                    general_queries.append({
                        'nested': {
                            'path': nested_field,
                            'query': {
                                'simple_query_string': {
                                    'query': query.strip() + '*', 'fields': [f"{nested_field}.label"]
                                }
                            }
                        }
                    })

                # date fields should use the converted value, and possibly a range query
                if date_fields and date_query_value:
                    if date_query_end_value:
                        for date_field in date_fields:
                            general_queries.append({
                                'range': {
                                    date_field: {
                                        'gte': date_query_value,
                                        'lte': date_query_end_value
                                    }
                                }
                            })
                    else:
                        general_queries.append({
                            'simple_query_string': {
                                'query': date_query_value,
                                'fields': date_fields
                            }
                        })

                if timespan_fields and date_query_value:
                    for timespan_field in timespan_fields:
                        timespan_query = generate_timespan_query(
                            timespan_field,
                            date_query_value,
                            date_query_end_value
                        )
                        if timespan_query:
                            general_queries.append(timespan_query)

                # now that we've built our various queries, let's OR them together if necessary:
                if len(general_queries) > 1:
                    final_query = {
                        'bool': {
                            'should': general_queries
                        }
                    }
                elif general_queries:
                    final_query = general_queries[0]

                return final_query

            def generate_timespan_query(timespan_field, date_query_value, date_query_end_value=None,
                                        include_all_before_or_after=False):
                should_queries = []

                # create the various ingredients for creating queries depending on the situation
                ts_end_exists = {
                    'exists': {
                        'field': f"{timespan_field}.end",
                    }
                }
                ts_start_lte_dq_start = {
                    'range': {
                        f"{timespan_field}.start": {
                            'lte': date_query_value
                        }
                    }
                }
                ts_start_gte_dq_start = {
                    'range': {
                        f"{timespan_field}.start": {
                            'gte': date_query_value
                        }
                    }
                }
                ts_end_gte_dq_start = {'range': {
                    f"{timespan_field}.end": {
                        'gte': date_query_value
                    }
                }}
                ts_start_lte_dq_end = {
                    'range': {
                        f"{timespan_field}.start": {
                            'lte': date_query_end_value
                        }
                    }
                }
                ts_end_gte_dq_end = {
                    'range': {
                        f"{timespan_field}.end": {
                            'gte': date_query_end_value
                        }
                    }
                }
                ts_end_lte_dq_end = {
                    'range': {
                        f"{timespan_field}.end": {
                            'lte': date_query_end_value
                        }
                    }
                }

                # if we're matching all timespans before or after a date
                if include_all_before_or_after:
                    if date_query_value and not date_query_end_value:
                        ts_with_end = {
                            'bool': {
                                'must': [ts_end_exists, ts_end_gte_dq_start]
                            }
                        }
                        ts_no_end = {
                            'bool': {
                                'must_not': [ts_end_exists],
                                'must': [ts_start_gte_dq_start]
                            }
                        }
                        should_queries = [ts_with_end, ts_no_end]

                    elif date_query_end_value and not date_query_value:
                        should_queries.append({
                            'bool': {
                                'must': [ts_end_exists, ts_start_lte_dq_end]
                            }
                        })

                # if we're matching all timespans by an exact start date or within a range. start date required
                elif date_query_value:
                    if date_query_end_value:
                        ts_with_end = {
                            'bool': {
                                'must': [
                                    ts_end_exists,
                                    {'bool': {'should': [
                                        {'bool': {
                                            'must': [ts_start_lte_dq_end, ts_end_gte_dq_end]
                                        }},
                                        {'bool': {
                                            'must': [ts_start_lte_dq_start, ts_end_gte_dq_start]
                                        }},
                                        {'bool': {
                                            'must': [ts_start_gte_dq_start, ts_start_lte_dq_end]
                                        }},
                                        {'bool': {
                                            'must': [ts_end_gte_dq_start, ts_end_lte_dq_end]
                                        }},
                                    ]}}
                                ]
                            }
                        }

                        ts_no_end = {
                            'bool': {
                                'must_not': [ts_end_exists],
                                'must': {'range': {
                                    f"{timespan_field}.start": {
                                        'gte': date_query_value,
                                        'lte': date_query_end_value
                                    }
                                }}
                            }
                        }

                        should_queries = [ts_with_end, ts_no_end]
                    else:
                        ts_with_end = {'bool': {
                            'must': [
                                ts_end_exists,
                                ts_start_lte_dq_start,
                                ts_end_gte_dq_start
                            ]
                        }}

                        ts_no_end = {'bool': {
                            'must_not': [ts_end_exists],
                            'must': [{'match': {
                                f"{timespan_field}.start": {
                                    'query': date_query_value
                                }
                            }}]
                        }}

                        should_queries = [ts_with_end, ts_no_end]

                if should_queries:
                    return {'nested': {
                        'path': timespan_field,
                        'query': {'bool': {
                            'should': should_queries
                        }}
                    }}

            # GENERAL QUERY
            if general_query:
                if general_query == '*':
                    general_query = {'simple_query_string': {'query': general_query}}
                else:
                    general_query = generate_default_queries(general_query, content_type)

                if general_query:
                    if operator == 'and':
                        must.append(general_query)
                    else:
                        should.append(general_query)

            # FIELDS QUERY
            for search_field in fields_query.keys():
                field_values = [value_part for value_part in fields_query[search_field].split('__') if value_part]
                search_field, local_operator = determine_local_operator(search_field, operator)

                for field_value in field_values:
                    q = {}

                    if '.' in search_field:
                        [field_name, nested_field_name] = search_field.split('.')
                        field = self.content_types[content_type].get_field(field_name)
                        if field:
                            xref_ct = field.cross_reference_type
                            q = generate_default_queries(field_value, xref_ct, nested_field_name, f'{field_name}.')
                            q = {'nested': {'path': field_name, 'query': q}}
                    else:
                        q = generate_default_queries(field_value, content_type, search_field)

                    if q:
                        if local_operator == 'and':
                            must.append(q)
                        elif local_operator == 'or':
                            should.append(q)
                        elif local_operator == 'exclude':
                            must_not.append(q)

            # PHRASE QUERY
            for search_field in fields_phrase.keys():
                field_values = [value_part for value_part in fields_phrase[search_field].split('__') if value_part]
                search_field, local_operator = determine_local_operator(search_field, operator)

                for field_value in field_values:
                    q = {}

                    if '.' in search_field:
                        field_parts = search_field.split('.')
                        q = {'nested': {
                            'path': field_parts[0],
                            'query': {'match_phrase': {search_field: field_value}}
                        }}
                    else:
                        q = {'match_phrase': {search_field: field_value}}

                    if q:
                        if local_operator == 'and':
                            must.append(q)
                        elif local_operator == 'or':
                            should.append(q)
                        elif local_operator == 'exclude':
                            must_not.append(q)

            # TERMS QUERY
            for search_field in fields_term.keys():
                field_values = [value_part for value_part in fields_term[search_field].split('__') if value_part]
                search_field, local_operator = determine_local_operator(search_field, operator)

                if field_values:
                    terms_search_type = 'term'
                    terms_search_value = field_values[0]
                    if len(field_values) > 1:
                        terms_search_type = 'terms'
                        terms_search_value = field_values

                    q = {}

                    if '.' in search_field:
                        field_parts = search_field.split('.')

                        q = {'nested': {
                            'path': field_parts[0],
                            'query': {
                                terms_search_type: {search_field: terms_search_value}
                            }
                        }}
                    else:
                        q = {terms_search_type: {search_field: terms_search_value}}

                    if q:
                        if local_operator == 'and':
                            must.append(q)
                        elif local_operator == 'or':
                            should.append(q)
                        elif local_operator == 'exclude':
                            must_not.append(q)

            # WILDCARD QUERY
            for search_field in fields_wildcard.keys():
                field_values = [value_part for value_part in fields_wildcard[search_field].split('__') if value_part]
                search_field, local_operator = determine_local_operator(search_field, operator)

                for field_value in field_values:
                    if '*' not in field_value:
                        field_value += '*'

                    q = {}

                    if '.' in search_field:
                        field_parts = search_field.split('.')

                        q = {'nested': {
                            'path': field_parts[0],
                            'query': {'wildcard': {search_field: field_value}}
                        }}
                    else:
                        q = {'wildcard': {search_field: field_value}}

                    if q:
                        if local_operator == 'and':
                            must.append(q)
                        elif local_operator == 'or':
                            should.append(q)
                        elif local_operator == 'exclude':
                            must_not.append(q)

            # EXISTENCE QUERY
            for search_field in fields_exist:
                q = {}

                if '.' in search_field:
                    field_parts = search_field.split('.')

                    q = {'nested': {
                        'path': field_parts[0],
                        'query': {'exists': {'field': search_field}}
                    }}
                else:
                    q = {'exists': {'field': search_field}}

                if q:
                    if operator == 'and':
                        must.append(q)
                    else:
                        should.append(q)

            # FILTER QUERY
            if fields_filter:
                for search_field in fields_filter.keys():
                    field_values = [value_part for value_part in fields_filter[search_field].split('__') if value_part]
                    search_field, local_operator = determine_local_operator(search_field, operator)

                    field_queries = []
                    for field_value in field_values:
                        if '.' in search_field and not (search_field.count('.') == 1 and search_field.endswith('.raw')):
                            field_parts = search_field.split('.')

                            field_queries.append({'nested': {
                                'path': field_parts[0],
                                'query': {'term': {search_field: field_value}}
                            }})
                        else:
                            if search_field == 'id':
                                search_field = '_id'

                            if '.' not in search_field:
                                field_spec = self.content_types[content_type].get_field(search_field)
                                if field_spec and field_spec.type == 'text':
                                    search_field += '.raw'

                            field_queries.append({'term': {search_field: field_value}})

                    if field_queries:
                        if len(field_queries) > 1 or local_operator == 'exclude':
                            if local_operator == 'and':
                                filter.append({'bool': {'must': field_queries}})
                            elif local_operator == 'or':
                                filter.append({'bool': {'should': field_queries}})
                            elif local_operator == 'exclude':
                                filter.append({'bool': {'must_not': field_queries}})
                        else:
                            filter.append(field_queries[0])

            # RANGE QUERY
            if fields_range:
                for search_field in fields_range.keys():
                    field_values = [value_part for value_part in fields_range[search_field].split('__') if value_part]
                    field_converter = None
                    field_type = None
                    range_query = None

                    for field_value in field_values:
                        if '.' in search_field:
                            field_parts = search_field.split('.')
                            xref_ct = self.content_types[content_type].get_field(field_parts[0]).cross_reference_type

                            if field_parts[1] == 'label':
                                field_type = 'text'
                            elif field_parts[1] in ['uri', 'id']:
                                field_type = 'keyword'
                            else:
                                field_type = self.content_types[xref_ct].get_field(field_parts[1]).type
                        else:
                            if search_field == 'label':
                                field_type = 'text'
                            elif search_field in ['uri', 'id']:
                                field_type = 'keyword'
                            else:
                                field_type = self.content_types[content_type].get_field(search_field).type

                        if field_type in ['number', 'decimal', 'date', 'timespan']:
                            # default field conversion for number value
                            field_converter = lambda x: int(x)

                            if field_type == 'decimal':
                                field_converter = lambda x: float(x)
                            elif field_type in ['date', 'timespan']:
                                field_converter = lambda x: parse_date_string(x).isoformat()

                            range_parts = [part for part in field_value.split('to') if part]
                            if len(range_parts) == 2:
                                if field_type == 'timespan':
                                    range_query = generate_timespan_query(
                                        search_field,
                                        field_converter(range_parts[0]),
                                        field_converter(range_parts[1])
                                    )
                                else:
                                    range_query = {'range': {search_field: {
                                        'gte': field_converter(range_parts[0]),
                                        'lte': field_converter(range_parts[1])
                                    }}}
                            elif len(range_parts) == 1 and field_value.endswith('to'):
                                if field_type == 'timespan':
                                    range_query = generate_timespan_query(
                                        search_field,
                                        field_converter(range_parts[0]),
                                        None,
                                        True
                                    )
                                else:
                                    range_query = {'range': {search_field: {
                                        'gte': field_converter(range_parts[0]),
                                    }}}
                            elif len(range_parts) == 1 and field_value.startswith('to'):
                                if field_type == 'timespan':
                                    range_query = generate_timespan_query(
                                        search_field,
                                        None,
                                        field_converter(range_parts[0]),
                                        True
                                    )
                                else:
                                    range_query = {'range': {search_field: {
                                        'lte': field_converter(range_parts[0]),
                                    }}}

                        elif field_type == 'geo_point' and 'to' in field_value:
                            [top_left, bottom_right] = field_value.split('to')
                            if top_left.count(',') == 1 and bottom_right.count(',') == 1:
                                [top_left_lon, top_left_lat] = top_left.split(',')
                                [bottom_right_lon, bottom_right_lat] = bottom_right.split(',')

                                valid_geo_query = True
                                try:
                                    top_left_lon = float(top_left_lon)
                                    top_left_lat = float(top_left_lat)
                                    bottom_right_lon = float(bottom_right_lon)
                                    bottom_right_lat = float(bottom_right_lat)

                                    if not (is_valid_long_lat(top_left_lon, top_left_lat) and
                                            is_valid_long_lat(bottom_right_lon, bottom_right_lat)):
                                        valid_geo_query = False
                                except:
                                    valid_geo_query = False

                                if valid_geo_query:
                                    range_query = {'geo_bounding_box': {
                                        search_field: {
                                            'top_left': {'lat': top_left_lat, 'lon': top_left_lon},
                                            'bottom_right': {'lat': bottom_right_lat, 'lon': bottom_right_lon}
                                        }
                                    }}

                        if range_query:
                            if '.' in search_field:
                                field_parts = search_field.split('.')

                                range_query = {'nested': {'path': field_parts[0], 'query': range_query}}

                            if operator == 'and':
                                filter.append(range_query)
                            else:
                                should.append(range_query)

            # CONTENT VIEW
            if content_view:
                filter.append({'terms': {'_id': {
                    'index': 'content_view',
                    'id': content_view,
                    'path': 'ids'
                }}})

            if should or must or must_not or filter:
                search_query = {'query': {'bool': {}}}
                if should:
                    search_query['query']['bool']['should'] = should
                if must:
                    search_query['query']['bool']['must'] = must
                if must_not:
                    search_query['query']['bool']['must_not'] = must_not
                if filter:
                    search_query['query']['bool']['filter'] = filter

                if generate_query_only:
                    return search_query['query']

                search_query['track_total_hits'] = True
                if fields_query and fields_highlight:
                    search_query['min_score'] = 0.001

                using_page_token = False
                if next_page_token:
                    next_page_info = self.redis_cache.get(next_page_token)
                    if next_page_info:
                        next_page_info = json.loads(next_page_info)
                        search_query['search_after'] = next_page_info['search_after']
                        results['meta']['page'] = next_page_info['page_num']
                        results['meta']['page_size'] = next_page_info['page_size']
                        using_page_token = True

                # HANDLE RETURNING FIELD RESTRICTIONS (ONLY and EXCLUDES)
                if only or excludes:
                    if only and '_id' not in only:
                        only.append('_id')

                    search_query['source'] = {'includes': only, 'excludes': excludes}

                # ADD ANY AGGREGATIONS TO SEARCH
                agg_type_map = {}
                for agg_name, agg in aggregations.items():
                    # agg should be of type elasticsearch_dsl.A, so calling A's .to_dict()
                    # method to get at what type ('terms', 'nested', etc) of aggregation
                    # this is.
                    agg_descriptor = list(agg.keys())[0]
                    if agg_descriptor == 'nested':
                        agg_descriptor += '_' + list(agg['aggs']['names'].keys())[0]
                    agg_type_map[agg_name] = agg_descriptor

                    if 'aggs' not in search_query:
                        search_query['aggs'] = {}
                    search_query['aggs'][agg_name] = agg

                # HANDLE SORTING (by default, all data sorted by ID for "search_after" functionality)
                adjusted_fields_sort = []
                sorting_by_id = False

                if fields_sort:
                    mappings = index.get()[index_name]['mappings']['properties']

                    for x in range(0, len(fields_sort)):
                        field_name = list(fields_sort[x].keys())[0]
                        sort_direction = fields_sort[x][field_name]
                        subfield_name = None

                        if field_name == 'id':
                            adjusted_fields_sort.append({
                                '_id': sort_direction
                            })
                            sorting_by_id = True
                        else:
                            # check if timespan field so we can add .start to field_name
                            ct_field = self.content_types[content_type].get_field(field_name)
                            if ct_field and ct_field.type == 'timespan':
                                field_name += '.start'

                            if '.' in field_name:
                                field_parts = field_name.split('.')
                                field_name = field_parts[0]
                                subfield_name = field_parts[1]

                            if field_name in mappings:
                                field_type = mappings[field_name]['type']
                                if field_type == 'nested' and subfield_name:
                                    field_type = mappings[field_name]['properties'][subfield_name]['type']
                                    if field_type == 'nested' and 'start' in \
                                            mappings[field_name]['properties'][subfield_name]['properties']:
                                        field_type = 'timespan'

                                if subfield_name:
                                    full_field_name = '{0}.{1}'.format(field_name, subfield_name)
                                    if field_type == 'text':
                                        full_field_name += '.raw'
                                    elif field_type == 'timespan':
                                        full_field_name += '.start'

                                    adjusted_fields_sort.append({
                                        full_field_name: {
                                            'order': sort_direction['order'],
                                            'nested': {'path': field_name}
                                        }
                                    })
                                else:
                                    adjusted_fields_sort.append({
                                        field_name + '.raw' if field_type == 'text' else field_name: sort_direction
                                    })

                if not sorting_by_id:
                    adjusted_fields_sort.append({
                        '_score': 'desc'
                    })
                    adjusted_fields_sort.append({
                        '_id': 'asc'
                    })

                search_query['sort'] = adjusted_fields_sort

                if fields_highlight:
                    formatted_highlight_fields = {}
                    for field_to_highlight in fields_highlight:
                        formatted_highlight_fields[field_to_highlight] = {}

                    search_query['highlight'] = {
                        'fields': formatted_highlight_fields,
                        'fragment_size': highlight_fragment_size,
                        'number_of_fragments': highlight_num_fragments,
                        'max_analyzed_offset': 90000
                    }

                if using_page_token:
                    search_query['size'] = results['meta']['page_size']
                else:
                    search_query['from'] = start_index
                    search_query['size'] = results['meta']['page_size']

                # execute search
                try:
                    es_logger = None
                    es_log_level = None
                    if es_debug or es_debug_query:
                        search_query['explain'] = True
                        print(json.dumps(search_query, indent=4))
                        es_logger = logging.getLogger('elasticsearch')
                        es_log_level = es_logger.getEffectiveLevel()
                        es_logger.setLevel(logging.DEBUG)

                    search_results = get_connection().search(index=index_name, body=search_query)

                    if es_debug:
                        print(json.dumps(search_results.body, indent=4))
                        es_logger.setLevel(es_log_level)

                    results['meta']['total'] = search_results['hits']['total']['value']
                    if results['meta']['page_size'] > 0:
                        results['meta']['num_pages'] = ceil(results['meta']['total'] / results['meta']['page_size'])
                        results['meta']['has_next_page'] = results['meta']['page'] < results['meta']['num_pages']
                    else:
                        results['meta']['num_pages'] = 0
                        results['meta']['has_next_page'] = False

                    # identify any multi-valued geo_point fields, as their output needs to be adjusted
                    multi_geo_fields = [f.name for f in self.content_types[content_type].fields if
                                        f.type == 'geo_point' and f.multiple]

                    hit = None
                    for hit in search_results['hits']['hits']:
                        record = deepcopy(hit['_source'])
                        record['id'] = hit['_id']
                        record['_search_score'] = hit['_score']

                        for multi_geo_field in multi_geo_fields:
                            if multi_geo_field in record:
                                record[multi_geo_field] = record[multi_geo_field]['coordinates']

                        if fields_highlight:
                            if 'highlight' in hit:
                                record['_search_highlights'] = hit['highlight']
                                results['records'].append(record)
                            elif not only_highlights:
                                results['records'].append(record)
                        else:
                            results['records'].append(record)

                    # search_after
                    if (end_index >= 9000 or using_page_token) and results['meta']['has_next_page']:
                        next_page_token = str(ObjectId())

                        if hit and 'sort' in hit:
                            next_page_info = {
                                'search_after': hit['sort'],
                                'page_num': results['meta']['page'] + 1,
                                'page_size': results['meta']['page_size']
                            }
                            next_page_info = json.dumps(next_page_info)
                            self.redis_cache.set(next_page_token, next_page_info, ex=300)
                            results['meta']['next_page_token'] = next_page_token

                    if 'aggregations' in search_results:
                        for agg_name in search_results['aggregations'].keys():
                            results['meta']['aggregations'][agg_name] = {}

                            if agg_type_map[agg_name].startswith('nested'):
                                if agg_type_map[agg_name].endswith('_terms') or agg_type_map[agg_name].endswith(
                                        '_histogram') or agg_type_map[agg_name].endswith('_geotile_grid'):
                                    for agg_result in search_results['aggregations'][agg_name]['names']['buckets']:
                                        results['meta']['aggregations'][agg_name][agg_result['key']] = agg_result[
                                            'doc_count']
                                elif agg_type_map[agg_name].endswith('_max') or agg_type_map[agg_name].endswith('_min'):
                                    results['meta']['aggregations'][agg_name] = \
                                    search_results['aggregations'][agg_name]['names']['value']
                                elif agg_type_map[agg_name].endswith('_geo_bounds'):
                                    results['meta']['aggregations'][agg_name] = \
                                    search_results['aggregations'][agg_name]['names']['bounds']


                            elif agg_type_map[agg_name] in ['max', 'min']:
                                results['meta']['aggregations'][agg_name] = search_results['aggregations'][agg_name][
                                    'value']

                            elif agg_type_map[agg_name] in ['terms', 'histogram']:
                                for agg_result in search_results['aggregations'][agg_name]['buckets']:
                                    results['meta']['aggregations'][agg_name][agg_result['key']] = agg_result[
                                        'doc_count']

                except:
                    print('Error executing elasticsearch query in corpus.search_content:')
                    print(traceback.format_exc())

        return results

    def explore_content(
            self,
            left_content_type,
            left_id=None,
            left_content=[],
            relationship_cypher=None,
            relationship=None,
            cardinality=1,
            right_content_type=None,
            right_id=None,
            order_by=None):
        """
        Explore graph relationships between content using Neo4j.

        Traverses the graph database to find related content based on relationship
        patterns. Results are attached to the source content objects.

        Args:
            left_content_type (str): Source content type name.
            left_id (str): Specific source content ID.
            left_content (list): Pre-loaded source content objects.
            relationship_cypher (str): Custom Cypher relationship pattern.
            relationship (str): Simple relationship type name.
            cardinality (int): Relationship direction:
                - 0: Undirected (---)
                - 1: Left to right (-->)
                - 2: Right to left (<--)
                - 3: Bidirectional (<->)
            right_content_type (str): Target content type name.
            right_id (str): Specific target content ID.
            order_by (str): Cypher ORDER BY clause.

        Returns:
            list: Source content objects with a new _exploration attribute for any content that matches specified pattern.
                The _explororation attribute is a dictionary where the keys are the labels of any edges (like 'hasAuthor')
                and the value for each key is a list containing a "content stub," which is a dictionary containing the
                content type, id, and URI for a piece of content having the specified relationship.

        Examples:
            >>> # Find all articles by a specific author
            >>> articles = corpus.explore_content(
            ...     'Article',
            ...     relationship='hasAuthor',
            ...     right_content_type='Person',
            ...     right_id=author_id
            ... )
        """

        results_added = 0
        if left_content_type in self.content_types:
            left_uri_constraints = []
            left_id_map = {}

            if not left_content:
                left_content = []
                if left_id:
                    left_content.append(self.get_content(left_content_type, left_id))
                else:
                    left_content = self.get_content(left_content_type, all=True)

            if left_content:
                left_content = [lefty for lefty in left_content]  # <- in case left content is a queryset
                for left_index in range(0, len(left_content)):
                    left_uri_constraints.append(
                        "/corpus/{0}/{1}/{2}".format(
                            self.id,
                            left_content_type,
                            left_content[left_index].id
                        )
                    )

                    left_id_map[str(left_content[left_index].id)] = left_index

                left_cypher = "(left:{0})".format(left_content_type)

                # determine relationship cypher based on relationship and cardinality
                if not relationship_cypher:
                    relationship_cypher = "[rel]"
                    if relationship:
                        relationship_cypher = "[rel:{0}]".format(relationship)

                    relationship_start = '-'
                    relationship_end = '->'

                    if cardinality == 0:
                        relationship_end = '-'
                    elif cardinality == 2:
                        relationship_start = '<-'
                        relationship_end = '-'
                    elif cardinality == 3:
                        relationship_start = '<-'

                    relationship_cypher = "{0}{1}{2}".format(relationship_start, relationship_cypher, relationship_end)

                right_cypher = "(right)"
                if right_content_type:
                    right_cypher = "(right:{0})".format(right_content_type)

                order_cypher = ""
                if order_by:
                    order_cypher = " ORDER BY {0}".format(order_by)

                cypher = '''
                    MATCH {0} {1} {2}
                    WHERE left.corpus_id = $corpus_id
                    AND right.corpus_id = $corpus_id
                    AND left.uri IN $left_uri_constraints
                    RETURN left.id, type(rel), right.uri{3}
                '''.format(left_cypher, relationship_cypher, right_cypher, order_cypher)

                print(cypher)

                results = run_neo(cypher, {
                    'corpus_id': str(self.id),
                    'left_uri_constraints': left_uri_constraints
                })

                for result in results:
                    result = result.data()
                    left_id = result['left.id']
                    relation = result['type(rel)']
                    right_uri = result['right.uri']
                    right_uri_parts = [uri_part for uri_part in right_uri.split('/') if uri_part]
                    if len(right_uri_parts) == 4:
                        right_id = right_uri_parts[3]
                        right_content_type = right_uri_parts[2]

                        if left_id in left_id_map:
                            left_index = left_id_map[left_id]
                            right_dict = {
                                'content_type': right_content_type,
                                'id': right_id,
                                'uri': right_uri
                            }

                            if not hasattr(left_content[left_index], '_exploration'):
                                setattr(left_content[left_index], '_exploration', {})

                            if relation not in left_content[left_index]._exploration:
                                left_content[left_index]._exploration[relation] = [right_dict]
                            else:
                                left_content[left_index]._exploration[relation].append(right_dict)

                            results_added += 1

        print(results_added)
        return left_content

    def suggest_content(
            self,
            content_type,
            prefix,
            fields=[],
            max_suggestions_per_field=5,
            filters={},
            es_debug=False
    ):
        """
        Generate autocomplete suggestions for content fields.

        Uses Elasticsearch's search-as-you-type (autocomplete) functionality to provide
        real-time suggestions based on indexed content.

        Args:
            content_type (str): Name of the content type.
            prefix (str): Partial text to match.
            fields (list): Specific fields to search (empty for all autocomplete fields).
            max_suggestions_per_field (int): Maximum suggestions per field. Defaults to 5.
            filters (dict): Field specific term searches to use as criteria.
            es_debug (bool): Whether to print the Elasticsearch query and the results to stdout. Defaults to False.

        Returns:
            dict: Suggestions organized by field name.

        Examples:
            >>> suggestions = corpus.suggest_content(
            ...     'Person',
            ...     prefix='joh',
            ...     fields=['first_name', 'last_name']
            ... )
            >>> # Returns: {'first_name': ['John', 'Johann'], 'last_name': ['Johnson']}
        """

        results = {}

        if content_type in self.content_types:
            ct = self.content_types[content_type]
            index_name = "corpus-{0}-{1}".format(self.id, ct.name.lower())
            index = Index(index_name)
            if index.exists():
                text_fields = []
                xref_fields = []

                for ct_field in ct.fields:
                    if ct_field.autocomplete and (not fields) or (ct_field.name in fields):
                        if ct_field.type == 'text':
                            text_fields.append(ct_field.name)
                        elif ct_field.type == 'cross_reference':
                            xref_fields.append(ct_field.name)
                if 'label' in fields and ct.autocomplete_labels:
                    text_fields.append('label')

                if text_fields or xref_fields:
                    filter_queries = []
                    if filters:
                        for search_field in filters.keys():
                            field_values = [value_part for value_part in filters[search_field].split('__') if
                                            value_part]
                            field_queries = []
                            for field_value in field_values:
                                if '.' in search_field:
                                    field_parts = search_field.split('.')
                                    field_queries.append(Q(
                                        "nested",
                                        path=field_parts[0],
                                        query=Q(
                                            'term',
                                            **{search_field: field_value}
                                        )
                                    ))
                                else:
                                    if search_field == 'id':
                                        search_field = '_id'
                                    field_queries.append(Q('term', **{search_field: field_value}))

                            if field_queries:
                                if len(field_queries) > 1:
                                    filter_queries.append(Q('bool', should=field_queries))
                                else:
                                    filter_queries.append(field_queries[0])

                    if text_fields:
                        subfields = []
                        for text_field in text_fields:
                            subfields.append(text_field + '.suggest')
                            subfields.append(text_field + '.suggest._2gram')
                            subfields.append(text_field + '.suggest._3gram')

                        text_query = Q('multi_match', query=prefix, type='bool_prefix', fields=subfields)
                        command = Search(using=get_connection(), index=index_name)
                        command = command.query('bool', must=[text_query], filter=filter_queries)
                        command = command.source(includes=text_fields)

                        if es_debug:
                            print(json.dumps(command.to_dict(), indent=4))
                        response = command.execute()
                        if es_debug:
                            print(json.dumps(response.to_dict(), indent=4))

                        if hasattr(response, 'hits'):
                            field_hits_gathered = {}
                            total_hits_gathered = 0

                            for hit in response.hits:
                                if total_hits_gathered >= len(text_fields) * max_suggestions_per_field:
                                    break
                                else:
                                    for text_field in text_fields:
                                        if 'text_field' not in field_hits_gathered or field_hits_gathered[
                                            text_field] < max_suggestions_per_field:
                                            if hasattr(hit, text_field) and getattr(hit, text_field):
                                                if text_field not in results:
                                                    results[text_field] = []

                                                hit_value = getattr(hit, text_field)

                                                if hit_value not in results[text_field]:
                                                    results[text_field].append(hit_value)

                                                    if text_field not in field_hits_gathered:
                                                        field_hits_gathered[text_field] = 0

                                                    field_hits_gathered[text_field] += 1
                                                    total_hits_gathered += 1

                    if xref_fields:
                        nested_queries = []
                        for xref_field in xref_fields:
                            nested_queries.append(Q(
                                'nested',
                                path=xref_field,
                                query=Q(
                                    'multi_match',
                                    query=prefix,
                                    type='bool_prefix',
                                    fields=[
                                        xref_field + '.label.suggest',
                                        xref_field + '.label.suggest._2gram',
                                        xref_field + '.label.suggest._3gram'
                                    ]
                                )
                            ))

                        command = Search(using=get_connection(), index=index_name, extra={'size': 0})
                        command = command.query('bool', must=nested_queries, filter=filter_queries)

                        for xref_field in xref_fields:
                            agg = A('nested', path=xref_field)
                            agg.bucket('names', 'terms', size=max_suggestions_per_field,
                                       field=xref_field + '.label.raw')
                            command.aggs.bucket(xref_field, agg)

                        if es_debug:
                            print(json.dumps(command.to_dict(), indent=4))
                        response = command.execute()
                        if es_debug:
                            print(json.dumps(response.to_dict(), indent=4))

                        if hasattr(response, 'aggregations'):
                            for xref_field in xref_fields:
                                if hasattr(response.aggregations, xref_field):
                                    suggestions = getattr(response.aggregations, xref_field).names.buckets
                                    for suggestion in suggestions:
                                        if xref_field not in results:
                                            results[xref_field] = []
                                        results[xref_field].append(suggestion.key)

        return results

    def save_content_type(self, schema):
        """
        Create or update a content type definition.

        Validates the schema, creates necessary indexes, and triggers reindexing
        if needed. For existing content types, handles field additions, modifications,
        and deletions gracefully.

        Args:
            schema (dict): Content type definition with structure:
                {
                    'name': str,
                    'plural_name': str,
                    'fields': list[dict],
                    'show_in_nav': bool,
                    'templates': dict,
                    'inherited_from_module': str (optional),
                    'inherited_from_class': str (optional),
                    'autocomplete_labels': bool (optional),
                    'view_widget_url': str (optional),
                    'edit_widget_url': str (optional),
                    'has_file_field': bool (optional),
                    'invalid_field_names': list (optional),
                }

        Returns:
            list[str]: Job IDs for any triggered reindexing tasks.

        Examples:
            >>> schema = {
            ...     'name': 'Person',
            ...     'plural_name': 'People',
            ...     'fields': [
            ...         {
            ...             'name': 'email',
            ...             'type': 'keyword',
            ...             'label': 'Email Address',
            ...             'unique': True,
            ...             'indexed': True
            ...         }
            ...     ]
            ... }
            >>> job_ids = corpus.save_content_type(schema)
        """

        valid = True
        existing = False
        had_file_field = False
        reindex = False
        relabel = False
        resave = False
        queued_job_ids = []
        ct_name = schema['name']

        default_field_values = {
            'type': 'keyword',
            'in_lists': True,
            'indexed': False,
            'indexed_with': [],
            'unique': False,
            'unique_with': [],
            'multiple': False,
            'proxy_field': "",
            'inherited': False,
            'cross_reference_type': '',
            'has_intensity': False,
            'language': 'english',
            'autocomplete': False,
            'synonym_file': None
        }

        default_invalid_field_names = [
            'corpus_id',
            'content_type',
            'last_updated',
            'provenance',
            'field_intensities',
            'path',
            'label',
            'uri',
        ]

        invalid_field_names = deepcopy(default_invalid_field_names)
        if 'invalid_field_names' in schema:
            invalid_field_names += schema['invalid_field_names']
            invalid_field_names = list(set(invalid_field_names))

        # NEW CONTENT TYPE
        if ct_name not in self.content_types:
            new_content_type = ContentType()
            new_content_type.name = schema['name']
            new_content_type.plural_name = schema['plural_name']
            new_content_type.show_in_nav = schema.get('show_in_nav', True)
            new_content_type.autocomplete_labels = schema.get('autocomplete_labels', False)
            new_content_type.proxy_field = schema.get('proxy_field', None)
            new_content_type.view_widget_url = schema.get('view_widget_url', None)
            new_content_type.edit_widget_url = schema.get('edit_widget_url', None)
            new_content_type.has_file_field = schema.get('has_file_field', False)
            new_content_type.invalid_field_names = invalid_field_names

            if 'templates' in schema:
                for template_name in schema['templates']:
                    template = ContentTemplate()
                    template.template = schema['templates'][template_name]['template']
                    template.mime_type = schema['templates'][template_name]['mime_type']
                    new_content_type.templates[template_name] = template

            if 'inherited_from_module' in schema and 'inherited_from_class' in schema:
                new_content_type.inherited_from_module = schema['inherited_from_module']
                new_content_type.inherited_from_class = schema['inherited_from_class']

                if 'base_mongo_indexes' in schema and schema['base_mongo_indexes']:
                    new_content_type.base_mongo_indexes = json.dumps(schema['base_mongo_indexes'])

            for field_dict in schema['fields']:
                if field_dict['name'] in invalid_field_names or field_dict['name'].startswith('_'):
                    print("Invalid field name: {0}".format(field_dict['name']))
                    valid = False
                else:
                    field = default_field_values.copy()
                    field.update(field_dict)

                    new_field = Field()
                    new_field.name = field['name']
                    new_field.label = field['label']
                    new_field.in_lists = field['in_lists']
                    new_field.indexed = field['indexed']
                    new_field.indexed_with = field['indexed_with']
                    new_field.unique = field['unique']
                    new_field.unique_with = field['unique_with']
                    new_field.multiple = field['multiple']
                    new_field.type = field['type']
                    new_field.cross_reference_type = field['cross_reference_type']
                    new_field.has_intensity = field['has_intensity']
                    new_field.inherited = field['inherited']
                    new_field.synonym_file = field['synonym_file']
                    new_field.language = field['language']
                    new_field.autocomplete = field['autocomplete']

                    if new_field.type == 'embedded':
                        new_field.in_lists = False

                    new_content_type.fields.append(new_field)

            if valid:
                reindex = True
                self.content_types[new_content_type.name] = new_content_type

        # EXISTING CONTENT TYPE
        else:
            existing = True
            had_file_field = self.content_types[ct_name].has_file_field
            had_autocomplete_labels = self.content_types[ct_name].autocomplete_labels

            self.content_types[ct_name].plural_name = schema['plural_name']
            self.content_types[ct_name].show_in_nav = schema['show_in_nav']
            self.content_types[ct_name].autocomplete_labels = schema.get('autocomplete_labels', False)
            self.content_types[ct_name].proxy_field = schema['proxy_field']

            if 'view_widgel_url' in schema:
                self.content_types[ct_name].view_widget_url = schema['view_widget_url']
            if 'edit_widget_url' in schema:
                self.content_types[ct_name].edit_widget_url = schema['edit_widget_url']
            if 'synonym_file' in schema:
                self.content_types[ct_name].synonym_file = schema['synonym_file']

            label_template = self.content_types[ct_name].templates['Label'].template
            for template_name in schema['templates']:
                if template_name in self.content_types[ct_name].templates:
                    self.content_types[ct_name].templates[template_name].template = schema['templates'][template_name][
                        'template']
                    self.content_types[ct_name].templates[template_name].mime_type = schema['templates'][template_name][
                        'mime_type']
                else:
                    template = ContentTemplate()
                    template.template = schema['templates'][template_name]['template']
                    template.mime_type = schema['templates'][template_name]['mime_type']
                    self.content_types[ct_name].templates[template_name] = template

            if label_template != self.content_types[ct_name].templates['Label'].template:
                relabel = True
                reindex = True

            if had_autocomplete_labels != self.content_types[ct_name].autocomplete_labels:
                reindex = True

            old_fields = {}
            for x in range(0, len(self.content_types[ct_name].fields)):
                old_fields[self.content_types[ct_name].fields[x].name] = x

            for x in range(0, len(schema['fields'])):
                if schema['fields'][x]['name'] in invalid_field_names or schema['fields'][x]['name'].startswith('_'):
                    valid = False
                elif valid:
                    if schema['fields'][x]['name'] not in old_fields:
                        new_field = Field()
                        new_field.name = schema['fields'][x]['name']
                        new_field.label = schema['fields'][x]['label']
                        new_field.type = schema['fields'][x]['type']
                        new_field.in_lists = schema['fields'][x].get('in_lists', default_field_values['in_lists'])
                        new_field.indexed = schema['fields'][x].get('indexed', default_field_values['indexed'])
                        new_field.indexed_with = schema['fields'][x].get('indexed_with',
                                                                         default_field_values['indexed_with'])
                        new_field.unique = schema['fields'][x].get('unique', default_field_values['unique'])
                        new_field.unique_with = schema['fields'][x].get('unique_with',
                                                                        default_field_values['unique_with'])
                        new_field.multiple = schema['fields'][x].get('multiple', default_field_values['multiple'])
                        new_field.inherited = schema['fields'][x].get('inherited', default_field_values['inherited'])
                        new_field.cross_reference_type = schema['fields'][x].get('cross_reference_type',
                                                                                 default_field_values[
                                                                                     'cross_reference_type'])
                        new_field.has_intensity = schema['fields'][x].get('has_intensity',
                                                                          default_field_values['has_intensity'])
                        new_field.synonym_file = schema['fields'][x].get('synonym_file',
                                                                         default_field_values['synonym_file'])
                        new_field.language = schema['fields'][x].get('language', default_field_values['language'])
                        new_field.autocomplete = schema['fields'][x].get('autocomplete',
                                                                         default_field_values['autocomplete'])

                        self.content_types[ct_name].fields.append(new_field)
                        if new_field.in_lists:
                            reindex = True
                    else:
                        field_index = old_fields[schema['fields'][x]['name']]
                        self.content_types[ct_name].fields[field_index].label = schema['fields'][x]['label']

                        reindex_triggering_attributes = ['in_lists', 'type', 'multiple', 'language', 'synonym_file',
                                                         'autocomplete']
                        if self.content_types[ct_name].fields[field_index].type != 'embedded':
                            for reindex_triggering_attribute in reindex_triggering_attributes:
                                old_val = getattr(self.content_types[ct_name].fields[field_index],
                                                  reindex_triggering_attribute)
                                new_val = schema['fields'][x].get(reindex_triggering_attribute,
                                                                  default_field_values[reindex_triggering_attribute])
                                if old_val != new_val:
                                    reindex = True

                        if not self.content_types[ct_name].fields[field_index].inherited:
                            self.content_types[ct_name].fields[field_index].type = schema['fields'][x]['type']
                            self.content_types[ct_name].fields[field_index].in_lists = schema['fields'][x].get(
                                'in_lists', default_field_values['in_lists'])
                            self.content_types[ct_name].fields[field_index].indexed = schema['fields'][x].get('indexed',
                                                                                                              default_field_values[
                                                                                                                  'indexed'])
                            self.content_types[ct_name].fields[field_index].indexed_with = schema['fields'][x].get(
                                'indexed_with', default_field_values['indexed_with'])
                            self.content_types[ct_name].fields[field_index].unique = schema['fields'][x].get('unique',
                                                                                                             default_field_values[
                                                                                                                 'unique'])
                            self.content_types[ct_name].fields[field_index].unique_with = schema['fields'][x].get(
                                'unique_with', default_field_values['unique_with'])
                            self.content_types[ct_name].fields[field_index].multiple = schema['fields'][x].get(
                                'multiple', default_field_values['multiple'])
                            self.content_types[ct_name].fields[field_index].cross_reference_type = schema['fields'][
                                x].get('cross_reference_type', default_field_values['cross_reference_type'])
                            self.content_types[ct_name].fields[field_index].has_intensity = schema['fields'][x].get(
                                'has_intensity', default_field_values['has_intensity'])
                            self.content_types[ct_name].fields[field_index].synonym_file = schema['fields'][x].get(
                                'synonym_file', default_field_values['synonym_file'])
                            self.content_types[ct_name].fields[field_index].language = schema['fields'][x].get(
                                'language', default_field_values['language'])
                            self.content_types[ct_name].fields[field_index].autocomplete = schema['fields'][x].get(
                                'autocomplete', default_field_values['autocomplete'])

                        del old_fields[schema['fields'][x]['name']]

            # check to see if any old fields weren't present in the new schema, indicating they should be deleted
            for field_to_delete in old_fields.keys():
                self.delete_content_type_field(ct_name, field_to_delete)

            # now that old and new fields have been reconciled, sort them according to the order found in the schema
            schema_ordered = [self.content_types[ct_name].get_field(f_spec['name']) for f_spec in schema['fields']]
            self.content_types[ct_name].fields = schema_ordered

            if not valid:
                self.reload()

        if valid:
            related_content_types = []

            # ENSURE NEO4J INDEXES ON NEW CONTENT TYPE AND DEPENDENT NODES
            if not existing:
                new_node_indexes = [ct_name]
                if 'dependent_nodes' in schema:
                    for dependent_node in schema['dependent_nodes']:
                        new_node_indexes.append(dependent_node)

                ensure_neo_indexes(new_node_indexes)

            if 'Label' not in self.content_types[ct_name].templates:
                template = ContentTemplate()
                template.template = "{content_type} ({{{{ {content_type}.id }}}})".format(content_type=ct_name)
                template.mime_type = "text/html"
                self.content_types[ct_name].templates['Label'] = template

            if reindex:
                self.build_content_type_elastic_index(ct_name)
                if not existing:
                    reindex = False
                else:
                    for related_ct in self.content_types.keys():
                        if related_ct != ct_name:
                            for related_field in self.content_types[related_ct].fields:
                                if related_field.type == 'cross_reference' and related_field.cross_reference_type == ct_name:
                                    if related_ct not in related_content_types:
                                        self.build_content_type_elastic_index(related_ct)
                                        related_content_types.append(related_ct)

            self.content_types[ct_name].has_file_field = schema.get('has_file_field', False)
            for field in self.content_types[ct_name].fields:
                if field.type in ['file', 'repo']:
                    self.content_types[ct_name].has_file_field = True
                    break

            if not had_file_field and self.content_types[ct_name].has_file_field:
                resave = True

            if reindex or relabel or resave:
                queued_job_ids.append(self.queue_local_job(task_name="Adjust Content", parameters={
                    'content_type': ct_name,
                    'reindex': reindex,
                    'relabel': relabel,
                    'resave': resave,
                    'related_content_types': ','.join(related_content_types)
                }))

            self.save()

        return queued_job_ids

        if content_type in self.content_types:
            # Delete Neo4J nodes
            nodes_deleted = 1
            while nodes_deleted > 0:
                nodes_deleted = run_neo(
                    '''
                        MATCH (x:{0} {{corpus_id: $corpus_id}})
                        WITH x LIMIT 5000
                        DETACH DELETE x
                        RETURN count(*)
                    '''.format(content_type),
                    {'corpus_id': str(self.id)}
                )[0][0]

            # Delete Elasticsearch index
            index_name = "corpus-{0}-{1}".format(self.id, content_type.lower())
            index = Index(index_name)
            if index.exists():
                index.delete()

            # Drop MongoDB collection
            self.content_types[content_type].get_mongoengine_class(self).drop_collection()

            # Delete files
            ct_path = "{0}/{1}".format(self.path, content_type)
            if os.path.exists(ct_path):
                shutil.rmtree(ct_path)

            del self.content_types[content_type]


    def clear_content_type_field(self, content_type, field_name):
        if content_type in self.content_types:
            ct = self.content_types[content_type]
            if field_name in [field.name for field in ct.fields]:
                ct.get_mongoengine_class(self).objects.update(**{'set__{0}'.format(field_name): None})

    def delete_content_type_field(self, content_type, field_name):
        if content_type in self.content_types:
            ct = self.content_types[content_type]

            if field_name in [field.name for field in ct.fields]:

                # find and delete field or references to field
                field_index = -1
                for x in range(0, len(ct.fields)):
                    if ct.fields[x].name == field_name and not ct.fields[x].inherited:
                        field_index = x
                    else:
                        if field_name in ct.fields[x].unique_with:
                            self.content_types[content_type].fields[x].unique_with.remove(field_name)
                        if field_name in ct.fields[x].indexed_with:
                            self.content_types[content_type].fields[x].indexed_with.remove(field_name)
                if field_index > -1:
                    self.content_types[content_type].fields.pop(field_index)
                    self.save()

                    # delete any indexes referencing field, then drop field from collection
                    print('field cleared. now attemtpting to drop indexes...')
                    collection_name = "corpus_{0}_{1}".format(self.id, content_type)
                    db = self._get_db()
                    index_info = db[collection_name].index_information()
                    for index_name in index_info.keys():
                        delete_index = False
                        for key in index_info[index_name]['key']:
                            if key[0] == field_name:
                                delete_index = True
                        if delete_index:
                            db[collection_name].drop_index(index_name)
                    print('indexes cleared. now attemtpting to unset fields...')
                    db[collection_name].update_many({}, {'$unset': {field_name: 1}})

    def build_content_type_elastic_index(self, content_type):
        """
        Build or rebuild the Elasticsearch index for a content type.

        Creates appropriate index mappings based on field definitions, including
        analyzers for text fields and nested mappings for cross-references.

        Args:
            content_type (str): Name of the content type to index.
        """

        if content_type in self.content_types:
            ct = self.content_types[content_type]
            field_type_map = {
                'text': 'text',
                'large_text': 'large_text',
                'keyword': 'keyword',
                'html': 'large_text',
                'number': 'integer',
                'decimal': 'float',
                'boolean': 'boolean',
                'date': 'date',
                'timespan': Nested(properties={
                    'start': 'date',
                    'end': 'date',
                    'uncertain': 'boolean',
                    'granularity': 'keyword'
                }),
                'file': 'keyword',
                'image': 'keyword',
                'iiif-image': 'keyword',
                'geo_point': GeoPoint(),
                'repo': 'keyword',
                'link': 'keyword',
                'cross_reference': None,
                'document': 'text',
            }

            index_name = "corpus-{0}-{1}".format(self.id, ct.name.lower())
            index = Index(index_name)
            if index.exists():
                index.delete()

            label_analyzer = analyzer(
                'corpora_label_analyzer',
                tokenizer='classic',
                filter=['stop', 'lowercase', 'classic']
            )
            label_subfields = {
                'raw': {'type': 'keyword'},
            }
            if ct.autocomplete_labels:
                label_subfields['suggest'] = {'type': 'search_as_you_type'}

            mapping = Mapping()
            mapping.field('label', 'text', analyzer=label_analyzer, fields=label_subfields)
            mapping.field('uri', 'keyword')

            for field in ct.fields:
                if field.type != 'embedded' and field.in_lists:
                    field_type = field_type_map[field.type]

                    if field.type == 'cross_reference' and field.cross_reference_type in self.content_types:
                        xref_ct = self.content_types[field.cross_reference_type]
                        xref_label_subfields = {'raw': {'type': 'keyword'}}
                        if field.autocomplete:
                            xref_label_subfields['suggest'] = {'type': 'search_as_you_type'}

                        xref_mapping_props = {
                            'id': 'keyword',
                            'label': {
                                'type': 'text',
                                'analyzer': label_analyzer,
                                'fields': xref_label_subfields
                            },
                            'uri': 'keyword'
                        }

                        if field.has_intensity:
                            xref_mapping_props['intensity'] = 'integer'

                        for xref_field in xref_ct.fields:
                            if xref_field.in_lists and not xref_field.type == 'cross_reference':
                                xref_field_type = field_type_map[xref_field.type]

                                if xref_field.type in ['text', 'large_text', 'html']:

                                    xref_field_type = {
                                        'type': 'text',
                                        'analyzer': xref_field.get_elasticsearch_analyzer(),
                                    }

                                    if xref_field.type == 'text':
                                        xref_field_type['fields'] = {
                                            'raw': {
                                                'type': 'keyword'
                                            }
                                        }

                                xref_mapping_props[xref_field.name] = xref_field_type

                        mapping.field(field.name, Nested(properties=xref_mapping_props))

                    elif field_type == 'text':
                        subfields = {'raw': {'type': 'keyword'}}
                        if field.autocomplete:
                            subfields['suggest'] = {'type': 'search_as_you_type'}
                        mapping.field(field.name, field_type, analyzer=field.get_elasticsearch_analyzer(),
                                      fields=subfields)

                    # large text fields assumed too large to provide a "raw" subfield for sorting
                    elif field_type == 'large_text':
                        mapping.field(field.name, 'text', analyzer=field.get_elasticsearch_analyzer())

                    elif field.type == 'geo_point' and field.multiple:
                        mapping.field(field.name, GeoShape())

                    else:
                        mapping.field(field.name, field_type)

            index.mapping(mapping)
            index.save()

    def queue_local_job(self, content_type=None, content_id=None, task_id=None, task_name=None, scholar_id=None,
                        parameters={}):
        """
        Queue an asynchronous task for execution.

        Creates a job entry for background processing of tasks like reindexing,
        import/export, or custom operations using HUEY asynchronous task runners.

        Args:
            content_type (str): Target content type (None for corpus-level tasks).
            content_id (str): Specific content ID to process.
            task_id (str): Task definition ID.
            task_name (str): Task name (alternative to task_id).
            scholar_id (str): ID of user initiating the task.
            parameters (dict): Task-specific parameters.

        Returns:
            str: Job ID for tracking, or None if task not found.

        Examples:
            >>> # Launch the "Adjust Content" task so that it reindexes, relabels, and resaves every Book
            >>> my_corpus.queue_local_job(task_name="Adjust Content", parameters={
            ...     'content_type': 'Book',
            ...     'reindex': True,
            ...     'relabel': True,
            ...     'resave': True,
            ...     'related_content_types': "Author,Library"
            >>> })
        """

        # importing here to avoid circular dependency between Scholar and Corpus classes:
        from .scholar import Scholar

        local_jobsite = JobSite.objects(name='Local')[0]
        if task_name and not task_id:
            task_id = local_jobsite.task_registry[task_name]['task_id']

        if task_id:
            task = Task.objects(id=task_id)[0]
            scholar = None
            if scholar_id:
                scholar = Scholar.objects(id=scholar_id)[0]

            if not content_type and task.content_type == 'Corpus':
                content_type = 'Corpus'

            if content_type:
                job = Job()
                job.corpus = self
                job.task_id = str(task_id)
                job.content_type = content_type
                job.content_id = str(content_id) if content_id else None
                job.scholar = scholar
                job.jobsite = local_jobsite
                job.status = "queueing"
                job.configuration = deepcopy(task.configuration)

                for param in parameters.keys():
                    if param in job.configuration['parameters']:
                        job.configuration['parameters'][param]['value'] = parameters[param]

                job.save()
                return job.id
        return None

    def running_jobs(self):
        return Job.get_jobs(corpus_id=str(self.id))

    def import_content_crystal(self, path):
        content_path = None
        crystal_path = None
        last_step = path.split('/')[-1]

        if last_step.endswith('.json'):
            crystal_path = path
            content_path = os.path.dirname(path)
        else:
            content_path = path
            crystal_path = "{0}/{1}.json".format(path, last_step)

        if content_path and crystal_path and os.path.exists(content_path) and os.path.exists(crystal_path):
            content_dict = None
            with open(crystal_path, 'r', encoding='utf-8') as crystal_in:
                content_dict = json.load(crystal_in)

            if content_dict:
                ct_name = content_dict['content_type']
                if ct_name in self.content_types:
                    ct = self.content_types[ct_name]
                    old_corpus_id = content_dict['corpus_id']

                    content_json = None
                    with open(crystal_path, 'r', encoding='utf-8') as crystal_in:
                        content_json = crystal_in.read()

                    content_json = content_json.replace(old_corpus_id, str(self.id))
                    content_dict = json.loads(content_json)

                    content_obj = self.get_content(ct_name)
                    content_obj.id = ObjectId(content_dict['id'])
                    content_obj.label = content_dict['label']
                    content_obj.uri = content_dict['uri']

                    successfully_saved = False

                    if ct.inherited_from_module:
                        from_dict_method = getattr(content_obj, "from_dict", None)
                        if callable(from_dict_method):
                            content_obj.from_dict(content_dict)
                            content_obj.save()
                            successfully_saved = True
                    else:
                        all_fields_present = True
                        for field in ct.fields:
                            if field.name in content_dict:
                                setattr(content_obj, field.name, content_dict[field.name])
                            else:
                                all_fields_present = False
                                break

                        if all_fields_present:
                            content_obj.save()
                            successfully_saved = True

                    if successfully_saved:
                        content_files = [f for f in os.listdir(content_path) if not f.startswith('.')]
                        if len(content_files) > 1:
                            content_obj._make_path(force=True)
                            shutil.copytree(content_path, content_obj.path, dirs_exist_ok=True)

    def _make_path(self):
        corpus_path = "/corpora/{0}".format(self.id)
        os.makedirs("{0}/files".format(corpus_path), exist_ok=True)
        return corpus_path

    @property
    def redis_cache(self):
        if not hasattr(self, '_redis_cache'):
            setattr(self, '_redis_cache', redis.Redis(host=settings.REDIS_HOST, decode_responses=True))
        return self._redis_cache

    @classmethod
    def _post_save(cls, sender, document, **kwargs):

        if not document.uri:
            document.uri = "/corpus/{0}".format(document.id)
            document.path = document._make_path()
            document.update(**{'set__uri': document.uri, 'set__path': document.path})

        # Create node in Neo4j for corpus
        run_neo('''
                MERGE (c:Corpus { uri: $corpus_uri })
                SET c.name = $corpus_title
            ''',
                {
                    'corpus_uri': "/corpus/{0}".format(document.id),
                    'corpus_title': document.name
                }
                )

        # Add this corpus to Corpora Elasticsearch index
        get_connection().index(
            index='corpora',
            id=str(document.id),
            body={
                'name': document.name,
                'description': document.description,
                'open_access': document.open_access
            }
        )

    @classmethod
    def _pre_delete(cls, sender, document, **kwargs):
        corpus_id = str(document.id)

        # Delete any ContentViews associated with this corpus
        cvs = ContentView.objects(corpus=corpus_id)
        for cv in cvs:
            # set status to prevent CV audit from trying to repopulate while clearing
            cv.status = 'deleting'
            cv.save()
            cv.clear()
            cv.delete()

        # Delete Content Type indexes and collections
        for content_type in document.content_types.keys():
            # Delete ct index
            index_name = "corpus-{0}-{1}".format(corpus_id, content_type.lower())
            index = Index(index_name)
            if index.exists():
                index.delete()

            # Drop ct MongoDB collection
            document.content_types[content_type].get_mongoengine_class(document).drop_collection()

        # Delete all Neo4J nodes associated with corpus
        delete_count = 1
        while delete_count > 0:
            res = run_neo(
                '''
                    MATCH (x {corpus_id: $corpus_id})
                    WITH x LIMIT 5000
                    DETACH DELETE x
                    RETURN count(*)
                ''',
                {'corpus_id': corpus_id}
            )
            delete_count = res[0].value()

        # Delete the Neo4J corpus node
        run_neo(
            '''
                MATCH (x:Corpus {uri: $corpus_uri})
                DETACH DELETE x
            ''',
            {'corpus_uri': '/corpus/{0}'.format(corpus_id)}
        )

        # Delete any available_corpora entries in Scholar objects
        # Importing here to avoid circular dependency between Scholar and Corpus classes
        from .scholar import Scholar
        scholars = Scholar.objects
        scholars = scholars.batch_size(10)
        for scholar in scholars:
            if corpus_id in scholar.available_corpora.keys():
                del scholar.available_corpora[corpus_id]
                scholar.save()

        # Remove corpus from ES index
        es_corpus_doc = Search(index='corpora').query("match", _id=corpus_id)
        es_corpus_doc.delete()

        # Delete corpus files
        if os.path.exists(document.path):
            shutil.rmtree(document.path)

    def to_dict(self, include_views=False):
        """
        Export corpus configuration as a dictionary.

        Includes all content type definitions, configuration, and optionally
        content views. Useful for backup and migration.

        Args:
            include_views (bool): Whether to include ContentView definitions.

        Returns:
            dict: Complete corpus configuration.
        """

        corpus_dict = {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'path': self.path,
            'uri': self.uri,
            'kvp': deepcopy(self.kvp),
            'open_access': self.open_access,
            'files': {},
            'repos': {},
            'content_types': {},
        }

        for file_key in self.files:
            corpus_dict['files'][file_key] = self.files[file_key].to_dict(parent_uri=self.uri)

        for repo_name in self.repos:
            corpus_dict['repos'][repo_name] = self.repos[repo_name].to_dict()

        for ct_name in self.content_types:
            corpus_dict['content_types'][ct_name] = self.content_types[ct_name].to_dict()

        if include_views:
            content_views = ContentView.objects(corpus=self.id, status__in=['populated', 'needs_refresh']).order_by(
                'name')
            for cv in content_views:
                if cv.target_ct in corpus_dict['content_types']:
                    if 'views' not in corpus_dict['content_types'][cv.target_ct]:
                        corpus_dict['content_types'][cv.target_ct]['views'] = []
                    corpus_dict['content_types'][cv.target_ct]['views'].append(cv.to_dict())

            corpus_dict['content_type_groups'] = [ctg.to_dict() for ctg in self.content_type_groups]

        corpus_dict['provenance'] = [prov.to_dict() for prov in self.provenance]

        return corpus_dict

    meta = {
        'indexes': [
            'open_access',
            {
                'fields': ['id', 'content_types.name'],
                'unique': True,
                'sparse': True
            },
            {
                'fields': ['id', 'content_types.plural_name'],
                'unique': True,
                'sparse': True
            },
            {
                'fields': ['id', 'content_types.name', 'content_types.fields.name'],
                'unique': True,
                'sparse': True
            }
        ]
    }


# rig up post save and delete signals for Corpus
mongoengine.signals.post_save.connect(Corpus._post_save, sender=Corpus)
mongoengine.signals.pre_delete.connect(Corpus._pre_delete, sender=Corpus)


class CorpusBackup(mongoengine.Document):
    """
    Describes a snapshot in time of a given corpus, ultimately in the form of a tarball containing
    Corpus metadata like Content Type definitions, MongoDB dumps for each collection of content,
    and any associated file structures and files for the corpus.

    Useful for registering a backup of a corpus that allows you to restore from a certain
    point in time. The backup tarball it describes works across instances of Corpora.

    Attributes:
        corpus_id (str): The unique ID of this corpus in the form of a string representation of an ObjectId
        corpus_name (str): The name (typically an acronymn) for this corpus
        corpus_description (str): The description (typically what the acronymn stands for) of this corpus
        name (str): The name of this backup; typically a string representation of the date the backup was made
        path (str): The path to the tarball file containing the backed-up data for this corpus
        status (str): Whether it's being created, has been created, or is being restored
        created (datetime): When this backup was created.

    Examples:
        >>> # Registering an existing backup
        >>> backup = CorpusBackup(
        ...     corpus_id='5f623f2a52023c009d73108e'
        ...     corpus_name='MTC',
        ...     corpus_description='My Test Corpus',
        ...     name='2025_06_05',
        ...     path='/corpora/backups/5f623f2a52023c009d73108e_2025_06_05.tar.gz'
        ...     status='created',
        ...     created=datetime.now()
        ... )
        >>> backup.save()
    """

    corpus_id = mongoengine.StringField()
    corpus_name = mongoengine.StringField()
    corpus_description = mongoengine.StringField()
    name = mongoengine.StringField(unique_with='corpus_id')
    path = mongoengine.StringField()
    status = mongoengine.StringField()
    created = mongoengine.DateTimeField(default=datetime.now)

    def to_dict(self):
        return {
            'id': str(self.id),
            'corpus_id': self.corpus_id,
            'corpus_name': self.corpus_name,
            'corpus_description': self.corpus_description,
            'name': self.name,
            'path': self.path,
            'status': self.status,
            'created': int(self.created.timestamp())
