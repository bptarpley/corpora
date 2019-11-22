#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='corpora',
    version='1.0',
    description='A web application for managing DH corpora.',
    author='Bryan Tarpley',
    author_email='bptarpley@tamu.edu',
    license='BSD',
    install_requires=[
        'django',
        'gunicorn',
        'mongoengine',
        'blinker',
        'djongo',
        'redis',
        'huey',
        'natsort',
        'Pillow',
        'pypdf2',
        'google-cloud-vision',
        'nltk',
        'matplotlib',
        'beautifulsoup4',
        'django-cors-headers',
        'djangorestframework',
        'pymysql',
        'neo4j',
        'elasticsearch-dsl',
        'lxml',
        'python-dateutil'
    ],
    packages=find_packages(),
)
