REGISTRY = [
    {
        "name": "Gender",
        "plural_name": "Genders",
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
                "template": "{{ Gender.name }}",
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
        ],
        "view_widget_url": None,
        "edit_widget_url": None
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
                "name": "novels",
                "label": "Novels",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Document",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "sex",
                "label": "Sex",
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
                "name": "gender",
                "label": "Gender",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Gender",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "catma_id",
                "label": "CATMA ID",
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
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ Character.name }} ({% for novel in Character.novels %}{% if not forloop.first %}, {% endif %}{{ novel.title }}{% endfor %})",
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
        ],
        "view_widget_url": None,
        "edit_widget_url": None
    },
    {
        "name": "Tag",
        "plural_name": "Tags",
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
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "catma_id",
                "label": "CATMA ID",
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
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ Tag.name }}",
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
        ],
        "view_widget_url": None,
        "edit_widget_url": None
    },
    {
        "name": "Tagset",
        "plural_name": "Tagsets",
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
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "tags",
                "label": "Tags",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Tag",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "catma_id",
                "label": "CATMA ID",
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
            }
        ],
        "show_in_nav": True,
        "proxy_field": "",
        "templates": {
            "Label": {
                "template": "{{ Tagset.name }}",
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
        ],
        "view_widget_url": None,
        "edit_widget_url": None
    },
    {
        "name": "Tagging",
        "plural_name": "Taggings",
        "fields": [
            {
                "name": "novel",
                "label": "Novel",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Document",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "character",
                "label": "Character",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Character",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "tag",
                "label": "Tag",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Tag",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "location_start",
                "label": "Location Start",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "decimal",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
                "indexed_with": [],
                "unique_with": [],
                "stats": {},
                "inherited": False
            },
            {
                "name": "location_end",
                "label": "Location End",
                "indexed": False,
                "unique": False,
                "multiple": False,
                "in_lists": True,
                "type": "decimal",
                "choices": [],
                "cross_reference_type": "",
                "synonym_file": None,
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
                "type": "large_text",
                "choices": [],
                "cross_reference_type": "",
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
                "template": "{{ Tagging.tag.name }}",
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
        ],
        "view_widget_url": None,
        "edit_widget_url": None
    },
    {
        "name": "Keyword",
        "plural_name": "BookNLP Keywords",
        "fields": [
            {
                "name": "word",
                "label": "Word",
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
                "name": "mode",
                "label": "Mode",
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
                "name": "characters",
                "label": "Characters",
                "indexed": False,
                "unique": False,
                "multiple": True,
                "in_lists": True,
                "type": "cross_reference",
                "choices": [],
                "cross_reference_type": "Character",
                "synonym_file": None,
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
                "template": "{{ Keyword.word }} ({{ Keyword.mode }})",
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
        ],
        "view_widget_url": None,
        "edit_widget_url": None
    },
]
