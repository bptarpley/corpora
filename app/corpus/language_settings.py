REGISTRY = {
    "arabic": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "decimal_digit",
            "arabic_stop",
            "arabic_normalization",
            "arabic_stemmer"
        ]
    },
    "armenian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "armenian_stop",
            "armenian_stemmer"
        ]
    },
    "basque": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "basque_stop",
            "basque_stemmer"
        ]
    },
    "bengali": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "decimal_digit",
            "indic_normalization",
            "bengali_normalization",
            "bengali_stop",
            "bengali_stemmer"
        ]
    },
    "brazilian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "brazilian_stop",
            "brazilian_stemmer"
        ]
    },
    "bulgarian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "bulgarian_stop",
            "bulgarian_stemmer"
        ]
    },
    "catalan": {
        "tokenizer": "standard",
        "filter": [
            "catalan_elision",
            "lowercase",
            "catalan_stop",
            "catalan_stemmer"
        ]
    },
    "cjk": {
        "tokenizer": "standard",
        "filter": [
            "cjk_width",
            "lowercase",
            "cjk_bigram",
            "english_stop"
        ]
    },
    "czech": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "czech_stop",
            "czech_stemmer"
        ]
    },
    "danish": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "danish_stop",
            "danish_stemmer"
        ]
    },
    "dutch": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "dutch_stop",
            "dutch_override",
            "dutch_stemmer"
        ]
    },
    "english": {
        "tokenizer": "standard",
        "filter": [
            "english_possessive_stemmer",
            "lowercase",
            "english_stop",
            "english_stemmer"
        ]
    },
    "estonian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "estonian_stop",
            "estonian_stemmer"
        ]
    },
    "finnish": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "finnish_stop",
            "finnish_stemmer"
        ]
    },
    "french": {
        "tokenizer": "standard",
        "filter": [
            "french_elision",
            "lowercase",
            "french_stop",
            "french_stemmer"
        ]
    },
    "galician": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "galician_stop",
            "galician_stemmer"
        ]
    },
    "german": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "german_stop",
            "german_normalization",
            "german_stemmer"
        ]
    },
    "greek": {
        "tokenizer": "standard",
        "filter": [
            "greek_lowercase",
            "greek_stop",
            "greek_stemmer"
        ]
    },
    "hindi": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "decimal_digit",
            "indic_normalization",
            "hindi_normalization",
            "hindi_stop",
            "hindi_stemmer"
        ]
    },
    "hungarian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "hungarian_stop",
            "hungarian_stemmer"
        ]
    },
    "indonesian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "indonesian_stop",
            "indonesian_stemmer"
        ]
    },
    "irish": {
        "tokenizer": "standard",
        "filter": [
            "irish_hyphenation",
            "irish_elision",
            "irish_lowercase",
            "irish_stop",
            "irish_stemmer"
        ]
    },
    "italian": {
        "tokenizer": "standard",
        "filter": [
            "italian_elision",
            "lowercase",
            "italian_stop",
            "italian_stemmer"
        ]
    },
    "latvian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "latvian_stop",
            "latvian_stemmer"
        ]
    },
    "lithuanian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "lithuanian_stop",
            "lithuanian_stemmer"
        ]
    },
    "norwegian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "norwegian_stop",
            "norwegian_stemmer"
        ]
    },
    "persian": {
        "tokenizer": "standard",
        "char_filter": [
            "zero_width_spaces"
        ],
        "filter": [
            "lowercase",
            "decimal_digit",
            "arabic_normalization",
            "persian_normalization",
            "persian_stop"
        ]
    },
    "portuguese": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "portuguese_stop",
            "portuguese_stemmer"
        ]
    },
    "romanian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "romanian_stop",
            "romanian_stemmer"
        ]
    },
    "russian": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "russian_stop",
            "russian_stemmer"
        ]
    },
    "sorani": {
        "tokenizer": "standard",
        "filter": [
            "sorani_normalization",
            "lowercase",
            "decimal_digit",
            "sorani_stop",
            "sorani_stemmer"
        ]
    },
    "spanish": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "spanish_stop",
            "spanish_stemmer"
        ]
    },
    "swedish": {
        "tokenizer": "standard",
        "filter": [
            "lowercase",
            "swedish_stop",
            "swedish_stemmer"
        ]
    },
    "turkish": {
        "tokenizer": "standard",
        "filter": [
            "apostrophe",
            "turkish_lowercase",
            "turkish_stop",
            "turkish_stemmer"
        ]
    },
    "thai": {
        "tokenizer": "thai",
        "filter": [
            "lowercase",
            "decimal_digit",
            "thai_stop"
        ]
    }
}