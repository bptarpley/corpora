from django.core.management.base import BaseCommand
from manager.utilities import relink_corpus
from corpus import Corpus


class Command(BaseCommand):
    help = "Purge and rebuild the Neo4j nodes and relationships for every corpus."

    def handle(self, *args, **options):
        # the per-corpus logic is shared with the "Relink Corpora" task so that this
        # command and the admin action on the Corpora home page behave identically
        for c in Corpus.objects.all():
            relink_corpus(c, report=self.stdout.write)
            self.stdout.write("\n")

        self.stdout.write("All content successfully relinked :)")
