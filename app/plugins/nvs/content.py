REGISTRY = [
    {
        "name": "ContentBlock",
        "plural_name": "Content Blocks",
        "fields": [
            {
                "name": "handle",
                "label": "Handle",
                "indexed": False,
                "unique": True,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "html",
                "label": "HTML",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "html",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ ContentBlock.handle }}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ]
    },
    {
        "name": "DocumentCollection",
        "plural_name": "Document Collections",
        "fields": [
            {
                "name": "siglum",
                "label": "Siglum",
                "indexed": False,
                "unique": True,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "siglum_label",
                "label": "Siglum Label",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "referenced_documents",
                "label": "Referenced Documents",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Document",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ DocumentCollection.siglum_label }}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ]
    },
    {
        "name": "WitnessLocation",
        "plural_name": "Witness Locations",
        "fields": [
            {
                "name": "witness",
                "label": "Witness",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Document",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "starting_page",
                "label": "Starting Page",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "starting_line",
                "label": "Starting Line",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "ending_page",
                "label": "Ending Page",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "ending_line",
                "label": "Ending Line",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ WitnessLocation.witness.siglum_label }} {{ WitnessLocation.starting_page }}{% if WitnessLocation.starting_line %}:{{ WitnessLocation.starting_line }}{% endif %}{% if WitnessLocation.ending_page %} - {{ WitnessLocation.ending_page }}{% endif %}{% if WitnessLocation.ending_line %}:{{ WitnessLocation.ending_line }}{% endif %}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ]
    },
    {
        "name": "PlayLine",
        "plural_name": "Play Lines",
        "fields": [
            {
                "name": "xml_id",
                "label": "XML ID",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "line_label",
                "label": "Line Label",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "line_number",
                "label": "Line Number",
                "indexed": False,
                "unique": True,
                "multiple": False,
                "in_lists": True,
                "type": "number",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "act",
                "label": "Act",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "scene",
                "label": "Scene",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "witness_locations",
                "label": "Witness Locations",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "WitnessLocation",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "words",
                "label": "Words",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "rendered_html",
                "label": "Rendered HTML",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "html",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "witness_meter",
                "label": "Witness Meter",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "base_mongo_indexes": [
            'line_number'
        ],
        "templates": {
            "Label": {
                "template": "[{{ PlayLine.line_number }}] {{ PlayLine.words|join:' ' }}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ]
    },
    {
        "name": "PlayTag",
        "plural_name": "Play Tags",
        "fields": [
            {
                "name": "name",
                "label": "Name",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "classes",
                "label": "Classes",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "order",
                "label": "Order",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "number",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "[{{ PlayTag.name }} class=\"{{ PlayTag.classes }}\"]",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ]
    },
    {
        "name": "TextualVariant",
        "plural_name": "Textual Variants",
        "fields": [
            {
                "name": "lemma",
                "label": "Lemma",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "transform_type",
                "label": "Transform Type",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "transform",
                "label": "Transform",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "description",
                "label": "Description",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "variant",
                "label": "Variant",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "witness_formula",
                "label": "Witness Formula",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "html",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "witnesses",
                "label": "Witnesses",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Document",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "witness_meter",
                "label": "Witness Meter",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "html",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "has_bug",
                "label": "Has Bug?",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "number",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{% if TextualVariant.has_bug %}<span style='background-color: red; color: white;'>{% endif %}{% if TextualVariant.lemma %}<b>Lemma:</b> {{ TextualVariant.lemma }} {% endif %}{% if TextualVariant.transform_type %}<b>Transform Type:</b> {{ TextualVariant.transform_type }} {% endif %}{% if TextualVariant.transform %}<b>Transform:</b> {{ TextualVariant.transform }} {% endif %}{% if TextualVariant.description %}<b>Description:</b> {{ TextualVariant.description }} {% endif %}{% if TextualVariant.variant %}<b>Result:</b> {{ TextualVariant.variant }}{% endif %} ({% for witness in TextualVariant.witnesses %}{{ witness.label|safe }}{% if not forloop.last %}, {% endif %}{% endfor %}){% if TextualVariant.has_bug %}</span>{% endif %}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ]
    },
    {
        "name": "TextualNote",
        "plural_name": "Textual Notes",
        "fields": [
            {
                "name": "xml_id",
                "label": "XML ID",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "lines",
                "label": "Lines",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "PlayLine",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "variants",
                "label": "Variants",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "TextualVariant",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "witness_meter",
                "label": "Witness Meter",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "html",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "TextualNote {{ TextualNote.id }}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ]
    },
    {
        "name": "Commentary",
        "plural_name": "Commentaries",
        "fields": [
            {
                "name": "xml_id",
                "label": "XML ID",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "lines",
                "label": "Lines",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "PlayLine",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "line_label",
                "label": "Line Label",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "subject_matter",
                "label": "Subject Matter",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "contents",
                "label": "Contents",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "html",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "Commentary {{ Commentary.id }}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri"
        ]
    }
]
