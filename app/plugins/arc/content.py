import mongoengine
from corpus import Content

REGISTRY = [
    {
        "name": "ArcFederation",
        "plural_name": "Federations",
        "fields": [
            {
                "name": "handle",
                "label": "Handle",
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
                "name": "external_uri",
                "label": "External URI",
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
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ ArcFederation.handle }}",
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
            "uri",
        ]
    },
    {
        "name": "ArcType",
        "plural_name": "Types",
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
                "name": "external_uri",
                "label": "External URI",
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
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ ArcType.name }}",
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
            "uri",
        ]
    },
    {
        "name": "ArcEntity",
        "plural_name": "Entities",
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
                "name": "entity_type",
                "label": "Entity Type",
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
                "name": "external_uri_verified",
                "label": "External URI Verified?",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "boolean",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "external_uri_needs_attention",
                "label": "External URI Needs Attention",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "boolean",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "external_uri_notes",
                "label": "External URI Notes",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "html",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "alternate_names",
                "label": "Alternate Names",
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
            }
        ],
        "edit_widget_url": "/corpus/{corpus_id}/{content_type}/{content_id}/UriAscription/",
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ ArcEntity.name }}",
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
            "uri",
        ]
    },
    {
        "name": "ArcRole",
        "plural_name": "Roles",
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
                "name": "external_uri",
                "label": "External URI",
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
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ ArcRole.name }}",
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
            "uri",
        ]
    },
    {
        "name": "ArcAgent",
        "plural_name": "Agents",
        "fields": [
            {
                "name": "entity",
                "label": "Entity",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "ArcEntity",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "role",
                "label": "Role",
                "indexed": False,
                "unique": True,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "ArcRole",
                "indexed_with": [],
                "unique_with": [
                    "entity"
                ],
                "stats": {},
                "inherited": False
            },
            {
                "name": "uri_attribution_attempted",
                "label": "URI Attribution Attempted?",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "boolean",
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
                "template": "{{ ArcAgent.entity.label }} ({{ ArcAgent.role.label }})",
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
            "uri",
        ]
    },
    {
        "name": "ArcDiscipline",
        "plural_name": "Disciplines",
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
                "name": "external_uri",
                "label": "External URI",
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
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ ArcDiscipline.name }}",
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
            "uri",
        ]
    },
    {
        "name": "ArcGenre",
        "plural_name": "Genres",
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
                "name": "external_uri",
                "label": "External URI",
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
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ ArcGenre.name }}",
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
            "uri",
        ]
    },
    {
        "name": "ArcArchive",
        "plural_name": "Archives",
        "fields": [
            {
                "name": "handle",
                "label": "Handle",
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
                "name": "git_repository",
                "label": "Git Repository",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "last_indexed",
                "label": "Last Indexed",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "date",
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
                "unique": True,
                "multiple": False,
                "in_lists": False,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "site_url",
                "label": "Site URL",
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
                "name": "thumbnail",
                "label": "Thumbnail",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "keyword",
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
                "name": "featured_image",
                "label": "Featured Image",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "parent_path",
                "label": "Parent Path",
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
                "template": "{{ ArcArchive.handle }}",
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
            "uri",
        ]
    },
    {
        "name": "ArcArtifact",
        "plural_name": "Artifacts",
        "fields": [
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
                "name": "url",
                "label": "URL",
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
                "name": "archive",
                "label": "Archive",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "ArcArchive",
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
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "federations",
                "label": "Federations",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "ArcFederation",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "types",
                "label": "Types",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "ArcType",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "agents",
                "label": "Agents",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "ArcAgent",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "disciplines",
                "label": "Disciplines",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "ArcDiscipline",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "genres",
                "label": "Genres",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "ArcGenre",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "date_label",
                "label": "Date Label",
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
                "name": "date_value",
                "label": "Date Value",
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
                "name": "years",
                "label": "Years",
                "indexed": False,
                "unique": False,
                "multiple": True,
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
                "name": "alt_title",
                "label": "Alternate Title",
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
                "name": "date_of_edition",
                "label": "Date of Edition",
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
                "name": "date_of_review",
                "label": "Date of Review",
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
                "name": "language",
                "label": "Language",
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
                "name": "sources",
                "label": "Sources",
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
                "name": "subjects",
                "label": "Subjects",
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
                "name": "coverages",
                "label": "Coverages",
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
                "name": "free_culture",
                "label": "Free Culture?",
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
                "name": "ocr",
                "label": "OCR?",
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
                "name": "full_text",
                "label": "Full Text?",
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
                "name": "full_text_url",
                "label": "Full Text URL",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "full_text_contents",
                "label": "Full Text Contents",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "large_text",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "image_url",
                "label": "Image URL",
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
                "name": "thumbnail_url",
                "label": "Thumbnail URL",
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
                "name": "source_xml",
                "label": "XML Source Code",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "source_html",
                "label": "HTML Source Code",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "source_sgml",
                "label": "SGML Source Code",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": False,
                "type": "keyword",
                "choices": [],
                "cross_reference_type": "",
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "has_parts",
                "label": "Has Part(s)",
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
                "name": "is_part_ofs",
                "label": "Is Part Of(s)",
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
                "name": "relateds",
                "label": "Related To(s)",
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
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ ArcArtifact.title }}",
                "mime_type": "text/html"
            },
            "ArcRDF": {
                "template": "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<rdf:RDF\n      xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"\n      xmlns:dc=\"http://purl.org/dc/elements/1.1/\"\n      xmlns:dcterms=\"http://purl.org/dc/terms/\"\n      xmlns:collex=\"http://www.collex.org/schema#\"\n      xmlns:{{ ArcArtifact.archive.handle }}=\"http://www.ar-c.org/archive/{{ ArcArtifact.archive.handle }}/schema#\"\n      xmlns:rdfs=\"http://www.w3.org/2000/01/rdf-schema#\"\n      xmlns:role=\"http://www.loc.gov/loc.terms/relators/\">\n\n   <{{ ArcArtifact.archive.handle }}:artifact rdf:about=\"{{ ArcArtifact.external_uri }}\">\n        \n        {% for fed in ArcArtifact.federations %}\n            <collex:federation>{{ fed.handle }}</collex:federation>\n        {% endfor %}\n        \n        <collex:archive>{{ ArcArtifact.archive.handle }}</collex:archive>\n        <dc:title>{{ ArcArtifact.title }}</dc:title>\n        \n        {% if ArcArtifact.title %}\n            <dcterms:alternative>{{ ArcArtifact.title }}</dcterms:alternative>\n        {% endif %}\n    \n        {% for src in ArcArtifact.sources %}\n            <dc:source>{{ src }}</dc:source>\n        {% endfor %}\n    \n        {% for agent in ArcArtifact.agents %}\n            <role:{{ agent.role.name }}>{{ agent.entity.name }}</role:{{ agent.role.name }}>\n        {% endfor %}\n            \n        {% for art_type in ArcArtifact.types %}\n            <dc:type>{{ art_type }}</dc:type>\n        {% endfor %}\n        \n        {% for art_disc in ArcArtifact.types %}\n            <collex:discipline>{{ art_disc }}</collex:discipline>\n        {% endfor %}\n\n        {% for genre in ArcArtifact.genres %}\n            <collex:genre>{{ genre }}</collex:genre>\n        {% endfor %}\n\n        <rdfs:seeAlso rdf:resource=\"{{ ArcArtifact.url }}\"/>\n\n   </{{ ArcArtifact.archive.handle }}:artifact>\n\n</rdf:RDF>",
                "mime_type": "text/xml"
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
            "uri",
        ]
    },
    {
        "name": "UriAscription",
        "plural_name": "URI Ascriptions",
        "show_in_nav": True,
        "proxy_field": "",
        "inherited": True,
        "inherited_from_module": "plugins.arc.content",
        "inherited_from_class": "URIAscription",
        "has_file_field": False,
        "fields": [
            {
                "name": "corpora_uri",
                "label": "Corpora URI",
                "type": "keyword",
                "unique": True,
                "inherited": True
            },
            {
                "name": "ascriptions",
                "label": "Ascriptions",
                "type": "embedded",
                "multiple": True,
                "inherited": True,
                "in_lists": False
            }
        ],
        "invalid_field_names": [
            "corpus_id",
            "content_type",
            "last_updated",
            "provenance",
            "path",
            "label",
            "uri",
        ],
        "templates": {
            "Label": {
                "template": "{{ UriAscription.corpora_uri }}",
                "mime_type": "text/html"
            }
        },
    }
]

class Ascription(mongoengine.EmbeddedDocument):
    uri = mongoengine.StringField()
    label = mongoengine.StringField()
    name_probability = mongoengine.FloatField()
    date_probability = mongoengine.FloatField()
    title_score = mongoengine.FloatField()
    total_score = mongoengine.FloatField()

    def to_dict(self):
        return {
            'uri': self.uri,
            'label': self.label,
            'name_probability': self.name_probability,
            'date_probability': self.date_probability,
            'title_score': self.title_score,
            'total_score': self.total_score
        }


class URIAscription(Content):
    corpora_uri = mongoengine.StringField(unique=True)
    ascriptions = mongoengine.ListField(mongoengine.EmbeddedDocumentField(Ascription))

    @property
    def best_uri(self):
        best = None
        highest_score = 0

        for asc in self.ascriptions:
            if asc.total_score > highest_score:
                best = asc.uri
                highest_score = asc.total_score

        return best

    @property
    def best_score(self):
        highest_score = 0

        for asc in self.ascriptions:
            if asc.total_score > highest_score:
                highest_score = asc.total_score

        return highest_score

    def to_dict(self, ref_only=False):
        return {
            'corpora_uri': self.corpora_uri,
            'ascriptions': [asc.to_dict() for asc in self.ascriptions]
        }

    meta = {
        'abstract': True
    }
