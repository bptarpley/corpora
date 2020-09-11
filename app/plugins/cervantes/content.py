import mongoengine
from corpus import Content


REGISTRY = [
    {
        "name": "EditionCategory",
        "plural_name": "Edition Categories",
        "fields": [
            {
                "name": "sequence",
                "label": "Sequence",
                "in_lists": False,
                "type": "number",
            },
            {
                "name": "name",
                "label": "Name",
                "in_lists": True,
                "type": "text",
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "<span hidden>{{ EditionCategory.sequence }}</span>{{ EditionCategory.name }}",
                "mime_type": "text/html"
            }
        }
    },
    {
        "name": "DQLocation",
        "plural_name": "DQ Locations",
        "inherited_from_module": "plugins.cervantes.content",
        "inherited_from_class": "DQLocation",
        "fields": [
            {
                "name": "part",
                "label": "Part",
                "in_lists": True,
                "type": "text",
                "inherited": True
            },
            {
                "name": "chapter",
                "label": "Chapter",
                "in_lists": True,
                "type": "text",
                "inherited": True
            },
            {
                "name": "section",
                "label": "Section",
                "in_lists": True,
                "type": "text",
                "inherited": True
            },
            {
                "name": "description",
                "label": "Description",
                "in_lists": True,
                "type": "text",
                "inherited": True
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "base_mongo_indexes": [
            {
                'fields': ['part', 'chapter', 'section'],
                'unique': True,
                'sparse': True
            }
        ],
        "templates": {
            "Label": {
                "template": "{{ DQLocation.part }}-{{ DQLocation.chapter }}-{{ DQLocation.section }}",
                "mime_type": "text/html"
            }
        },
    },
    {
        "name": "Illustration",
        "plural_name": "Illustrations",
        "fields": [
            {
                "name": "image",
                "label": "Image",
                "in_lists": True,
                "type": "text",
            },
            {
                "name": "edition",
                "label": "Edition",
                "in_lists": True,
                "type": "cross_reference",
                "cross_reference_type": "Document",
            },
            {
                "name": "illustration_number",
                "label": "Illustration Number",
                "in_lists": True,
                "type": "number",
            },
            {
                "name": "illustrator",
                "label": "Illustrator",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "engraver",
                "label": "Engraver",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "lithographer",
                "label": "Lithographer",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "title_caption",
                "label": "Title Caption",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "title_supplied",
                "label": "Title Supplied",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "location",
                "label": "Location",
                "in_lists": True,
                "type": "cross_reference",
                "cross_reference_type": "DQLocation",
            },
            {
                "name": "illustration_type",
                "label": "Type",
                "in_lists": True,
                "type": "text",
            },
            {
                "name": "illustration_technique",
                "label": "Technique",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "color",
                "label": "Color",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "page_number",
                "label": "Page Number",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "image_dimensions",
                "label": "Image Dimensions",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "page_dimensions",
                "label": "Page Dimensions",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "commentary",
                "label": "Commentary",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "notes",
                "label": "Notes",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "def_frozen",
                "label": "Frozen?",
                "in_lists": False,
                "type": "text",
            },
            {
                "name": "user_id",
                "label": "User ID",
                "in_lists": False,
                "type": "text",
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ Illustration.image }}",
                "mime_type": "text/html"
            }
        }
    }
]


class DQLocation(Content):

    part = mongoengine.StringField()
    chapter = mongoengine.StringField()
    section = mongoengine.StringField()
    description = mongoengine.StringField()

    def _make_uri(self):
        new_uri = "/corpus/{0}/DQLocation/DonQuixote".format(self.corpus_id)

        if self.part and self.chapter and self.section:
            new_uri = "/corpus/{0}/DQLocation/{1}/{2}/{3}".format(
                self.corpus_id,
                self.part,
                self.chapter,
                self.section
            )
        elif self.part and self.chapter:
            new_uri = "/corpus/{0}/DQLocation/{1}/{2}".format(
                self.corpus_id,
                self.part,
                self.chapter
            )
        elif self.part:
            new_uri = "/corpus/{0}/DQLocation/{1}".format(
                self.corpus_id,
                self.part
            )

        if new_uri != self.uri:
            self.uri = new_uri
            return True
        return False

    meta = {
        'abstract': True
    }