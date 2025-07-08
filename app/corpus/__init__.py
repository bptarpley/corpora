"""
Corpus API

This module provides a comprehensive data management system that mirrors database functionality
using MongoDB for document storage, Elasticsearch for full-text search, and Neo4j for graph
relationships. The core architecture follows a hierarchical structure:

- Corpus (analogous to a database)
  - Content Types (analogous to tables)
    - Fields (analogous to columns)
      - Content instances (analogous to rows)

The system supports:
- Dynamic schema definition and modification
- Multi-language text analysis (34 languages)
- Cross-references between content types
- File and media management
- Provenance tracking and audit trails
- Advanced search with faceting and aggregations
- Graph-based relationship queries
"""

# As a bad habit, much of Corpora's code base was written by taking this shortcut:
#
# from corpus import *
#
# As a result, many plugins took advantage of the various import statements used
# by the Corpus API as a whole before its file structure was broken out into
# separate, class-based files (it used to be one giant file). As a workaround
# until all plugin code can be refactored to rely on their own explicit import
# statements, the following imports are for legacy support:
import mongoengine
import os
import json
import secrets
import traceback
import importlib
import zlib
import shutil
import redis
import requests
import git
import re
import calendar
from math import ceil
from copy import deepcopy
from datetime import datetime, timezone
from dateutil import parser
from bson.objectid import ObjectId
from bson import DBRef
from PIL import Image
from django.conf import settings
from django.utils.text import slugify
from elasticsearch_dsl import Index, Mapping, analyzer, Keyword, Text, Integer, Date, \
    GeoPoint, GeoShape, Nested, token_filter, char_filter, Q, A, Search
from elasticsearch_dsl.query import SimpleQueryString, Ids
from elasticsearch_dsl.connections import get_connection
from django.template import Template, Context
from .language_settings import REGISTRY as lang_settings

# Here is where the proper import statements commence:
import logging
from .scholar import Scholar
from .corpus import Corpus, CorpusBackup
from .content_type import ContentType, ContentTemplate, ContentTypeGroupMember, ContentTypeGroup
from .field import Field, FieldRenderer, FIELD_LANGUAGES, FIELD_TYPES
from .field_types.file import File
from .field_types.timespan import Timespan
from .field_types.gitrepo import GitRepo
from .job import Task, CompletedTask, Job, JobTracker, JobSite, Process
from .content import Content, ContentView, ContentDeletion
from .utilities import (
    ensure_connection, get_corpus, parse_date_string,
    search_corpora, search_scholars, run_neo,
    ensure_neo_indexes, get_network_json, publish_message,
    get_field_value_from_path
)


# Since we do a lot of querying and modifying of Elasticsearch
# indexes, it drastically helps cut down on the stdout noise by setting
# its logging threshold to ERROR
es_logger = logging.getLogger('elasticsearch')
es_logger.setLevel(logging.ERROR)


# Eventually, the following measure will be taken to ensure classes are
# imported cleanly:
'''
__all__ = [
    # Classes
    'Field', 'FieldRenderer', 'ContentType', 'ContentTemplate',
    'ContentTypeGroup', 'ContentTypeGroupMember', 'Corpus', 'CorpusBackup',
    'Content', 'ContentView', 'ContentDeletion', 'Scholar',
    'Task', 'CompletedTask', 'Job', 'JobTracker', 'JobSite', 'Process',
    'File', 'Timespan', 'GitRepo',
    # Utility Functions
    'ensure_connection', 'get_corpus', 'parse_date_string',
    'search_corpora', 'search_scholars', 'run_neo',
    'ensure_neo_indexes', 'get_network_json', 'publish_message',
    'get_field_value_from_path',
    # Constants
    'FIELD_LANGUAGES', 'FIELD_TYPES'
]
'''
