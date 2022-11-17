from corpus import Content


REGISTRY = [
    {
        "name": "Play",
        "plural_name": "Plays",
        "fields": [
            {
                "name": "title",
                "label": "Title",
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
                "name": "prefix",
                "label": "NVS Prefix",
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
                "name": "base_text",
                "label": "Base Text",
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
                "name": "primary_witnesses",
                "label": "Primary Witnesses",
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
                "name": "occasional_witnesses",
                "label": "Occasional Witnesses",
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
                "name": "primary_sources",
                "label": "Primary Sources",
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
                "name": "occasional_sources",
                "label": "Occasional Sources",
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
                "name": "bibliographic_sources",
                "label": "Bibliographic Sources",
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
                "name": "genre",
                "label": "Genre",
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
                "template": "{{ Play.title }}",
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
            },
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
            "path",
            "label",
            "uri",
            "last_updated",
            "provenance"
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
                "unique_with": [
                    "play"
                ],
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
            },
            {
                "name": "play",
                "label": "Play",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
                "has_intensity": False,
                "language": None,
                "autocomplete": False,
                "synonym_file": None,
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
            "path",
            "label",
            "uri",
            "last_updated",
            "provenance"
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
            },
            {
                "name": "play",
                "label": "Play",
                "indexed": True,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
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
            "path",
            "label",
            "uri",
            "last_updated",
            "provenance"
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
                "unique": True,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": ["play"],
                "stats": {},
                "inherited": False
            },
            {
                "name": "alt_xml_ids",
                "label": "Alternate XML IDs",
                "indexed": False,
                "unique": False,
                "multiple": True,
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
                "name": "line_label",
                "label": "Line Label",
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
                "name": "line_number",
                "label": "Line Number",
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
                "name": "act",
                "label": "Act",
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
                "name": "scene",
                "label": "Scene",
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
                "name": "text",
                "label": "Text",
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
                "name": "rendered_html",
                "label": "Rendered HTML",
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
            },
            {
                "name": "play",
                "label": "Play",
                "indexed": True,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
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
                "template": "{{ PlayLine.xml_id }}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "path",
            "label",
            "uri",
            "last_updated",
            "provenance"
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
                "name": "start_location",
                "label": "Starting Location",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "decimal",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "end_location",
                "label": "Ending Location",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "decimal",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "play",
                "label": "Play",
                "indexed": True,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
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
                "template": "[{{ PlayTag.name }} class=\"{{ PlayTag.classes }}\"]",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "path",
            "label",
            "uri",
            "last_updated",
            "provenance"
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
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "has_intensity": False,
                "language": None,
                "autocomplete": False,
                "synonym_file": None,
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
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "has_intensity": False,
                "language": None,
                "autocomplete": False,
                "synonym_file": None,
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
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "has_intensity": False,
                "language": None,
                "autocomplete": False,
                "synonym_file": None,
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
                "has_intensity": False,
                "language": None,
                "autocomplete": False,
                "synonym_file": None,
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
                "has_intensity": False,
                "language": "english",
                "autocomplete": False,
                "synonym_file": "early_modern",
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
                "has_intensity": False,
                "language": "english",
                "autocomplete": False,
                "synonym_file": None,
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
                "in_lists": False,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Document",
                "has_intensity": False,
                "language": None,
                "autocomplete": False,
                "synonym_file": None,
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
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "has_intensity": False,
                "language": "english",
                "autocomplete": False,
                "synonym_file": None,
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
                "has_intensity": False,
                "language": None,
                "autocomplete": False,
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "play",
                "label": "Play",
                "indexed": True,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
                "has_intensity": False,
                "language": None,
                "autocomplete": False,
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            }
        ],
        "show_in_nav": True,
        "autocomplete_labels": False,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{% if TextualVariant.lemma %}LEM: {{ TextualVariant.lemma|striptags }} {% endif %}{% if TextualVariant.transform_type %}TYPE: {{ TextualVariant.transform_type|striptags }} {% endif %}{% if TextualVariant.transform %}TRANS: {{ TextualVariant.transform|striptags }} {% endif %}{% if TextualVariant.description %}DESC: {{ TextualVariant.description|striptags }} {% endif %}",
                "mime_type": "text/html"
            }
        },
        "view_widget_url": None,
        "edit_widget_url": None,
        "inherited_from_module": None,
        "inherited_from_class": None,
        "base_mongo_indexes": None,
        "has_file_field": False,
        "invalid_field_names": [
            "corpus_id",
            "label",
            "content_type",
            "path",
            "uri",
            "last_updated",
            "provenance"
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
                "name": "play",
                "label": "Play",
                "indexed": True,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
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
            "path",
            "label",
            "uri",
            "last_updated",
            "provenance"
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
            },
            {
                "name": "play",
                "label": "Play",
                "indexed": True,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
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
            "path",
            "label",
            "uri",
            "last_updated",
            "provenance"
        ]
    },
    {
        "name": "Document",
        "plural_name": "Documents",
        "fields": [
            {
                "name": "title",
                "label": "Title",
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
                "inherited": True
            },
            {
                "name": "author",
                "label": "Author",
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
                "inherited": True
            },
            {
                "name": "work",
                "label": "Work",
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
                "inherited": True
            },
            {
                "name": "expression",
                "label": "Expression",
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
                "inherited": True
            },
            {
                "name": "manifestation",
                "label": "Manifestation",
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
                "inherited": True
            },
            {
                "name": "pub_date",
                "label": "Published",
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
                "inherited": True
            },
            {
                "name": "files",
                "label": "Files",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": False,
                "type": "embedded",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": True
            },
            {
                "name": "pages",
                "label": "Pages",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": False,
                "type": "embedded",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": True
            },
            {
                "name": "page_sets",
                "label": "Page Sets",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": False,
                "type": "embedded",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": True
            },
            {
                "name": "editor",
                "label": "Editor(s)",
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
                "name": "publisher",
                "label": "Publisher",
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
                "name": "place",
                "label": "Place of Publication",
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
                "name": "siglum",
                "label": "Siglum",
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
                "name": "bibliographic_entry",
                "label": "Bibliographic Entry",
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
            },
            {
                "name": "nvs_doc_type",
                "label": "Document Type",
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
                "template": "{{ Document.siglum_label|safe }}",
                "mime_type": "text/html"
            }
        },
        "inherited": True,
        "invalid_field_names": [
            "has_primary_text",
            "corpus_id",
            "content_type",
            "path",
            "label",
            "uri",
            "last_updated",
            "provenance",
            "save_page",
            "ordered_pages",
            "save_file",
            "kvp",
            "running_jobs",
            "get_page_file_collection",
            "page_file_collections",
            "save_page_file"
        ]
    },
    {
        "name": "Character",
        "plural_name": "Characters",
        "fields": [
            {
                "name": "name",
                "label": "Name",
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
                "name": "xml_id",
                "label": "XML ID",
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
                "name": "external_uri",
                "label": "External URI",
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
                "name": "speaker_abbreviations",
                "label": "Speaker Abbreviations",
                "indexed": False,
                "unique": False,
                "multiple": True,
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
                "name": "play",
                "label": "Play",
                "indexed": True,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
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
                "template": "{{ Character.name }}",
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
        "name": "Speech",
        "plural_name": "Speeches",
        "fields": [
            {
                "name": "act",
                "label": "Act",
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
                "name": "scene",
                "label": "Scene",
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
                "name": "speaking",
                "label": "Characters Speaking",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Character",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "text",
                "label": "Text",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "html",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": "early_modern",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "play",
                "label": "Play",
                "indexed": True,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
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
                "template": "{{ Speech.act }}.{{ Speech.scene }}.{{ Speech.line_number }} ({% for speaker in Speech.speaking %}{% if not forloop.first %}, {% endif %}{{ speaker.name }}{% endfor %})",
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
        "name": "ParaText",
        "plural_name": "Paratexts",
        "fields": [
            {
                "name": "xml_id",
                "label": "XML ID",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "section",
                "label": "Section",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "title",
                "label": "Title",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "html_content",
                "label": "HTML Content",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "large_text",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": "early_modern",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "child_xml_ids",
                "label": "Child XML IDs",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "level",
                "label": "Level",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "number",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
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
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "parent",
                "label": "Parent",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "ParaText",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "play",
                "label": "Play",
                "indexed": True,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
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
                "template": "{{ ParaText.title }} (from {{ ParaText.section }})",
                "mime_type": "text/html"
            }
        },
        "inherited": True,
        "inherited_from_module": "plugins.nvs.content",
        "inherited_from_class": "ParaText",
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri",
            "children"
        ],
        "view_widget_url": None,
        "edit_widget_url": None
    },
    {
        "name": "Reference",
        "plural_name": "References",
        "fields": [
            {
                "name": "play",
                "label": "Play",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Play",
                "has_intensity": False,
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "document",
                "label": "Document",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Document",
                "has_intensity": False,
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "ref_type",
                "label": "Reference Type",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "has_intensity": False,
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "bibliographic_entry",
                "label": "Bibliographic Entry",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "html",
                "choices": [],
                "cross_reference_type": "",
                "has_intensity": False,
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "bibliographic_entry_text",
                "label": "Bibliographic Entry Text",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "text",
                "choices": [],
                "cross_reference_type": "",
                "has_intensity": False,
                "synonym_file": None,
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
                "template": "Reference {{ Reference.id }}",
                "mime_type": "text/html"
            }
        },
        "inherited": False,
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "field_intensities",
            "path",
            "label",
            "uri"
        ],
        "view_widget_url": None,
        "edit_widget_url": None
    }
]


class ParaText(Content):

    @property
    def children(self):
        if not hasattr(self, '_children'):
            setattr(self, '_children', self._corpus.get_content('ParaText', {
                'parent': self.id,
                'level': self.level + 1
            }).order_by('order'))
        return self._children

    @property
    def toc_html(self):
        if self.level <= 2:
            if not hasattr(self, '_toc_html'):
                html = '''
                    <li class="anchor-link is-level-{0}">
                        <a href="#paratext-{1}">{2}</a>
                    </li>
                '''.format(
                    self.level,
                    self.id,
                    self.title
                )

                if self.children:
                    for child in self.children:
                        html += child.toc_html

                setattr(self, '_toc_html', html)
            return self._toc_html
        return ''

    @property
    def full_html(self):
        if not hasattr(self, '_full_html'):
            html = '<a name="paratext-{0}" class="anchor"></a>'.format(self.id)
            html += '<h2 class="section-heading level-{0}">{1}</h2>'.format(
                self.level,
                self.title
            )
            html += self.html_content
            for child in self.children:
                html += child.full_html

            setattr(self, '_full_html', html)
        return self._full_html

    meta = {
        'abstract': True
    }
