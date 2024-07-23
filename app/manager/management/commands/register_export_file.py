from django.core.management.base import BaseCommand
from manager.utilities import process_corpus_export_file


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('export_filename', type=str, help='The name of the export file, i.e. 6285564874d5f7a229b60520_2024_05_02.tar.gz')

    def handle(self, *args, **options):
        export_filename = options['export_filename']
        if process_corpus_export_file(export_filename):
            print("Export file successfully registered :)")
        else:
            print("An error occurred while registering this export file!")
