from django.core.management.base import BaseCommand
from manager.utilities import reindex_corpus
from corpus import Corpus


class Command(BaseCommand):
    help = "Rebuild the Elasticsearch index for every corpus and reindex all content."

    def handle(self, *args, **options):
        # the per-corpus logic is shared with the "Reindex Corpora" task so that this
        # command and the admin action on the Corpora home page behave identically
        for c in Corpus.objects.all():
            reindex_corpus(c, report=self.stdout.write)
            self.stdout.write("\n")

        self.stdout.write("All content successfully reindexed.")
