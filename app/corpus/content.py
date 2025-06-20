import os
import shutil
import json
import re
import traceback
import mongoengine
from typing import TYPE_CHECKING
from bson import ObjectId
from datetime import datetime
from django.conf import settings
from django.template import Template, Context
from django.utils.text import slugify
from elasticsearch_dsl import Search, Index
from elasticsearch_dsl.connections import get_connection
from .utilities import run_neo
from .field_types.file import File
from .job import CompletedTask
from .scholar import Scholar


if TYPE_CHECKING:
    from .corpus import Corpus


class Content(mongoengine.Document):
    """
    Base class for all content instances within a corpus.

    Content objects are dynamically extended based on their ContentType definition.
    They support automatic labeling, URI generation, full-text indexing, and
    graph relationship management.

    Attributes:
        corpus_id (str): ID of the parent Corpus.
        content_type (str): Name of the ContentType.
        last_updated (datetime): Timestamp of last modification.
        provenance (list[CompletedTask]): Audit trail of operations.
        field_intensities (dict): Weights for cross-reference relationships.
        path (str): File system path for associated files.
        label (str): Computed display label from template.
        uri (str): Unique resource identifier.

    Note:
        This is an abstract base class. Actual content classes are generated
        dynamically by ContentType.get_mongoengine_class().

    Examples:
        >>> # Content instances are typically created via Corpus.get_content()
        >>> article = corpus.get_content('Article')
        >>> article.title = "Introduction to Machine Learning"
        >>> article.author = author_instance  # Cross-reference
        >>> article.save()

        >>> # Access computed properties
        >>> print(article.label)  # "Introduction to Machine Learning"
        >>> print(article.uri)    # "/corpus/123/Article/456"
    """

    corpus_id = mongoengine.StringField(required=True)
    content_type = mongoengine.StringField(required=True)
    last_updated = mongoengine.DateTimeField(default=datetime.now())
    provenance = mongoengine.EmbeddedDocumentListField(CompletedTask)
    field_intensities = mongoengine.DictField(default={})
    path = mongoengine.StringField()
    label = mongoengine.StringField()
    uri = mongoengine.StringField()

    def get_intensity(self, field_name, value):
        if hasattr(self, field_name):
            if type(value) is ObjectId:
                value = str(ObjectId)
            elif hasattr(value, 'id'):
                value = str(value.id)

            if type(value) is str:
                return self.field_intensities.get('{field_name}-{value}'.format(field_name=field_name, value=value), 0)
        return 0

    def set_intensity(self, field_name, value, intensity):
        if hasattr(self, field_name):
            if type(value) is ObjectId:
                value = str(ObjectId)
            elif hasattr(value, 'id'):
                value = str(value.id)

            if type(value) is str:
                self.field_intensities['{field_name}-{value}'.format(field_name=field_name, value=value)] = int(intensity)

    @property
    def referencing_content(self):
        """
        Generator that yields information about other content that references this instance of content.

        Yields:
            dict: Containing the content type, id, label, referencing field, and whether that field is multivalued.
        """

        skip = 0
        batch_size = 1000

        while True:
            cypher = f"""
                MATCH (source)-[r]->(c:{self.content_type} {{uri: '{self.uri}'}})
                RETURN source, labels(source) as content_type, type(r) as relationship_type
                ORDER BY id(source)
                SKIP $skip LIMIT $limit
                """

            params = {
                "skip": skip,
                "limit": batch_size
            }

            results = run_neo(cypher, params)

            if not results:
                break

            for record in results:
                content_stub = dict(record['source'])
                content_stub['content_type'] = record['content_type'][0]
                content_stub['referencing_field'] = record['relationship_type'][3:]

                if content_stub['content_type'] in self._corpus.content_types:
                    referencing_field = self._corpus.content_types[content_stub['content_type']].get_field(content_stub['referencing_field'])
                    if referencing_field:
                        content_stub['referencing_field_multivalued'] = referencing_field.multiple

                yield content_stub

            # If we got fewer results than batch_size, we're done
            if len(results) < batch_size:
                break

            skip += batch_size

    @property
    def is_orphan(self):
        """
        Checks whether other content references this content.

        Uses the Neo4J graph database to query for inbound connections from other content.

        Returns:
            Boolean: True if no content references this content.
        """

        try:
            cypher = '''
                MATCH (c:{0} {{uri: '{1}'}}) <-[r]- ()
                RETURN count(r) as count
            '''.format(self.content_type, self.uri)

            count = run_neo(cypher)

            return count[0].value() == 0
        except:
            print(traceback.format_exc())
            return False

    @classmethod
    def _pre_save(cls, sender, document, **kwargs):
        document.last_updated = datetime.now()

    def save(self, do_indexing=True, do_linking=True, relabel=True, **kwargs):
        """
        Save content with automatic processing.

        Handles label generation, file path creation (if necessary), Elasticsearch indexing, and
        Neo4j graph linking. Can selectively disable processing for performance.

        Args:
            do_indexing (bool | list): Update search index. Can be field list.
            do_linking (bool): Update graph relationships.
            relabel (bool): Regenerate label from template.
            **kwargs: Additional arguments passed to MongoEngine save.
        """

        super().save(**kwargs)
        label_created = self._make_label(relabel)
        path_created = self._make_path()
        uri_created = self._make_uri()

        if path_created or label_created or uri_created:
            self.update(
                set__path=self.path,
                set__label=self.label,
                set__uri=self.uri
            )

        if do_indexing or do_linking:
            cx_fields = [field.name for field in self._ct.fields if field.type == 'cross_reference']
            if isinstance(do_indexing, list):
                cx_fields = [f for f in cx_fields if f in do_indexing]

            geo_fields = [field.name for field in self._ct.fields if field.type == 'geo_point']
            if isinstance(do_indexing, list):
                geo_fields = [f for f in geo_fields if f in do_indexing]

            if cx_fields:
                self.reload(*cx_fields)
            if geo_fields:
                self.reload(*geo_fields)

            if do_indexing:
                if isinstance(do_indexing, list):
                    self._do_indexing(do_indexing)
                else:
                    self._do_indexing()
            if do_linking:
                self._do_linking()

    def delete(self, track_deletions=True, unindex=True, unlink=True, **kwargs):
        """
        Delete content with cleanup.

        Removes the content from MongoDB, Elasticsearch, and Neo4j, and
        tracks deletions for referential integrity cleanup. The cleanup logic is found in the
        _pre_delete method of this class which is called in response to the pre-delete event
        rigged up by the signals library.

        Args:
            track_deletions (bool): Create deletion record for cleaning up any references to this content throughout the corpus.
            unindex (bool): Remove from search index.
            unlink (bool): Remove from graph database.
            **kwargs: Additional arguments passed to MongoEngine delete.
        """

        setattr(self, '_track_deletions', track_deletions)
        setattr(self, '_unindex', unindex)
        setattr(self, '_unlink', unlink)
        super().delete(**kwargs)

    @classmethod
    def _pre_delete(cls, sender, document, **kwargs):
        if (document._unlink):
            # delete Neo4J node
            run_neo(
                '''
                    MATCH (d:{content_type} {{ uri: $content_uri }})
                    DETACH DELETE d
                '''.format(content_type=document.content_type),
                {
                    'content_uri': document.uri
                }
            )

        if (document._unindex):
            # delete from ES index
            es_index = "corpus-{0}-{1}".format(document.corpus_id, document.content_type.lower())
            Search(index=es_index).query("match", _id=str(document.id)).delete()

        # determine if deletion cleanup needed
        if hasattr(document, '_track_deletions') and document._track_deletions:
            # mark any relevant content views as needs_refresh
            cvs = ContentView.objects(corpus=document._corpus, status='populated', relevant_cts=document.content_type)
            for cv in cvs:
                cv.set_status('needs_refresh')
                cv.save()

            reffing_cts = document._corpus.get_referencing_content_type_fields(document.content_type)
            if reffing_cts or document.path:
                deletion = ContentDeletion()
                if reffing_cts:
                    deletion.uri = document.uri
                if document.path:
                    deletion.path = document.path
                deletion.save()

    def _make_label(self, force=True):
        if force or not self.label:
            # make sure that if template is referencing cross_reference fields, we reload from database
            if re.search(r'{{[^}\.]*\.[^}\.]*\.[^}]*}}', self._ct.templates['Label'].template):
                self.reload()

            label_template = Template(self._ct.templates['Label'].template)
            context = Context({self.content_type: self})
            self.label = label_template.render(context)
            return True
        return False

    def _make_uri(self):
        new_uri = self.uri

        if self._ct.proxy_field:
            proxy_field = self._ct.get_field(self._ct.proxy_field)
            proxy_field_value = getattr(self, self._ct.proxy_field)

            if proxy_field and \
                    proxy_field.multiple is False and \
                    proxy_field.cross_reference_type and \
                    proxy_field_value:
                proxy_ct = proxy_field.cross_reference_type
                proxy_id = proxy_field_value.id
                new_uri = "/corpus/{0}/{1}/{2}".format(self.corpus_id, proxy_ct, proxy_id)
        else:
            new_uri = "/corpus/{0}/{1}/{2}".format(
                self.corpus_id,
                self.content_type,
                self.id
            )

        if new_uri != self.uri:
            self.uri = new_uri
            return True
        return False

    def _make_path(self, force=False):
        if not self.path and (self._ct.has_file_field or force):
            breakout_dir = str(self.id)[-6:-2]
            self.path = "/corpora/{0}/{1}/{2}/{3}".format(self.corpus_id, self.content_type, breakout_dir, self.id)
            os.makedirs(self.path + "/files", exist_ok=True)
            return True
        return False

    def _move_temp_file(self, field_name, field_index=None, new_basename=None):
        field = self._ct.get_field(field_name)
        file = None
        new_path = f"{self.path}/files/{field_name}"
        new_file = None

        if field:
            if field.multiple and field_index is not None:
                file = getattr(self, field_name)[field_index]
                new_path += str(field_index)
            else:
                file = getattr(self, field_name)

            if file and file.path.startswith(settings.DJANGO_DRF_FILEPOND_UPLOAD_TMP):
                # Make sure the folder for this new file doesn't already exist. If so,
                # we need to create a different one
                unique_path = new_path
                unique_path_modifier = 1
                while os.path.exists(unique_path):
                    unique_path = f"{new_path}-{unique_path_modifier}"
                    unique_path_modifier += 1
                new_path = unique_path

                # Create the new path
                os.makedirs(new_path)

                old_path = file.path
                if new_basename:
                    new_path = f"{new_path}/{new_basename}"
                else:
                    new_path = f"{new_path}/{os.path.basename(old_path)}"

                os.rename(old_path, new_path)

                new_file = File.process(
                    new_path,
                    parent_uri=self.uri,
                    desc=file.description,
                    prov_type=file.provenance_type,
                    prov_id=file.provenance_id
                )

            if file and new_file:
                file._unlink(self.uri)

                if field.multiple and field_index is not None:
                    getattr(self, field_name)[field_index] = new_file
                else:
                    setattr(self, field_name, new_file)

    def _do_indexing(self, field_list=[]):
        index_obj = {}
        for field in self._ct.fields:
            if field.in_lists and (len(field_list) == 0 or field.name in field_list):
                field_value = getattr(self, field.name)
                if field_value or ((field.type == 'number' or field.type == 'decimal') and field_value == 0):
                    if field.cross_reference_type:
                        if field.multiple:
                            field_value = []
                            for xref in getattr(self, field.name):
                                xref_dict = {
                                    'id': str(xref.id),
                                    'label': xref.label,
                                    'uri': xref.uri
                                }

                                if field.has_intensity:
                                    xref_dict['intensity'] = self.field_intensities.get(
                                        '{field_name}-{val_id}'.format(field_name=field.name, val_id=xref.id),
                                        1
                                    )

                                for xref_field in self._corpus.content_types[field.cross_reference_type].fields:
                                    if xref_field.in_lists and not xref_field.cross_reference_type:
                                        xref_dict[xref_field.name] = xref_field.get_dict_value(getattr(xref, xref_field.name), xref.uri)
                                field_value.append(xref_dict)
                        else:
                            xref = field_value
                            field_value = {
                                'id': str(xref.id),
                                'label': xref.label,
                                'uri': xref.uri
                            }

                            if field.has_intensity:
                                field_value['intensity'] = self.field_intensities.get(
                                    '{field_name}-{val_id}'.format(field_name=field.name, val_id=xref.id),
                                    1
                                )

                            for xref_field in self._corpus.content_types[field.cross_reference_type].fields:
                                if xref_field.in_lists and xref_field.type != "cross_reference":
                                    if xref_field.type == 'file':
                                        if xref_field.multiple:
                                            field_value[xref_field.name] = [f.path for f in getattr(xref, xref_field.name) if hasattr(f, 'path')]
                                        elif hasattr(getattr(xref, xref_field.name), 'path'):
                                            field_value[xref_field.name] = getattr(xref, xref_field.name).path

                                    elif xref_field.type == 'geo_point' and xref_field.multiple:
                                        field_value[xref_field.name] = {
                                            'type': 'MultiPoint',
                                            'coordinates': [v['coordinates'] for v in getattr(xref, xref_field.name)]
                                        }
                                    else:
                                        field_value[xref_field.name] = xref_field.get_dict_value(getattr(xref, xref_field.name), xref.uri)

                        index_obj[field.name] = field_value

                    elif field.type == 'file' and hasattr(field_value, 'path'):
                        index_obj[field.name] = field_value.path

                    elif field.type == 'geo_point' and field.multiple:
                        index_obj[field.name] = {
                            'type': 'MultiPoint',
                            'coordinates': [v['coordinates'] for v in field_value]
                        }

                    elif field.type not in ['file']:
                        index_obj[field.name] = field.get_dict_value(field_value, self.uri)

        if len(field_list) == 0 or 'label' in field_list:
            index_obj['label'] = self.label
        if len(field_list) == 0 or 'uri' in field_list:
            index_obj['uri'] = self.uri

        try:
            if len(field_list) == 0:
                get_connection().index(
                    index="corpus-{0}-{1}".format(self.corpus_id, self.content_type.lower()),
                    id=str(self.id),
                    body=index_obj
                )
            elif index_obj:
                get_connection().update(
                    index="corpus-{0}-{1}".format(self.corpus_id, self.content_type.lower()),
                    id=str(self.id),
                    body={'doc': index_obj}
                )
        except:
            print("Error indexing {0} with ID {1}:".format(self.content_type, self.id))
            print(traceback.format_exc())

    def _do_linking(self):
        # here we're making sure the node exists
        run_neo(
            '''
                MERGE (d:{content_type} {{ uri: $content_uri }})
                SET d.id = $content_id
                SET d.corpus_id = $corpus_id
                SET d.label = $content_label
            '''.format(content_type=self.content_type),
            {
                'corpus_id': str(self.corpus_id),
                'content_uri': self.uri,
                'content_id': str(self.id),
                'content_label': self.label
            }
        )

        # here we're deleting all outbound relationships (they will be rebuilt below as necessary);
        # this is to ensure changed or deleted cross references are reflected in the graph (no stale
        # relationships)
        run_neo(
            '''
                MATCH (d:{content_type} {{ uri: $content_uri }}) -[rel]-> ()
                DELETE rel
            '''.format(content_type=self.content_type),
            {
                'content_uri': self.uri,
            }
        )

        nodes = {}
        for field in self._ct.fields:
            field_value = getattr(self, field.name)
            if field_value:
                if field.cross_reference_type:
                    cross_ref_type = field.cross_reference_type
                    if cross_ref_type not in nodes:
                        nodes[cross_ref_type] = []

                    if field.multiple:
                        for cross_ref in field_value:
                            node_dict = {
                                'id': cross_ref.id,
                                'uri': cross_ref.uri,
                                'label': cross_ref.label,
                                'field': field.name
                            }

                            if field.has_intensity:
                                node_dict['intensity'] = self.field_intensities.get(
                                    '{field_name}-{val_id}'.format(field_name=field.name, val_id=cross_ref.id),
                                    1
                                )

                            nodes[cross_ref_type].append(node_dict)
                    else:
                        node_dict = {
                            'id': field_value.id,
                            'uri': field_value.uri,
                            'label': field_value.label,
                            'field': field.name
                        }

                        if field.has_intensity:
                            node_dict['intensity'] = self.field_intensities.get(
                                '{field_name}-{val_id}'.format(field_name=field.name, val_id=field_value.id),
                                1
                            )

                        nodes[cross_ref_type].append(node_dict)

                elif field.multiple and hasattr(field_value, 'keys'):
                    for field_key in field_value.keys():
                        mapped_value = field_value[field_key]
                        if hasattr(mapped_value, '_do_linking'):
                            mapped_value._do_linking(self._ct.name, self.uri)

                elif field.multiple:
                    for list_value in field_value:
                        if hasattr(list_value, '_do_linking'):
                            list_value._do_linking(self._ct.name, self.uri)

                elif hasattr(field_value, '_do_linking'):
                    field_value._do_linking(self._ct.name, self.uri)

        if nodes:
            for node_label in nodes.keys():
                for node in nodes[node_label]:
                    intensity_specifier = ''
                    if 'intensity' in node:
                        intensity_specifier = ' {{ intensity: {0} }}'.format(node['intensity'])

                    run_neo(
                        '''
                            MERGE (a:{content_type} {{ uri: $content_uri }})
                            MERGE (b:{cx_type} {{ uri: $cx_uri }})
                            MERGE (a)-[rel:has{field}{intensity_specifier}]->(b)
                        '''.format(
                            content_type=self.content_type,
                            cx_type=node_label,
                            field=node['field'],
                            intensity_specifier=intensity_specifier
                        ),
                        {
                            'content_uri': self.uri,
                            'cx_uri': node['uri']
                        }
                    )

    def to_dict(self, ref_only=False):
        content_dict = {
            'corpus_id': self.corpus_id,
            'content_type': self.content_type,
            'id': str(self.id),
            'last_updated': int(self.last_updated.timestamp()),
            'label': self.label,
            'uri': self.uri
        }

        if not ref_only:
            content_dict['provenance'] = [prov.to_dict() for prov in self.provenance]

            for field in self._ct.fields:
                content_dict[field.name] = field.get_dict_value(getattr(self, field.name), self.uri, self.field_intensities)

        return content_dict

    def from_dict(self, field_values):
        for field in field_values.keys():
            if field == 'id':
                field_values[field] = ObjectId(field_values[field])
            if field in ['corpus_id', 'uri']:
                continue
            setattr(self, field, field_values[field])

    def crystalize(self):
        if not self.path:
            self._make_path(force=True)
            self.update(set__path=self.path)

        make_crystal = True
        crystal_path = "{0}/{1}.json".format(self.path, self.id)
        if os.path.exists(crystal_path):
            crystal_updated = datetime.fromtimestamp(os.path.getmtime(crystal_path))
            if crystal_updated > self.last_updated:
                make_crystal = False

        if make_crystal:
            with open(crystal_path, 'w', encoding='utf-8') as crystal_out:
                json.dump(self.to_dict(), crystal_out, indent=4)

    meta = {
        'abstract': True
    }


class ContentView(mongoengine.Document):
    corpus = mongoengine.ReferenceField('Corpus')
    created_by = mongoengine.ReferenceField(Scholar)
    name = mongoengine.StringField(unique_with='corpus')
    target_ct = mongoengine.StringField()
    relevant_cts = mongoengine.ListField(mongoengine.StringField())
    search_filter = mongoengine.StringField()
    graph_path = mongoengine.StringField()
    es_document_id = mongoengine.StringField()
    neo_super_node_uri = mongoengine.StringField()
    status = mongoengine.StringField()
    status_date = mongoengine.DateTimeField(default=datetime.now())

    def set_status(self, status):
        self.status = status
        self.status_date = datetime.now()

    def populate(self):
        valid_spec = True
        filtered_with_graph_path = False
        es_conn = get_connection()
        index = Index('content_view')

        if index.exists() and \
                self.name and \
                self.corpus and \
                self.target_ct in self.corpus.content_types:

            ids = []
            graph_steps = {}

            if not self.es_document_id or not self.neo_super_node_uri:
                name_slug = slugify(self.name).replace('-', '_')
                view_identifier = "corpus_{0}_{1}".format(self.corpus.id, name_slug)
                self.es_document_id = view_identifier
                self.neo_super_node_uri = "/contentview/{0}".format(view_identifier)
            else:
                run_neo("MATCH (supernode:ContentView { uri: $cv_uri }) DETACH DELETE supernode", {'cv_uri': self.neo_super_node_uri})

            self.relevant_cts = [self.target_ct]
            self.set_status("populating")
            self.save()

            if self.graph_path:
                ct_pattern = re.compile(r'\(([a-zA-Z]*)')
                ids_pattern = re.compile(r'\[([^\]]*)\]')

                graph_step_specs = [step for step in self.graph_path.split(' ') if step]

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

                    if step_ct and step_ct in self.corpus.content_types:
                        graph_steps[step_index] = {
                            'direction': step_direction,
                            'ct': step_ct,
                            'ids': step_ids
                        }
                        self.relevant_cts.append(step_ct)
                    else:
                        valid_spec = False
                        break

                if graph_steps and valid_spec:
                    cypher = "MATCH (target:{0})".format(self.target_ct)
                    where_clauses = []

                    for step_index, step_info in graph_steps.items():
                        cypher += " {0} (ct{1}:{2})".format(step_info['direction'], step_index, step_info['ct'])
                        if step_info['ids']:
                            step_uris = ['/corpus/{0}/{1}/{2}'.format(self.corpus.id, step_info['ct'], ct_id) for ct_id in step_info['ids']]
                            where_clauses.append("ct{0}.uri in ['{1}']".format(
                                step_index,
                                "','".join(step_uris)
                            ))

                    if where_clauses:
                        cypher += "\nWHERE {0}".format(" AND ".join(where_clauses))

                    count_cypher = cypher + "\nRETURN count(distinct target)"
                    data_cypher = cypher + "\nRETURN distinct target.uri"

                    print(count_cypher)

                    try:
                        count_results = run_neo(count_cypher, {})
                        count = count_results[0].value()

                        print(count)

                        if count <= 60000:
                            data_results = run_neo(data_cypher, {})
                            ids = [res.value().split('/')[-1] for res in data_results]
                            es_conn.index(
                                index='content_view',
                                id=self.es_document_id,
                                body={
                                    'ids': ids,
                                }
                            )

                            filtered_with_graph_path = True
                        else:
                            valid_spec = False
                            self.set_status("error: content views must contain less than 60,000 results")

                    except:
                        print(traceback.format_exc())
                        valid_spec = False
                        self.set_status("error")
                        self.save()

                else:
                    print("Invalid pattern of association for content view!")

            if self.search_filter and valid_spec and self.status == 'populating':

                search_dict = json.loads(self.search_filter)

                # determine if this search filter has any actual criteria specified
                criteria_specified = False
                if 'general_query' in search_dict and search_dict['general_query'] != '*':
                    criteria_specified = True

                if not criteria_specified:
                    for criteria in search_dict.keys():
                        if criteria.startswith('fields_') and search_dict[criteria]:
                            criteria_specified = True

                if criteria_specified:
                    if filtered_with_graph_path:
                        search_dict['content_view'] = self.es_document_id

                    search_dict['page_size'] = 1000
                    search_dict['only'] = ['id']

                    ids = []
                    page = 1
                    num_pages = 1

                    while page <= num_pages and valid_spec:
                        search_dict['page'] = page
                        results = self.corpus.search_content(self.target_ct, **search_dict)
                        if results:
                            if results['meta']['num_pages'] > num_pages:
                                num_pages = results['meta']['num_pages']

                            if results['meta']['total'] <= 60000:
                                for record in results['records']:
                                    ids.append(record['id'])
                            else:
                                valid_spec = False
                                self.set_status("error: content views must contain less than 60,000 results")

                            if 'next_page_token' in results['meta']:
                                search_dict['next_page_token'] = results['meta']['next_page_token']

                        page += 1

                if valid_spec:
                    es_conn.index(
                        index='content_view',
                        id=self.es_document_id,
                        body={
                            'ids': ids,
                        }
                    )

            if valid_spec and ids:
                total = len(ids)
                cursor = 0
                window = 1000

                run_neo("MERGE (cv:_ContentView { uri: $cv_uri })", {'cv_uri': self.neo_super_node_uri})

                supernode_cypher = '''
                    MATCH (cv:_ContentView {{ uri: $cv_uri }}), (target:{0})
                    WHERE target.uri IN $uris 
                    MERGE (cv) -[rel:hasContent]-> (target)
                '''.format(self.target_ct)

                while cursor < total:
                    uris = ["/corpus/{0}/{1}/{2}".format(self.corpus.id, self.target_ct, id) for id in ids[cursor:window]]
                    run_neo(
                        supernode_cypher,
                        {
                            'cv_uri': self.neo_super_node_uri,
                            'uris': uris
                        }
                    )
                    cursor += window
                self.set_status("populated")

            self.save()

    def clear(self):
        # delete ES content_view document
        Search(index='content_view').query('match', _id=self.es_document_id).delete()

        # delete Neo super node
        run_neo(
            '''
                MATCH (cv:_ContentView { uri: $cv_uri })
                DETACH DELETE cv
            ''',
            {
                'cv_uri': self.neo_super_node_uri
            }
        )

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'es_document_id': self.es_document_id,
            'neo_super_node_uri': self.neo_super_node_uri,
            'target_ct': self.target_ct,
            'status': self.status
        }


class ContentDeletion(mongoengine.Document):
    uri = mongoengine.StringField()
    path = mongoengine.StringField()

    @property
    def corpus_id(self):
        if self.uri and self.uri.count('/') == 4:
            return self.uri.split('/')[2]
        return None

    @property
    def content_type(self):
        if self.uri and self.uri.count('/') == 4:
            return self.uri.split('/')[3]
        return None

    @property
    def content_id(self):
        if self.uri and self.uri.count('/') == 4:
            return self.uri.split('/')[4]
        return None
