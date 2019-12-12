import os
import json
import mongoengine
from mongoengine.queryset.visitor import Q
import logging
import traceback
import shutil
from time import sleep
from bson import ObjectId
from elasticsearch_dsl import Search, Q
from elasticsearch_dsl.query import SimpleQueryString
from elasticsearch_dsl.connections import get_connection
from django.template import Template, Context
from django.conf import settings
from .tasks import index_content, run_xml_transforms, build_indexes
from corpus import Corpus

FIELD_TYPES = ('text', 'html', 'choice', 'number', 'date', 'file', 'image', 'link', 'cross_reference')
RESERVED_FIELD_NAMES = [
    'type',
    'created_by',
    'created_timestamp',
    'updated_timestamp',
    'versions'
]
DEFAULT_TEMPLATE_FORMATS = [
    {
        'extension': 'html',
        'label': 'HTML',
        'mime_type': 'text/html',
        'ace_editor_mode': 'django'
    },
    {
        'extension': 'js',
        'label': 'Javascript',
        'mime_type': 'text/javascript',
        'ace_editor_mode': 'django'
    }
]


class TemplateFormat(mongoengine.Document):
    corpus = mongoengine.ReferenceField(Corpus, required=True)
    extension = mongoengine.StringField(required=True)
    label = mongoengine.StringField(required=True)
    mime_type = mongoengine.StringField(default='text/html')
    ace_editor_mode = mongoengine.StringField(default='django')

    meta = {
        'indexes': [
            'corpus',
            {
                'fields': ['corpus', 'extension', 'label'],
                'unique': True
            },
        ]
    }


class Field(mongoengine.EmbeddedDocument):
    name = mongoengine.StringField(required=True)
    label = mongoengine.StringField()
    indexed = mongoengine.BooleanField(default=False)
    unique = mongoengine.BooleanField(default=False)
    multiple = mongoengine.BooleanField(default=False)
    in_lists = mongoengine.BooleanField(default=True)
    type = mongoengine.StringField(choices=FIELD_TYPES)
    choices = mongoengine.ListField()
    cross_reference_type = mongoengine.ReferenceField('ContentType')
    indexed_with = mongoengine.ListField()
    unique_with = mongoengine.ListField()
    stats = mongoengine.DictField()


class ContentType(mongoengine.Document):
    corpus = mongoengine.ReferenceField(Corpus, required=True)
    name = mongoengine.StringField(required=True)
    plural_name = mongoengine.StringField(required=True)
    fields = mongoengine.EmbeddedDocumentListField('Field') # TODO: make fields a MapField
    show_in_nav = mongoengine.BooleanField(default=True)
    proxy_field = mongoengine.StringField()
    templates = mongoengine.DictField()

    def get_field_skeleton(self, only=[]):
        fields = {}
        for field in self.fields:
            if not only or field.name in only:
                cross_reference_type = field.cross_reference_type
                if cross_reference_type:
                    cross_reference_type = cross_reference_type.name

                fields[field.name] = {
                    'label': field.label,
                    'value': '',
                    'type': field.type,
                    'cross_reference_type': cross_reference_type,
                    'multiple': field.multiple
                }
        return fields

    def get_field(self, field_name):
        for index in range(0, len(self.fields)):
            if self.fields[index].name == field_name:
                return self.fields[index]
        return None

    def get_field_stats(self):
        stats = {}
        for field in self.fields:
            stats[field.name] = field.stats
            stats[field.name]['type'] = field.type
        return stats

    @property
    def mongoengine_class(self):
        if not hasattr(self, '_mongoengine_class'):
            class_dict = {
                '_label': mongoengine.StringField(),
                '_url': mongoengine.StringField()
            }
            indexes = []

            for field in self.fields:

                if field.type == 'number':
                    if field.unique and not field.unique_with:
                        class_dict[field.name] = mongoengine.IntField(unique=True)
                    else:
                        class_dict[field.name] = mongoengine.IntField()
                elif field.type == 'date':
                    if field.unique and not field.unique_with:
                        class_dict[field.name] = mongoengine.DateField(unique=True)
                    else:
                        class_dict[field.name] = mongoengine.DateField()
                elif field.type == 'cross_reference':
                    xref_class = ContentType.objects(corpus=self.corpus, name=field.cross_reference_type.name)[
                        0].mongoengine_class

                    if field.unique and not field.unique_with:
                        class_dict[field.name] = mongoengine.ReferenceField(xref_class, unique=True)
                    else:
                        class_dict[field.name] = mongoengine.ReferenceField(xref_class)
                else:
                    if field.unique and not field.unique_with:
                        class_dict[field.name] = mongoengine.StringField(unique=True)
                    else:
                        class_dict[field.name] = mongoengine.StringField()

                if field.unique_with:
                    indexes.append({
                        'fields': [field.name] + [unique_with for unique_with in field.unique_with],
                        'unique': True,
                        'sparse': True
                    })

                if field.indexed:
                    if field.indexed_with:
                        indexes.append({
                            'fields': [field.name] + [indexed_with for indexed_with in field.indexed_with],
                        })
                    else:
                        indexes.append(field.name)

                if field.multiple:
                    class_dict[field.name] = mongoengine.ListField(class_dict[field.name])

            class_dict['meta'] = {
                'indexes': indexes,
                'collection': "corpus_{0}_{1}".format(self.corpus.id, self.name)
            }

            self._mongoengine_class = type(
                self.name,
                (mongoengine.Document,),
                class_dict
            )
        return self._mongoengine_class

    def clear_field(self, field_name):
        if field_name in [field.name for field in self.fields]:
            self.mongoengine_class.objects.update(**{'set__{0}'.format(field_name): None})

    def delete_field(self, field_name):
        if field_name in [field.name for field in self.fields]:
            self.clear_field(field_name)

            # find and delete field or references to field
            field_index = -1
            for x in range(0, len(self.fields)):
                if self.fields[x].name == field_name:
                    field_index = x
                else:
                    if field_name in self.fields[x].unique_with:
                        self.fields[x].unique_with.remove(field_name)
                    if field_name in self.fields[x].indexed_with:
                        self.fields[x].indexed_with.remove(field_name)
            if field_index > -1:
                self.fields.pop(field_index)
                self.save()

            # delete any indexes referencing field, then drop field from collection
            print('field cleared. now attemtpting to drop indexes...')
            collection_name = "corpus_{0}_{1}".format(self.corpus.id, self.name)
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
            db[collection_name].update({}, {'$unset': {field_name: 1}}, multi=True)

    def delete(self):
        self.mongoengine_class.drop_collection()
        super().delete()

    meta = {
        'indexes': [
            'corpus',
            {
                'fields': ['corpus', 'name'],
                'unique': True,
            },
            {
                'fields': ['corpus', 'plural_name'],
                'unique': True,
            },
            {
                'fields': ['corpus', 'name', 'fields.name'],
                'unique': True,
                'sparse': True
            }
        ]
    }


class Content(object):
    content_type = None
    instance = None
    id = None
    fields = [] # TODO: Make fields a dict

    def __init__(self, corpus_id, content_type, id=None, instance=None, only=[]):

        if isinstance(content_type, str):
            try:
                self.content_type = ContentType.objects(corpus=corpus_id, name=content_type)[0]
            except:
                logging.error(traceback.format_exc())
                self.content_type = None
        else:
            self.content_type = content_type

        if self.content_type:
            self.fields = self.content_type.get_field_skeleton(only)

            if id:
                if not instance:
                    self.instance = self.content_type.mongoengine_class.objects(id=id).only(*only)[0]
                else:
                    self.instance = instance

                if self.instance:
                    self.id = str(self.instance.id)
                    self.label = self.instance._label
                    self.url = self.instance._url
                    for field in self.fields.keys():
                        if hasattr(self.instance, field):
                            if self.fields[field]['multiple']:
                                self.fields[field]['value'] = []
                                for value_index in range(0, len(getattr(self.instance, field))):
                                    if self.fields[field]['cross_reference_type']:
                                        self.fields[field]['value'].append({
                                            'id': str(getattr(self.instance, field)[value_index].id),
                                            'label': getattr(self.instance, field)[value_index]._label,
                                            'url': getattr(self.instance, field)[value_index]._url
                                        })
                                    else:
                                        self.fields[field]['value'].append(getattr(self.instance, field)[value_index])
                            elif self.fields[field]['cross_reference_type'] and getattr(self.instance, field):
                                self.fields[field]['value'] = {
                                    'id': str(getattr(self.instance, field).id),
                                    'label': getattr(self.instance, field)._label,
                                    'url': getattr(self.instance, field)._url
                                }
                            else:
                                self.fields[field]['value'] = getattr(self.instance, field)
            else:
                self.instance = self.content_type.mongoengine_class()

    def save(self):
        if self.instance:
            for field in self.fields.keys():
                if hasattr(self.instance, field):
                    if self.fields[field]['multiple']:
                        setattr(self.instance, field, [])
                        for value in self.fields[field]['value']:
                            if self.fields[field]['cross_reference_type'] and value and value['id']:
                                value = ObjectId(value['id'])

                            getattr(self.instance, field).append(value)
                    else:
                        value = self.fields[field]['value']
                        if self.fields[field]['cross_reference_type'] and value and value['id']:
                            value = ObjectId(value['id'])

                        setattr(self.instance, field, value)

            if not self.id:
                self.instance.save()

            self.id = str(self.instance.id)
            self.instance._label = self.get_label()
            self.instance._url = self.get_url()
            self.label = self.instance._label
            self.url = self.instance._url
            if not self.instance._label:
                self.instance._label = self.id
            self.instance.save()

            self.index()

            if settings.NEO4J:
                self.make_connections()

    def delete(self):
        if self.instance and self.instance.id:
            self.instance.delete()

    def get_label(self):
        if self.content_type and 'label' in self.content_type.templates:
            label_template = Template(self.content_type.templates['label']['html'])
            context = Context({self.content_type.name: self})
            return label_template.render(context)
        return ''

    def get_url(self):
        if self.content_type:
            if self.content_type.proxy_field and \
                    self.content_type.proxy_field in self.fields and \
                    self.fields[self.content_type.proxy_field]['multiple'] == False and \
                    self.fields[self.content_type.proxy_field]['cross_reference_type'] and \
                    self.fields[self.content_type.proxy_field]['value']:
                proxy_ct = self.fields[self.content_type.proxy_field]['cross_reference_type']
                proxy_id = self.fields[self.content_type.proxy_field]['value']['id']
                return "/corpus/{0}/type/{1}/view/{2}/".format(self.content_type.corpus.id, proxy_ct, proxy_id)
            else:
                return "/corpus/{0}/type/{1}/view/{2}/".format(
                    self.content_type.corpus.id,
                    self.content_type.name,
                    self.id
                )

    def index(self):
        if self.instance:
            index_obj = self.fields.copy()
            for field in index_obj.keys():
                new_value = ''

                if index_obj[field]['cross_reference_type']:
                    if index_obj[field]['multiple']:
                        new_value = " ".join(
                            ["{0} {1}".format(x['label'], x['url']) for x in index_obj[field]['value']])
                    elif index_obj[field]['value'] and 'label' in index_obj[field]['value']:
                        new_value = "{0} {1}".format(index_obj[field]['value']['label'],
                                                     index_obj[field]['value']['url'])
                else:
                    if index_obj[field]['multiple'] and index_obj[field]['type'] != 'number':
                        new_value = " ".join(index_obj[field]['value'])
                    else:
                        new_value = index_obj[field]['value']
                index_obj[field] = new_value
            index_obj['_label'] = self.label

            index_content(self.content_type.corpus.id, self.content_type.name, self.id, index_obj)

    def make_connections(self):
        if self.instance:
            nodes = {}
            for field in self.fields.keys():
                if self.fields[field]['cross_reference_type']:
                    cross_ref_type = self.fields[field]['cross_reference_type']
                    if cross_ref_type not in nodes:
                        nodes[cross_ref_type] = []

                    if self.fields[field]['multiple']:
                        nodes[cross_ref_type] = []
                        for cross_ref in self.fields[field]['value']:
                            nodes[cross_ref_type].append({
                                'oid': cross_ref['id'],
                                'uri': cross_ref['url'],
                                'label': cross_ref['label'],
                                'field': field
                            })
                    elif self.fields[field]['value'] and 'url' in self.fields[field]['value']:
                        nodes[cross_ref_type].append({
                            'oid': self.fields[field]['value']['id'],
                            'uri': self.fields[field]['value']['url'],
                            'label': self.fields[field]['value']['label'],
                            'field': field
                        })
            if nodes:
                with settings.NEO4J.session() as session:
                    for node_label in nodes.keys():
                        for node in nodes[node_label]:
                            cypher = '''
                                MERGE (a:{content_type} {{ oid: "{oid}", label: "{label}", uri: "{uri}" }})
                                MERGE (b:{cx_type} {{ oid: "{cx_oid}", label: "{cx_label}", uri: "{cx_uri}" }})
                                MERGE (a)-[rel:member_{field}]->(b)
                            '''.format(
                                content_type=self.content_type.name,
                                oid=self.id,
                                label=self.label,
                                uri=self.url,
                                field=node['field'],
                                cx_type=node_label,
                                cx_oid=node['oid'],
                                cx_label=node['label'],
                                cx_uri=node['uri']
                            )
                            session.run(cypher)

    def get_template(self, template):
        if self.content_type and template in self.content_type.templates:
            return self.content_type.templates[template]
        else:
            return ''


class ContentList(object):

    def __init__(self, corpus_id, content_type, page_size=50, current_page=1, all=False, search=None, query={}, sort={}, only=[]):
        self.query_set = []
        self.corpus_id = corpus_id
        self.count = 0
        self.all = all
        self.only = only
        self.page_size = page_size
        self.current_page = current_page
        self.content_type = None
        self.hits = []
        self.hit_counter = 0
        self.start_index = (current_page - 1) * page_size
        self.end_index = current_page * page_size

        if content_type and isinstance(content_type, str):
            try:
                self.content_type = ContentType.objects(corpus=corpus_id, name=content_type)[0]
            except:
                logging.error(traceback.format_exc())
                self.content_type = None
        elif content_type:
            self.content_type = content_type

        if self.content_type:
            if all:
                self.query_set = self.content_type.mongoengine_class.objects(**query)
                self.count = self.query_set.count()

                if self.count:
                    if only:
                        self.query_set = self.query_set.only(*only)
            else:
                index = "corpus-{0}-{1}".format(corpus_id, content_type.name.lower())
                should = []
                must = []
                if search:
                    should.append(SimpleQueryString(query=search))

                if query:
                    for search_field in query.keys():
                        must.append(Q("match", **{search_field: query[search_field]}))

                if should or must:
                    search_query = Q('bool', should=should, must=must)
                    search_cmd = Search(using=get_connection(), index=index).query(search_query).source(includes=['_id'])

                    if sort:
                        search_cmd = search_cmd.sort(*sort)

                    search_cmd = search_cmd[self.start_index:self.end_index]
                    print("Searching index {0}".format(index))
                    print(json.dumps(search_cmd.to_dict(), indent=4))
                    results = search_cmd.execute().to_dict()
                    print(json.dumps(results, indent=4))
                    self.hits = results['hits']['hits']
                    self.count = results['hits']['total']['value']

    def __iter__(self):
        if self.query_set:
            self.query_set.rewind()
        elif self.hits:
            self.hit_counter = 0
        return self

    def __next__(self):
        content = {}
        if self.query_set:
            content_obj = self.query_set.__next__()
            if content_obj:
                content = Content(self.corpus_id, self.content_type, str(content_obj.id), instance=content_obj, only=self.only)
            return content
        elif self.hits and self.hit_counter < self.count:
            content = Content(self.corpus_id, self.content_type, self.hits[self.hit_counter]['_id'], only=self.only)
            self.hit_counter += 1
            return content
        else:
            raise StopIteration

    def get_template(self, template):
        if self.content_type and template in self.content_type.templates:
            return self.content_type.templates[template]
        else:
            return ''


class Block(mongoengine.EmbeddedDocument):
    name = mongoengine.StringField()
    html_only = mongoengine.BooleanField()
    content_type = mongoengine.ReferenceField(ContentType)
    field_parameters = mongoengine.DictField()
    sort_by = mongoengine.StringField()
    limit = mongoengine.IntField()
    template = mongoengine.DictField()


class Page(mongoengine.Document):
    title = mongoengine.StringField(required=True, unique=True)
    url = mongoengine.StringField(required=True, unique=True)
    blocks = mongoengine.EmbeddedDocumentListField(Block)
    show_in_nav = mongoengine.BooleanField(default=True)
    nav_parent = mongoengine.StringField(default="")
    nav_location = mongoengine.IntField(default=0)
    template = mongoengine.DictField()
    xml_pageset = mongoengine.ReferenceField('XMLPageSet')

    meta = {
        'indexes': ['url']
    }

    def save(self, write_templates=False):
        super().save()
        if write_templates:
            template_dir = "{0}/{1}".format(settings.TEMPLATE_DIR, 'pages')
            pg_template_dir = "{0}{1}".format(template_dir, self.url)
            os.makedirs(pg_template_dir, exist_ok=True)
            pg_template_path = "{0}/page.html".format(pg_template_dir)
            with open(pg_template_path, 'w', encoding='utf-8') as page_out:
                page_out.write("{% extends base_template %}{% load static %}{% load extras %}{% block main %}\n")
                page_out.write(self.template['html'])
                page_out.write("\n{% endblock %}{% block js %}\n")
                page_out.write(self.template['js'])
                page_out.write("\n{% endblock %}")

                if 'css' in self.template:
                    page_out.write("\n{% block css %}")
                    page_out.write(self.template['css'])
                    page_out.write("\n{% endblock %}")

            for block in self.blocks:
                if block.html_only:
                    block_template_dir = "{0}/blocks".format(pg_template_dir)
                    os.makedirs(block_template_dir, exist_ok=True)
                    block_html_template_path = "{0}/{1}.html".format(block_template_dir, block.name)
                    block_js_template_path = "{0}/{1}.js".format(block_template_dir, block.name)
                    with open(block_html_template_path, 'w', encoding='utf-8') as block_out:
                        block_out.write(block.template['html'])
                    with open(block_js_template_path, 'w', encoding='utf-8') as block_out:
                        block_out.write(block.template['js'])

    def delete(self):
        template_dir = "{0}/{1}".format(settings.TEMPLATE_DIR, 'pages')
        pg_template_dir = "{0}{1}".format(template_dir, self.url)
        if os.path.exists(pg_template_dir):
            shutil.rmtree(pg_template_dir)
        super().delete()


class XMLTransform(mongoengine.EmbeddedDocument):
    name = mongoengine.StringField(required=True, unique=True)
    kind = mongoengine.StringField(required=True)
    path = mongoengine.StringField()
    result_filename_pattern = mongoengine.StringField(default='*.html')
    ran = mongoengine.BooleanField(default=False)
    output = mongoengine.StringField(required=False)


class XMLPageSet(mongoengine.Document):
    name = mongoengine.StringField(required=True, unique=True)
    url_root = mongoengine.StringField(required=True, unique=True)
    source_path = mongoengine.StringField(required=True)
    destination_path = mongoengine.StringField(required=True)
    transforms = mongoengine.EmbeddedDocumentListField(XMLTransform)
    result_pages = mongoengine.ListField(mongoengine.ReferenceField(Page))
    css_path = mongoengine.StringField(required=False)
    js_path = mongoengine.StringField(required=False)

    def save(self, run_transforms=False):
        super().save()
        if run_transforms:
            run_xml_transforms(self.id)


def load_content_types_from_schema(corpus, schema):
    templates_changed = False
    indexes_to_build = []

    for content_type in schema:
        current_types = ContentType.objects
        content_type_names = [ct.name for ct in current_types]

        if 'id' not in content_type and content_type['name'] in content_type_names:
            print("{0} already in corpus {1}".format(content_type['name'], corpus.id))
            continue

        if 'id' not in content_type or not content_type['id']:
            new_content_type = ContentType()
            new_content_type.corpus = corpus
            new_content_type.name = content_type['name']
            new_content_type.plural_name = content_type['plural_name']
            new_content_type.show_in_nav = content_type['show_in_nav']
            new_content_type.proxy_field = content_type['proxy_field']
            for template_type in content_type['templates'].keys():
                new_content_type.templates[template_type] = content_type['templates'][template_type]

            self_referencing_fields = {}
            field_count = 0

            for field in content_type['fields']:
                self_referenced = False

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

                if new_field.type == 'cross_reference':
                    if new_content_type.name == field['cross_reference_type']:
                        self_referencing_fields[field_count] = new_field
                        self_referenced = True
                    else:
                        for current_type in current_types:
                            if current_type.name == field['cross_reference_type']:
                                new_field.cross_reference_type = current_type

                if not self_referenced:
                    new_content_type.fields.append(new_field)
                field_count += 1

            new_content_type.save()
            if self_referencing_fields:
                for field_index in self_referencing_fields.keys():
                    self_referencing_fields[field_index].cross_reference_type = new_content_type
                    new_content_type.fields.insert(field_index, self_referencing_fields[field_index])
                new_content_type.save()
            templates_changed = True
            indexes_to_build.append(new_content_type.name)

        else:
            ct = None

            if 'id' in content_type:
                try:
                    ct = ContentType.objects(corpus=corpus, id=content_type['id'])[0]
                except:
                    ct = None
            else:
                try:
                    ct = ContentType.objects(corpus=corpus, name=content_type['name'])[0]
                except:
                    ct = None

            if ct:
                ct.plural_name = content_type['plural_name']
                ct.show_in_nav = content_type['show_in_nav']
                ct.proxy_field = content_type['proxy_field']
                for template_type in content_type['templates'].keys():
                    if ct.templates[template_type] != content_type['templates'][template_type]:
                        ct.templates[template_type] = content_type['templates'][template_type]
                        templates_changed = True

                old_fields = {}
                for x in range(0, len(ct.fields)):
                    old_fields[ct.fields[x].name] = x

                for x in range(0, len(content_type['fields'])):
                    if content_type['fields'][x]['name'] not in old_fields:
                        new_field = Field()
                        new_field.name = content_type['fields'][x]['name']
                        new_field.label = content_type['fields'][x]['label']
                        new_field.in_lists = content_type['fields'][x]['in_lists']
                        new_field.indexed = content_type['fields'][x]['indexed']
                        new_field.indexed_with = content_type['fields'][x]['indexed_with']
                        new_field.unique = content_type['fields'][x]['unique']
                        new_field.unique_with = content_type['fields'][x]['unique_with']
                        new_field.multiple = content_type['fields'][x]['multiple']
                        new_field.type = content_type['fields'][x]['type']

                        if new_field.type == 'cross_reference':
                            for current_type in current_types:
                                if current_type.name == content_type['fields'][x]['cross_reference_type']:
                                    new_field.cross_reference_type = current_type
                        ct.fields.append(new_field)
                        indexes_to_build.append(ct.name)

                    else:
                        field_index = old_fields[content_type['fields'][x]['name']]
                        ct.fields[field_index].label = content_type['fields'][x]['label']

                        if ct.fields[field_index].in_lists != content_type['fields'][x]['in_lists']:
                            ct.fields[field_index].in_lists = content_type['fields'][x]['in_lists']
                            indexes_to_build.append(ct.name)

                        ct.fields[field_index].indexed = content_type['fields'][x]['indexed']
                        ct.fields[field_index].indexed_with = content_type['fields'][x]['indexed_with']
                        ct.fields[field_index].unique = content_type['fields'][x]['unique']
                        ct.fields[field_index].unique_with = content_type['fields'][x]['unique_with']
                        ct.fields[field_index].multiple = content_type['fields'][x]['multiple']
                        ct.fields[field_index].type = content_type['fields'][x]['type']
                        if ct.fields[field_index].type == 'cross_reference':
                            for current_type in current_types:
                                if current_type.name == content_type['fields'][x]['cross_reference_type']:
                                    ct.fields[field_index].cross_reference_type = current_type
                        else:
                            ct.fields[field_index].cross_reference_type = None
                ct.save()

    if templates_changed:
        print("writing templates...")
        current_types = ContentType.objects
        template_dir = "{0}/templates/types".format(corpus.path)
        os.makedirs(template_dir, exist_ok=True)
        for ct in current_types:
            ct_template_dir = "{0}/{1}".format(template_dir, ct.name)
            os.makedirs(ct_template_dir, exist_ok=True)
            for template_type in ct.templates.keys():
                if template_type != 'field_templates':
                    for template_format in ct.templates[template_type].keys():
                        template_path = "{0}/{1}.{2}".format(
                            ct_template_dir,
                            template_type,
                            template_format
                        )
                        print("writing {0}".format(ct_template_dir))
                        with open(template_path, 'w', encoding='utf-8') as template_out:
                            template_out.write(ct.templates[template_type][template_format])
    
    if indexes_to_build:
        build_indexes(corpus.id, indexes_to_build)
        # Sleep a little bit to make sure any new indexes are built
        sleep(4)
