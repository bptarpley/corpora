from django.core.management.base import BaseCommand
from manager.utilities import order_content_schema
from corpus import Corpus


class Command(BaseCommand):
    def handle(self, *args, **options):
        for c in Corpus.objects.all():
            print(f"Adding corpus \"{c.name}\" to corpus index...")
            c.save()

            ordered_schema = []
            for ct_name in c.content_types.keys():
                ordered_schema.append(c.content_types[ct_name].to_dict())
            ordered_schema = order_content_schema(ordered_schema)

            for ct in ordered_schema:
                ct_name = ct['name']
                print(f"Rebuilding \"{ct_name}\" content type index...")
                c.build_content_type_elastic_index(ct_name)

                content_count = 0
                for content in c.get_content(ct_name, all=True):
                    content._do_indexing()
                    content_count += 1
                print(f"Reindexed {content_count} \"{ct_name}\" instances!")

            print("\n")

        print("All content successfully reindexed.")
