from django.test import TestCase

# Create your tests here.

def create_document_content_type():
    from corpus import *
    c = Corpus.objects[0]
