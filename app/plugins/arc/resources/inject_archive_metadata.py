import json
from corpus import *

arch_json = '/apps/corpora/plugins/arc/resources/archives.json'
arch_metas = None
with open(arch_json, 'r') as meta_in:
    arch_metas = json.load(meta_in)

corpus = get_corpus('5f60bf2cc879ea00329af449')

def check_val(val):
    if val and val != 'NULL':
        return True
    return False

for arch_meta in arch_metas:
    if arch_meta['handle'] != 'NULL':
        arch = None
        try:
            arch = corpus.get_content('ArcArchive', {'handle': arch_meta['handle']})[0]
        except:
            arch = None
        if arch:
            arch.name = arch_meta['name']
            arch.site_url = arch_meta['site_url']
            if check_val(arch_meta['thumbnail']):
                arch.thumbnail = arch_meta['thumbnail']
            if check_val(arch_meta['carousel_description']):
                arch.description = arch_meta['carousel_description']
            if check_val(arch_meta['parent_path']):
                arch.parent_path = arch_meta['parent_path']
            arch.save()



