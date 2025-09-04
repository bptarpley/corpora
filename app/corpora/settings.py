import os
import json
import traceback
from mongoengine import connect
from huey import PriorityRedisHuey
from neo4j import GraphDatabase
from rest_framework.parsers import FileUploadParser
from elasticsearch_dsl import connections


# Basic Django config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = '=4@4^2y04f^c6^q9b7y*3r2n7+hsf+!3ou^m+bzlgk0#h&w=$1'
DEBUG = os.environ.get('CRP_DEVELOPMENT', 'no') == 'yes'

if 'CRP_HOST' in os.environ:
    ALLOWED_HOSTS = [os.environ['CRP_HOST']]
elif 'CRP_HOSTS' in os.environ:
    ALLOWED_HOSTS = [h for h in os.environ['CRP_HOSTS'].split(',') if h]

if 'nginx' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('nginx')

CSRF_TRUSTED_ORIGINS = []
for host in ALLOWED_HOSTS:
    CSRF_TRUSTED_ORIGINS.append(f'http://{host}')
    CSRF_TRUSTED_ORIGINS.append(f'https://{host}')

# Corpora sites config (for using Corpora as frontend)
if os.path.exists('/conf/corpora_sites.json'):
    with open('/conf/corpora_sites.json', 'r') as sites_in:
        CORPORA_SITES = json.load(sites_in)
else:
    CORPORA_SITES = {}

DEFAULT_USER_USERNAME = os.environ.get('CRP_DEFAULT_USER_USERNAME', 'corpora')
DEFAULT_USER_PASSWORD = os.environ.get('CRP_DEFAULT_USER_PASSWORD', 'corpora')
DEFAULT_USER_FNAME = os.environ.get('CRP_DEFAULT_USER_FNAME', 'Corpora')
DEFAULT_USER_LNAME = os.environ.get('CRP_DEFAULT_USER_LNAME', 'McCorpus')
DEFAULT_USER_EMAIL = os.environ.get('CRP_DEFAULT_USER_EMAIL', 'corpora@{0}'.format(ALLOWED_HOSTS[0]))
REDIS_HOST = os.environ.get('CRP_REDIS_HOST', 'redis')
REDIS_CACHE_EXPIRY_SECONDS = os.environ.get('CRP_REDIS_CACHE_EXPIRY_SECONDS', 1800)

if '.' not in DEFAULT_USER_EMAIL:
    DEFAULT_USER_EMAIL += '.com'


# Django app config
INSTALLED_APPS = [
    'daphne',
    'django_eventstream',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'huey.contrib.djhuey',
    'corsheaders',
    'manager',
    'plugins',
    'plugins.document',
]

installed_plugins = os.environ.get('CRP_INSTALLED_PLUGINS', '')
if installed_plugins:
    installed_plugins = [f'plugins.{p.strip()}' for p in installed_plugins.split(',') if p]
    INSTALLED_APPS += installed_plugins

INSTALLED_APPS += [
    'django_drf_filepond',
    'rest_framework',
    'rest_framework.authtoken',
]

MIDDLEWARE = [
    'manager.middleware.ChunkedTransferMiddleware',
    'manager.middleware.SiteMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'corpora.urls'

# configuring templates and disabling caching if DEBUG = True
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            '/corpora'
        ],
        'APP_DIRS': not DEBUG,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

if DEBUG:
    TEMPLATES[0]['OPTIONS']['loaders'] = [
        "django.template.loaders.filesystem.Loader",
        "django.template.loaders.app_directories.Loader",
    ]

WSGI_APPLICATION = 'corpora.wsgi.application'
ASGI_APPLICATION = 'corpora.asgi.application'


# Redis config
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://{0}:6379/1".format(os.environ.get('CRP_REDIS_HOST', 'redis')),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient"
        },
        "KEY_PREFIX": "corpora"
    }
}


# Database config
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/conf/corpora_users.sqlite3',
    }
}

# Register any plugin databases
for app in INSTALLED_APPS:
    if app.startswith('plugins.'):
        app_label = app.replace('plugins.', '')
        if os.path.exists(BASE_DIR + f'/plugins/{app_label}/models.py'):
            if app not in DATABASES:
                DATABASES[app] = {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': f'/conf/{app}.sqlite3',
                }

DATABASE_ROUTERS = ['plugins.PluginModelRouter']


# Mongoengine config
MONGO_DB = os.environ['CRP_MONGO_DB']
MONGO_USER = os.environ['CRP_MONGO_USER']
MONGO_PWD = os.environ['CRP_MONGO_PWD']
MONGO_HOST = os.environ['CRP_MONGO_HOST']
MONGO_AUTH_SOURCE = os.environ.get('CRP_MONGO_AUTH_SOURCE', 'admin')
MONGO_POOLSIZE = os.environ['CRP_MONGO_POOLSIZE']

connect(
    MONGO_DB,
    host=MONGO_HOST,
    username=MONGO_USER,
    password=MONGO_PWD,
    authentication_source=MONGO_AUTH_SOURCE,
    maxpoolsize=MONGO_POOLSIZE
)


# Neo4j config
NEO4J = None
try:
    NEO4J = GraphDatabase.driver(
        "bolt://{0}".format(os.environ['CRP_NEO4J_HOST']),
        auth=('neo4j', os.environ['CRP_NEO4J_PWD'])
    )
    with NEO4J.session() as test_session:
        test_session.run("MATCH (n) RETURN count(n) as count")
except:
    print(traceback.format_exc())
    print("Neo4J database uninitialized.")
    NEO4J = None


# Elasticsearch config
connections.configure(
    default={
        'hosts': os.environ['CRP_ELASTIC_HOST'],
        'timeout': 60,
    },
)

ES_SYNONYM_OPTIONS = {}
if 'CRP_ELASTIC_SYNONYM_OPTIONS' in os.environ:
    syn_options = os.environ['CRP_ELASTIC_SYNONYM_OPTIONS'].split(',')
    for syn_option in syn_options:
        syn_specs = syn_option.split(':')
        if len(syn_specs) == 3:
            ES_SYNONYM_OPTIONS[syn_specs[0]] = {
                'label': syn_specs[1],
                'file': syn_specs[2]
            }


# Email config
email_settings = [
    'CRP_EMAIL_HOST',
    'CRP_EMAIL_USE_TLS',
    'CRP_EMAIL_PORT',
    'CRP_EMAIL_USER',
    'CRP_EMAIL_PASSWORD'
]
email_configured = True
for email_setting in email_settings:
    if email_setting not in os.environ:
        email_configured = False
if email_configured:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ['CRP_EMAIL_HOST']
    EMAIL_USE_TLS = os.environ['CRP_EMAIL_USE_TLS'] == 'yes'
    EMAIL_PORT = int(os.environ['CRP_EMAIL_PORT'])
    EMAIL_HOST_USER = os.environ['CRP_EMAIL_USER']
    EMAIL_HOST_PASSWORD = os.environ['CRP_EMAIL_PASSWORD']


# Corpora content config
INVALID_FIELD_NAMES = [
    "id",
    "corpus_id",
    "content_type",
    "last_updated",
    "provenance",
    "path",
    "label",
    "uri",
    "objects",
]

VALID_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'tiff', 'tif']


# REST Framework config
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PARSER_CLASSES': (
        FileUploadParser
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50
}


# CORS config
CORS_ORIGIN_ALLOW_ALL = True
CORS_URLS_REGEX = r'^/api/.*$'
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'upload-length',
    'upload-offset',
    'upload-name',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]
X_FRAME_OPTIONS = 'SAMEORIGIN'


# Huey config
HUEY = PriorityRedisHuey('corpora', host='redis')
NUM_HUEY_WORKERS = os.environ.get('CRP_HUEY_WORKERS')
NUM_JOBS_PER_MINUTE = int(os.environ.get('CRP_NUM_JOBS_PER_MINUTE', 200))
JOB_TIMEOUT_SECS = int(os.environ.get('CRP_JOB_TIMEOUT_SECS', 86400))


# iPython Notebook config
NOTEBOOK_ARGUMENTS = [
    '--ip', '0.0.0.0',
    '--port', '9999',
    '--no-browser',
]


# Login/auth config
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LOGIN_URL = '/scholar'
USE_SSL = os.environ['CRP_USE_SSL'] == 'yes'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTOCOL', 'https')


# Internationalization config
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files config
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

STATIC_URL = '/static/'
STATIC_ROOT = '/static'

# to prevent stale browser caching
STATIC_NO_CACHE_SUFFIX = 'nocache'
if os.path.exists('/corpora/.last_started'):
    STATIC_NO_CACHE_SUFFIX = str(int(os.path.getmtime('/corpora/.last_started')))

DJANGO_DRF_FILEPOND_UPLOAD_TMP = '/corpora/uploads/temp'
DJANGO_DRF_FILEPOND_FILE_STORE_PATH = '/corpora/uploads/files'
DJANGO_DRF_FILEPOND_ALLOW_EXTERNAL_UPLOAD_DIR = True
