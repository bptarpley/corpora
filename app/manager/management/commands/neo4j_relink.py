from django.core.management.base import BaseCommand
from manager.utilities import order_content_schema
from corpus import Corpus, run_neo


class Command(BaseCommand):
    def handle(self, *args, **options):
        for c in Corpus.objects.all():
            ordered_schema = []
            for ct_name in c.content_types.keys():
                ordered_schema.append(c.content_types[ct_name].to_dict())
            ordered_schema = order_content_schema(ordered_schema)

            for ct in ordered_schema:
                ct_name = ct['name']
                print(f"Relinking \"{ct_name}\" nodes for {c.name}...")

                run_neo(
                    '''
                        MATCH (x:{0} {{corpus_id: $corpus_id}})
                        CALL {{
                            WITH x
                            DETACH DELETE x
                        }} IN TRANSACTIONS OF 50 ROWS
                    '''.format(ct_name),
                    {'corpus_id': str(c.id)}
                )

                content_count = 0
                for content in c.get_content(ct_name, all=True):
                    content._do_linking()
                    content_count += 1
                print(f"Relinked {content_count} \"{ct_name}\" nodes!")

            print("\n")

        print("All content successfully relinked :)")
