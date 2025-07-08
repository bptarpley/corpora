from django.core.management.base import BaseCommand
from manager.utilities import process_corpus_backup_file


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('backup_filename', type=str, help='The name of the backup file as it exists in /corpora/backups, i.e. 6285564874d5f7a229b60520_2024_05_02.tar.gz')

    def handle(self, *args, **options):
        backup_filename = options['backup_filename']

        if process_corpus_backup_file(backup_filename):
            print("Backup file successfully registered :)")
        else:
            print("An error occurred while registering this backup file!")
