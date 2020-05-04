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
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "base_mongo_indexes": [
            'line_number'
        ],
        "templates": {
            "Label": {
                "template": "[{{ PlayLine.line_number }}] {{ PlayLine.words|join:" " }}",
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
        "name": "LineLocation",
        "plural_name": "Line Locations",
        "fields": [
            {
                "name": "starting_line_number",
                "label": "Starting Line Number",
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
            {
                "name": "starting_word_index",
                "label": "Starting Word Index",
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
            {
                "name": "ending_line_number",
                "label": "Ending Line Number",
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
            {
                "name": "ending_word_index",
                "label": "Ending Word Index",
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
        "base_mongo_indexes": [
            {
                "fields": [
                    "starting_line_number",
                    "-ending_line_number",
                    "starting_word_index",
                    "-ending_word_index"
                ],
                "unique": False
            }
        ],
        "templates": {
            "Label": {
                "template": "{{ LineLocation.starting_line_number }}{% if LineLocation.starting_word_index %}:{{ LineLocation.starting_word_index }}{% endif %}{% if LineLocation.ending_line_number %} - {{ LineLocation.ending_line_number }}{% if LineLocation.ending_word_index %}:{{ LineLocation.ending_word_index }}{% endif %}{% endif %}",
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
        "name": "PlayRole",
        "plural_name": "Play Roles",
        "fields": [
            {
                "name": "xml_id",
                "label": "XML ID",
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
                "name": "role",
                "label": "Role",
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
                "name": "line_locations",
                "label": "Line Locations",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "LineLocation",
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
                "template": "{{ PlayRole.role }}",
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
        "name": "StageDirection",
        "plural_name": "Stage Directions",
        "fields": [
            {
                "name": "direction_type",
                "label": "Type",
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
                "name": "roles",
                "label": "Roles",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "PlayRole",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "line_location",
                "label": "Line Location",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "LineLocation",
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
                "template": "{{ StageDirection.direction_type }}",
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
        "name": "PlayStyle",
        "plural_name": "Play Styles",
        "fields": [
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
                "name": "line_location",
                "label": "Line Location",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "LineLocation",
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
                "template": "{{ PlayStyle.line_location.label }}: {{ PlayStyle.classes }}",
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
                "name": "starting_line",
                "label": "Starting Line",
                "indexed": False,
                "unique": False,
                "multiple": False,
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
                "name": "ending_line",
                "label": "Ending Line",
                "indexed": False,
                "unique": False,
                "multiple": False,
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
            }
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
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{% if TextualVariant.lemma %}<b>Lemma:</b> {{ TextualVariant.lemma }} {% endif %}{% if TextualVariant.transform_type %}<b>Transform Type:</b> {{ TextualVariant.transform_type }} {% endif %}{% if TextualVariant.transform %}<b>Transform:</b> {{ TextualVariant.transform }} {% endif %}{% if TextualVariant.description %}<b>Description:</b> {{ TextualVariant.description }} {% endif %} ({{ TextualVariant.witnesses|length }})",
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
