import os
import json
import importlib
import mongoengine
from copy import deepcopy
from django.conf import settings
from django.template import Context
from .content import Content
from .field import FieldRenderer


MIME_TYPES = ('text/html', 'text/css', 'text/xml', 'text/turtle', 'application/json')
CONTENT_TYPE_GROUP_MEMBER_DISPLAY_SETTINGS = ('full', 'half', 'minimized')


class ContentType(mongoengine.EmbeddedDocument):
    """
    Defines a type of content within a Corpus, analogous to a table schema in a database.

    ContentTypes define the structure and behavior of content instances, including their
    fields, display templates, and indexing configuration. They support inheritance from
    Python classes for custom behavior.

    Attributes:
        name (str): Singular name of the content type (e.g., 'Document').
        plural_name (str): Plural form for UI display (e.g., 'Documents').
        fields (list[Field]): List of Field objects defining the structure.
        show_in_nav (bool): Whether to show in navigation menus. Defaults to True.
        autocomplete_labels (bool): Enable search suggestions on labels. Defaults to False.
        proxy_field (str): Field name whose value determines the URI structure.
        templates (dict[str, ContentTemplate]): Display templates by name.
        view_widget_url (str): URL for custom view widget.
        edit_widget_url (str): URL for custom edit widget.
        inherited_from_module (str): Python module for base class.
        inherited_from_class (str): Python class name to inherit from.
        base_mongo_indexes (str): JSON string of additional MongoDB indexes.
        has_file_field (bool): Whether any field is of type 'file' or 'repo'.
        invalid_field_names (list[str]): Reserved field names that cannot be used.

    Examples:
        >>> article_type = ContentType(
        ...     name='Article',
        ...     plural_name='Articles',
        ...     fields=[
        ...         Field(name='title', type='text', label='Title'),
        ...         Field(name='author', type='cross_reference',
        ...               cross_reference_type='Person', label='Author'),
        ...         Field(name='content', type='large_text', label='Content')
        ...     ]
        ... )
    """

    name = mongoengine.StringField(required=True)
    plural_name = mongoengine.StringField(required=True)
    fields = mongoengine.EmbeddedDocumentListField('Field')
    show_in_nav = mongoengine.BooleanField(default=True)
    autocomplete_labels = mongoengine.BooleanField(default=False)
    proxy_field = mongoengine.StringField()
    templates = mongoengine.MapField(mongoengine.EmbeddedDocumentField('ContentTemplate'))
    view_widget_url = mongoengine.StringField()
    edit_widget_url = mongoengine.StringField()
    inherited_from_module = mongoengine.StringField()
    inherited_from_class = mongoengine.StringField()
    base_mongo_indexes = mongoengine.StringField()
    has_file_field = mongoengine.BooleanField(default=False)
    invalid_field_names = mongoengine.ListField(mongoengine.StringField())

    def get_field(self, field_name):
        for index in range(0, len(self.fields)):
            if self.fields[index].name == field_name:
                return self.fields[index]
        return None

    def get_mongoengine_class(self, corpus):
        """
        Dynamically generate a MongoEngine Document class for this content type.

        Creates a class that inherits from Content (or a custom base class) with
        all fields properly configured as MongoEngine fields. Handles indexes,
        unique constraints, and signal connections.

        Args:
            corpus (Corpus): The parent corpus instance.

        Returns:
            type: A MongoEngine Document class configured for this content type.
        """

        class_dict = {
            '_ct': self,
            '_corpus': corpus
        }

        indexes = []
        if self.base_mongo_indexes:
            indexes = json.loads(self.base_mongo_indexes)

        for field in self.fields:
            if not field.inherited:
                if field.type == 'cross_reference':
                    if field.cross_reference_type == self.name:
                        xref_class = self.name
                    else:
                        xref_class = corpus.content_types[field.cross_reference_type].get_mongoengine_class(corpus)

                    if field.unique and not field.unique_with:
                        class_dict[field.name] = mongoengine.ReferenceField(xref_class, unique=True)
                    else:
                        class_dict[field.name] = mongoengine.ReferenceField(xref_class)
                else:
                    class_dict[field.name] = field.get_mongoengine_field_class()

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
            'collection': "corpus_{0}_{1}".format(corpus.id, self.name)
        }

        ct_class = Content

        if self.inherited_from_class:
            ct_module = importlib.import_module(self.inherited_from_module)
            ct_class = getattr(ct_module, self.inherited_from_class)

        ct_class = type(
            self.name,
            (ct_class,),
            class_dict
        )

        mongoengine.signals.pre_save.connect(ct_class._pre_save, sender=ct_class)
        mongoengine.signals.pre_delete.connect(ct_class._pre_delete, sender=ct_class)

        return ct_class

    def _has_intensity_field(self):
        for field in self.fields:
            if field.has_intensity:
                return True
        return False

    def get_field_dict(self, include_embedded=False):
        fd = {}
        for field in self.fields:
            if field.type != 'embedded' or include_embedded:
                fd[field.name] = field
        return fd

    def set_field_values_from_content(self, content):
        for field_index in range(0, len(self.fields)):
            f = self.fields[field_index]
            self.fields[field_index].value = getattr(content, f.name, None)
            self.fields[field_index].parent_uri = content.uri

    def get_field_types(self):
        field_types = []
        for field in self.fields:
            field_types.append(field.type)
        return list(set(field_types))

    def get_render_requirements(self, mode):
        # build scripts/stylesheets to include
        inclusions = {}
        javascript_functions = ""
        css_styles = ""
        req_file = f"{settings.BASE_DIR}/corpus/field_templates/requirements.json"

        if self.inherited_from_module and self.inherited_from_class:
            module = importlib.import_module(self.inherited_from_module)
            class_obj = getattr(module, self.inherited_from_class)
            if hasattr(class_obj, 'get_render_requirements'):
                inclusions, javascript_functions, css_styles = class_obj.get_render_requirements(mode)

        if os.path.exists(req_file):
            with open(req_file, 'r') as reqs_in:
                all_reqs = json.load(reqs_in)
                field_types = self.get_field_types()
                for field_type in field_types:
                    # gather includes
                    if field_type in all_reqs:
                        if mode in all_reqs[field_type]:
                            for req_lang, req_paths in all_reqs[field_type][mode].items():
                                for req_path in req_paths:
                                    if req_lang not in inclusions:
                                        inclusions[req_lang] = []
                                    if req_path not in inclusions[req_lang]:
                                        inclusions[req_lang].append(req_path)

                    # gather javascript functions
                    js_renderer = FieldRenderer(field_type, mode, 'js')
                    javascript_functions += '\n' + js_renderer.render(Context({'field': None}))

                    # gather css styles
                    css_renderer = FieldRenderer(field_type, mode, 'css')
                    css_styles += '\n' + css_renderer.render(Context({'field': None}))

        return inclusions, javascript_functions, css_styles

    def render_embedded_field(self, field_name):
        if self.inherited_from_module and self.inherited_from_class:
            module = importlib.import_module(self.inherited_from_module)
            class_obj = getattr(module, self.inherited_from_class)
            field = self.get_field(field_name)
            if hasattr(class_obj, 'render_embedded_field') and field.value:
                return class_obj.render_embedded_field(field_name, field.value)
        return ''

    def to_dict(self):
        ct_dict = {
            'name': self.name,
            'plural_name': self.plural_name,
            'fields': [field.to_dict() for field in self.fields],
            'show_in_nav': self.show_in_nav,
            'autocomplete_labels': self.autocomplete_labels,
            'proxy_field': self.proxy_field,
            'templates': {},
            'view_widget_url': self.view_widget_url,
            'edit_widget_url': self.edit_widget_url,
            'inherited_from_module': self.inherited_from_module,
            'inherited_from_class': self.inherited_from_class,
            'base_mongo_indexes': self.base_mongo_indexes,
            'has_file_field': self.has_file_field,
            'invalid_field_names': deepcopy(self.invalid_field_names),
        }

        for template_name in self.templates:
            ct_dict['templates'][template_name] = self.templates[template_name].to_dict()

        return ct_dict


class ContentTemplate(mongoengine.EmbeddedDocument):
    template = mongoengine.StringField()
    mime_type = mongoengine.StringField(choices=MIME_TYPES)

    def to_dict(self):
        return {
            'template': self.template,
            'mime_type': self.mime_type
        }


class ContentTypeGroupMember(mongoengine.EmbeddedDocument):
    name = mongoengine.StringField(required=True)
    display_preference = mongoengine.StringField(default='full', choices=CONTENT_TYPE_GROUP_MEMBER_DISPLAY_SETTINGS)

    def from_dict(self, member_dict):
        self.name = member_dict['name']
        self.display_preference = member_dict['display_preference']

    def to_dict(self):
        return {
            'name': self.name,
            'display_preference': self.display_preference,
        }


class ContentTypeGroup(mongoengine.EmbeddedDocument):
    title = mongoengine.StringField()
    description = mongoengine.StringField()
    members = mongoengine.ListField(mongoengine.EmbeddedDocumentField(ContentTypeGroupMember))

    @property
    def content_types(self):
        if not hasattr(self, '_content_types'):
            self._content_types = [m.name for m in self.members]
        return self._content_types

    def from_dict(self, group_dict):
        self.title = group_dict['title']
        self.description = group_dict['description']
        for member_info in group_dict['members']:
            member = ContentTypeGroupMember()
            member.from_dict(member_info)
            self.members.append(member)

    def to_dict(self):
        return {
            'title': self.title,
            'description': self.description,
            'members': [m.to_dict() for m in self.members],
        }