from corpus import Corpus, Document
from rest_framework_mongoengine.serializers import DocumentSerializer


class DHDCorpusSerializer(DocumentSerializer):
    class Meta:
        model = Corpus
        fields = '__all__'


class DHDocumentSerializer(DocumentSerializer):
    class Meta:
        model = Document
        fields = '__all__'
