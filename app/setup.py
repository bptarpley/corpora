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
        'djongo',
        'mongoengine',
        'redis==3.2.1',
        'huey==2.0.1',
        'natsort',
        'Pillow',
        'pypdf2',
        'pymysql',
        'google-cloud-vision',
        'nltk',
        'matplotlib',
        'djangorestframework',
        'django-rest-framework-mongoengine'
    ],
    packages=find_packages(),
)
