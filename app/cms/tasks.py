import logging
import traceback
import re
import os
import glob
import json
import time
import bs4
import subprocess
from time import sleep
from django.conf import settings
from elasticsearch_dsl import Index, Mapping, analyzer, Keyword
from elasticsearch_dsl.connections import get_connection
from huey.contrib.djhuey import db_task, db_periodic_task
from huey import crontab
import cms as CMS


field_type_map = {
    'text': 'text',
    'html': 'text',
    'number': 'integer',
    'date': 'date',
    'file': 'text',
    'image': 'text',
    'link': 'text',
    'cross_reference': 'text'
}

TEI_transform_map = {
    'TEI-html': "/usr/src/TEI/Stylesheets/bin/teitohtml",
    'TEI-rdf': "/usr/src/TEI/Stylesheets/bin/teitordf",
    'TEI-text': "/usr/src/TEI/Stylesheets/bin/teitotext",
}


def _get_bash_cmd_output(cmd, cwd):
    output = ''
    command = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE
    )
    lines = command.stdout.readlines()

    for byte_line in lines:
        line = byte_line.decode("utf-8")
        output += line.strip() + '\n'

    return output


@db_task(priority=1)
def build_indexes(corpus_id, only=[]):
    indexes_to_rebuild = []

    try:
        content_types = CMS.ContentType.objects(corpus=corpus_id)

        for content_type in content_types:
            if not only or content_type.name in only:
                index_name = "corpus-{0}-{1}".format(corpus_id, content_type.name.lower())
                index = Index(index_name)
                if index.exists():
                    indexes_to_rebuild.append(content_type.name)
                    index.delete()
                    print('Deleting {0} index...'.format(index_name))
                    time.sleep(5)

                corpora_analyzer = analyzer(
                    'corpora_analyzer',
                    tokenizer='classic',
                    filter=['stop', 'lowercase', 'classic']
                )
                mapping = Mapping()
                mapping.field('_label', 'text', analyzer=corpora_analyzer, fields={'raw': Keyword()})

                for field in content_type.fields:
                    field_type = field_type_map[field.type]
                    subfields = {}

                    if field.in_lists and field_type == 'text':
                        subfields = {'raw': {'type': 'keyword'}}

                    if field.type == 'text':
                        mapping.field(field.name, field_type, analyzer=corpora_analyzer, fields=subfields)
                    else:
                        mapping.field(field.name, field_type, fields=subfields)

                index.mapping(mapping)
                index.save()

                print('Index {0} created.'.format(index_name))

        for content_type in indexes_to_rebuild:
            print('Rebuilding {0} index...'.format(index_name))

            items = CMS.ContentList(corpus_id, content_type, all=True)
            for item in items:
                item.index()

            print('Index {0} rebuilt.'.format(index_name))

    except:
        print("Error building indexes:")
        print(traceback.format_exc())


@db_task(priority=2)
def index_content(corpus_id, content_type, id, content):
    try:
        get_connection().index(
            index="corpus-{0}-{1}".format(corpus_id, content_type.lower()),
            id=id,
            body=content
        )
    except:
        print("Error indexing {0} with ID {1}:".format(content_type, id))
        print(traceback.format_exc())


@db_task(priority=3)
def update_field_stats(corpus_id, only=[]):
    try:
        content_types = CMS.ContentType.objects(corpus=corpus_id)

        for content_type in content_types:
            index_name = "corpus-{0}-{1}".format(corpus_id, content_type.name.lower())
            if not only or content_type.name in only:
                query = {
                    "size": 0,
                    "aggs": {}
                }

                agg_types = ['min', 'max', 'avg']

                for field in content_type.fields:
                    elastic_field_type = field_type_map[field.type]
                    if elastic_field_type == 'text' and field.in_lists:
                        for agg_type in agg_types:
                            query['aggs']['{0}_{1}'.format(field.name, agg_type)] = {
                                agg_type: {
                                    "script": "doc['{0}.raw'].value.toString().length()".format(field.name)
                                }
                            }
                    elif elastic_field_type != 'text':
                        for agg_type in agg_types:
                            query['aggs']['{0}_{1}'.format(field.name, agg_type)] = {
                                agg_type: {
                                    "field": field.name
                                }
                            }

                print(json.dumps(query, indent=4))

                hits = get_connection().search(
                    index=index_name,
                    doc_type=None,
                    body=query
                )

                if "aggregations" in hits:
                    field_indexes = {}
                    for index in range(0, len(content_type.fields)):
                        field_indexes[content_type.fields[index].name] = index
                        content_type.fields[index].stats = {}

                    for agg in hits['aggregations'].keys():
                        agg_parts = agg.split('_')
                        field = '_'.join(agg_parts[:-1])
                        stat = agg_parts[-1]
                        value = int(hits['aggregations'][agg]['value'])
                        content_type.fields[field_indexes[field]].stats[stat] = value

                    content_type.save()

    except:
        print("Error updating field stats for {0}:".format(content_type.name))
        print(traceback.format_exc())
        

@db_task(priority=2)
def run_xml_transforms(xml_pageset_id):
    # MAKING SURE NEWLY CREATED PAGESETS ARE AVAILABLE
    sleep(2)
    xml_pageset = CMS.XMLPageSet.objects(id=xml_pageset_id)[0]

    for page in xml_pageset.result_pages:
        page.delete()
    xml_pageset.result_pages = []

    for x in range(0, len(xml_pageset.transforms)):
        if not xml_pageset.transforms[x].ran:
            if xml_pageset.transforms[x].kind == 'custom':
                source = "/halcyon{0}".format(xml_pageset.source_path)
                dest = "/halcyon{0}".format(xml_pageset.destination_path)
                xsl = "/halcyon{0}".format(xml_pageset.transforms[x].path)
                saxon = '/usr/src/TEI/Stylesheets/lib/saxon9he.jar'

                if os.path.exists(source) and os.path.exists(dest) and os.path.exists(xsl):
                    cmd = [
                        'java', '-jar', saxon,
                        '-s:{0}'.format(source),
                        '-o:{0}'.format(dest),
                        '-xsl:{0}'.format(xsl)
                    ]
                    print(" ".join(cmd))
                    xml_pageset.transforms[x].output = _get_bash_cmd_output(cmd, source)
                    os.chdir(dest)
                    result_files = glob.glob(xml_pageset.transforms[x].result_filename_pattern)
                    for result_file in result_files:
                        result_file = os.path.abspath(os.path.join(dest, result_file))
                        if result_file.startswith(settings.MEDIA_DIR):
                            result_basename = os.path.basename(result_file)
                            result_title = re.sub(r'[^a-zA-Z0-9\\.\\-]', '_', "".join(result_basename.split('.')[:-1]))
                            result_url = result_file.replace(settings.MEDIA_DIR, settings.MEDIA_URL, 1)

                            page = CMS.Page()
                            page.title = result_title
                            page.url = xml_pageset.url_root + result_basename + '/'
                            page.show_in_nav = False

                            block = CMS.Block()
                            block.name = xml_pageset.transforms[x].name
                            block.html_only = True
                            block.template = {
                                'html': '''
<div id="{0}"></div>
                                '''.format(result_title),
                                'js': '''
<script type="application/javascript">
    $(document).ready(function() {{
        $('#{0}').load("{1}");
    }});
</script>
                                '''.format(result_title, result_url)
                            }
                            page.blocks.append(block)

                            page.template = {
                                'html': '''
<!-- BLOCK {0} HTML INCLUSION CODE /-->
{{% include 'pages{1}blocks/{0}.html' %}}
                                '''.format(
                                    xml_pageset.transforms[x].name,
                                    page.url
                                ),
                                'js': '''
<!-- BLOCK {0} JS INCLUSION CODE /-->
{{% include 'pages{1}blocks/{0}.js' %}}                                
                                '''.format(
                                    xml_pageset.transforms[x].name,
                                    page.url
                                ),
                            }

                            if xml_pageset.js_path:
                                page.template['js'] += '\n<script src="{0}"></script>'.format(xml_pageset.js_path)

                            if xml_pageset.css_path:
                                page.template['css'] = '<link href="{0}" rel="stylesheet">'.format(xml_pageset.css_path)

                            page.xml_pageset = xml_pageset.id
                            page.save(write_templates=True)
                            xml_pageset.result_pages.append(page.id)
        xml_pageset.save(run_transforms=False)

