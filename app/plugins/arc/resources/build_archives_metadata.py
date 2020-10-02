import json
import csv
from copy import deepcopy

archives = []
archive_id_map = {}

default_archive = {
	'id': '',
	'type': '',
	'parent_id': '',
	'handle': '',
	'name': '',
	'site_url': '',
	'thumbnail': '',
	'carousel_include': '',
	'carousel_description': '',
	'carousel_image_filename': '',
	'carousel_image_content_type': '',
	'carousel_image_file_size': '',
	'carousel_image_updated': '',
	'created_at': '',
	'updated_at': ''
}

def build_parent_path(parent_id, current_path):
	if current_path:
		current_path = '__' + current_path

	current_path = archives[archive_id_map[parent_id]]['name'] + current_path

	if archives[archive_id_map[parent_id]]['parent_id'] != '0':
		return build_parent_path(archives[archive_id_map[parent_id]]['parent_id'], current_path)

	return current_path


with open('archives.csv') as arch_in:
	arch_reader = csv.DictReader(arch_in)
	for row in arch_reader:
		archive = {}
		for field in default_archive.keys():
			archive[field] = row.get(field)
		archives.append(archive)
		archive_id_map[archive['id']] = len(archives) - 1

for arch_index in range(0, len(archives)):
	if archives[arch_index]['parent_id'] != '0':
		archives[arch_index]['parent_path'] = build_parent_path(archives[arch_index]['parent_id'], '')

with open('archives.json', 'w') as arch_out:
	json.dump(archives, arch_out, indent=4)
