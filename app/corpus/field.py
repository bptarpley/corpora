import os
import mongoengine
from datetime import datetime
from copy import deepcopy
from django.conf import settings
from django.template import Template
from elasticsearch_dsl import token_filter, analyzer
from .language_settings import REGISTRY as lang_settings
from .field_types.file import File
from .field_types.gitrepo import GitRepo
from .field_types.timespan import Timespan


FIELD_TYPES = ('text', 'large_text', 'keyword', 'html', 'choice', 'number', 'decimal', 'boolean', 'date', 'timespan', 'file', 'repo', 'link', 'iiif-image', 'geo_point', 'cross_reference', 'embedded')
FIELD_LANGUAGES = {
    'arabic': "Arabic", 'armenian': "Armenian", 'basque': "Basque", 'bengali': "Bengali", 'brazilian': "Brazilian",
    'bulgarian': "Bulgarian", 'catalan': "Catalan", 'cjk': "CJK", 'czech': "Czech", 'danish': "Danish", 'dutch': "Dutch",
    'english': "English", 'estonian': "Estonian", 'finnish': "Finnish", 'french': "French", 'galician': "Galician",
    'german': "German", 'greek': "Greek", 'hindi': "Hindi", 'hungarian': "Hungarian", 'indonesian': "Indonesian",
    'irish': "Irish", 'italian': "Italian", 'latvian': "Latvian", 'lithuanian': "Lithuanian", 'norwegian': "Norwegian",
    'persian': "Persian", 'portuguese': "Portuguese", 'romanian': "Romanian", 'russian': "Russian", 'sorani': "Sorani",
    'spanish': "Spanish", 'swedish': "Swedish", 'turkish': "Turkish", 'thai': "Thai"
}


class Field(mongoengine.EmbeddedDocument):
    """
    Defines a single field within a ContentType, analogous to a column in a database table.

    Fields support various data types including text, numbers, dates, files, and cross-references
    to other content. They can be configured for indexing, uniqueness constraints, and
    multi-value storage.

    Attributes:
        name (str): The field identifier used in code. Must be unique within a ContentType.
        label (str): Human-readable label for UI display.
        indexed (bool): Whether this field should be indexed for searching. Defaults to False.
        unique (bool): Whether values must be unique across all content. Defaults to False.
        multiple (bool): Whether this field can store multiple values. Defaults to False.
        in_lists (bool): Whether to include in list views and search results. Defaults to True.
        type (str): The data type. Must be one of FIELD_TYPES.
        choices (list): For 'choice' type fields, the allowed values.
        cross_reference_type (str): For 'cross_reference' fields, the target ContentType name.
        has_intensity (bool): For cross-references, whether to support weighted relationships.
        language (str): For text fields, the language for analysis. Defaults to 'english'.
        autocomplete (bool): Whether to enable search suggestions. Defaults to False.
        synonym_file (str): Reference to a synonym configuration for search enhancement.
        indexed_with (list): Other field names to create compound indexes with.
        unique_with (list): Other field names to create compound unique constraints with.
        stats (dict): Statistical information about field usage.
        inherited (bool): Whether this field is inherited from a base class.

    Examples:
        >>> # Simple text field
        >>> title_field = Field(
        ...     name='title',
        ...     label='Title',
        ...     type='text',
        ...     indexed=True
        ... )

        >>> # Cross-reference field with multiple values
        >>> authors_field = Field(
        ...     name='authors',
        ...     label='Authors',
        ...     type='cross_reference',
        ...     cross_reference_type='Person',
        ...     multiple=True,
        ...     has_intensity=True
        ... )
    """

    name = mongoengine.StringField(required=True)
    label = mongoengine.StringField()
    indexed = mongoengine.BooleanField(default=False)
    unique = mongoengine.BooleanField(default=False)
    multiple = mongoengine.BooleanField(default=False)
    in_lists = mongoengine.BooleanField(default=True)
    type = mongoengine.StringField(choices=FIELD_TYPES)
    choices = mongoengine.ListField()
    cross_reference_type = mongoengine.StringField()
    has_intensity = mongoengine.BooleanField(default=False)
    language = mongoengine.StringField(choices=list(FIELD_LANGUAGES.keys()), sparse=True)
    autocomplete = mongoengine.BooleanField(default=False)
    synonym_file = mongoengine.StringField(choices=list(settings.ES_SYNONYM_OPTIONS.keys()))
    indexed_with = mongoengine.ListField()
    unique_with = mongoengine.ListField()
    stats = mongoengine.DictField()
    inherited = mongoengine.BooleanField(default=False)

    def get_dict_value(self, value, parent_uri, field_intensities={}):
        """
        Convert field value to dictionary representation for serialization.

        Handles special conversions for dates, cross-references, files, and other complex types.
        For multiple-value fields, returns a list of converted values.

        Args:
            value: The field value to convert.
            parent_uri (str): URI of the parent content object.
            field_intensities (dict): Intensity values for weighted cross-references.

        Returns:
            Converted value suitable for JSON serialization.
        """

        dict_value = None

        if self.multiple:
            if self.type == 'embedded' and hasattr(value, 'keys'):
                dict_value = {}
                for key in value.keys():
                    dict_value[key] = self.to_primitive(value[key], parent_uri)

            else:
                dict_value = []
                for val in value:
                    dict_value.append(self.to_primitive(val, parent_uri, field_intensities))

        else:
            dict_value = self.to_primitive(value, parent_uri, field_intensities)

        return dict_value

    def to_primitive(self, value, parent_uri, field_intensities={}):
        """
        Convert a single value to its primitive (and thus serializable) representation.

        This is a helper function used chiefly by the get_dict_value method.

        Args:
            value: The value to convert.
            parent_uri (str): URI of the parent content object.
            field_intensities (dict): Intensity values for weighted cross-references.

        Returns:
            Primitive representation of the value.
        """

        if value:
            if self.type == 'date':
                dt = datetime.combine(value, datetime.min.time())
                return dt.isoformat()
            elif self.type == 'cross_reference':
                value_dict = value.to_dict(ref_only=True)
                if self.has_intensity and 'id' in value_dict:
                    value_dict['intensity'] = field_intensities.get(
                        '{field_name}-{val_id}'.format(field_name=self.name, val_id=value_dict['id']),
                        1
                    )
                return value_dict
            elif self.type == 'repo':
                return value.remote_url
            elif self.type in ['embedded', 'file', 'timespan'] and hasattr(value, 'to_dict'):
                return value.to_dict(parent_uri)
            elif self.type == 'geo_point':
                return value['coordinates']
        return value

    def get_mongoengine_field_class(self):
        """
        Generate the appropriate MongoEngine field class for this field type.

        Used by the get_mongoengine_class method of the Corpus class.

        Returns:
            MongoEngine field class instance configured with appropriate constraints.
        """

        if self.type == 'number':
            if self.unique and not self.unique_with:
                return mongoengine.IntField(unique=True, sparse=True)
            else:
                return mongoengine.IntField()
        elif self.type == 'decimal':
            if self.unique and not self.unique_with:
                return mongoengine.FloatField(unique=True, sparse=True)
            else:
                return mongoengine.FloatField()
        elif self.type == 'boolean':
            if self.unique and not self.unique_with:
                return mongoengine.BooleanField(unique=True, sparse=True)
            else:
                return mongoengine.BooleanField()
        elif self.type == 'date':
            if self.unique and not self.unique_with:
                return mongoengine.DateField(unique=True, sparse=True)
            else:
                return mongoengine.DateField()
        elif self.type == 'file':
            return mongoengine.EmbeddedDocumentField(File)
        elif self.type == 'repo':
            return mongoengine.EmbeddedDocumentField(GitRepo)
        elif self.type == 'timespan':
            return mongoengine.EmbeddedDocumentField(Timespan)
        elif self.type == 'geo_point':
            return mongoengine.PointField()
        elif self.type != 'cross_reference':
            if self.unique and not self.unique_with:
                return mongoengine.StringField(unique=True, sparse=True)
            else:
                return mongoengine.StringField()

    def get_elasticsearch_analyzer(self):
        """
        Create an Elasticsearch analyzer for text fields.

        Configures language-specific analyzers with appropriate filters, tokenizers,
        and synonym support based on field configuration.

        Returns:
            elasticsearch_dsl.analyzer instance or None for non-text fields.
        """

        analyzer_filters = ['lowercase', 'classic', 'stop']
        tokenizer = "standard"
        if self.language in lang_settings:
            analyzer_filters = deepcopy(lang_settings[self.language]['filter'])
            tokenizer = lang_settings[self.language]['tokenizer']

        if self.synonym_file and self.synonym_file in settings.ES_SYNONYM_OPTIONS:
            analyzer_filters.insert(1, token_filter(
                '{0}_synonym_filter'.format(self.synonym_file),
                'synonym',
                lenient=True,
                synonyms_path=settings.ES_SYNONYM_OPTIONS[self.synonym_file]['file']
            ))

        if self.type in ['text', 'large_text']:
            return analyzer(
                '{0}_analyzer'.format(self.name).lower(),
                type=self.language,
                tokenizer=tokenizer,
                filter=analyzer_filters,
            )

        elif self.type == 'html':
            return analyzer(
                '{0}_analyzer'.format(self.name).lower(),
                type=self.language,
                tokenizer=tokenizer,
                filter=analyzer_filters,
                char_filter=['html_strip']
            )

        return None

    @property
    def view_html(self):
        return FieldRenderer(self.type, 'view', 'html')

    @property
    def edit_html(self):
        return FieldRenderer(self.type, 'edit', 'html')

    def to_dict(self):
        """
        Export field definition as a dictionary.

        Returns:
            dict: Complete field definition including all configuration.
        """

        return {
            'name': self.name,
            'label': self.label,
            'indexed': self.indexed,
            'unique': self.unique,
            'multiple': self.multiple,
            'in_lists': self.in_lists,
            'type': self.type,
            'choices': [choice for choice in self.choices],
            'cross_reference_type': self.cross_reference_type,
            'has_intensity': self.has_intensity,
            'language': self.language,
            'autocomplete': self.autocomplete,
            'synonym_file': self.synonym_file,
            'indexed_with': [index for index in self.indexed_with],
            'unique_with': [unq for unq in self.unique_with],
            'stats': deepcopy(self.stats),
            'inherited': self.inherited
        }


class FieldRenderer(object):
    field_type = None
    mode = None
    language = None

    def __init__(self, field_type, mode, language):
        self.field_type = field_type
        self.mode = mode
        self.language = language

    def render(self, context):
        field_template_path = f"{settings.BASE_DIR}/corpus/field_templates/{self.field_type}/{self.mode}.{self.language}"
        default_template_path = f"{settings.BASE_DIR}/corpus/field_templates/default_{self.mode}.{self.language}"
        field_template = ""
        if os.path.exists(field_template_path):
            field_template = open(field_template_path, 'r').read()
        elif os.path.exists(default_template_path):
            field_template = open(default_template_path, 'r').read()

        if field_template:
            django_template = Template(field_template)
            return django_template.render(context)
        return ""