import os
import re
import json
import redis
import traceback
from copy import deepcopy
from corpus import Corpus, ensure_connection
from bson import ObjectId, DBRef
import pymysql as mysql
from .content import REGISTRY as CONTENT_REGISTRY
from plugins.document.content import REGISTRY as DOC_REGISTRY


REGISTRY = {
    "import_images": {
        "description": "This command will setup the Cervantes Illustration corpus via MySQL given the presence of the legacy Cervantes Project databases."
    }
}

CERVANTES_DOCUMENT_FIELDS = [
      {
        "name": "translator",
        "label": "Translator",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "editor",
        "label": "Editor",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "year_desc",
        "label": "Year",
        "in_lists": True,
        "type": "text",
      },
      {
        "name": "year",
        "label": "Year (number)",
        "in_lists": False,
        "type": "number",
      },
      {
        "name": "place",
        "label": "Place",
        "in_lists": True,
        "type": "text",
      },
      {
        "name": "publisher",
        "label": "Publisher",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "language",
        "label": "Language",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "volume",
        "label": "Volume",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "edition_size",
        "label": "Size",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "illustrations",
        "label": "Illustrations",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "reference",
        "label": "Reference",
        "type": "text",
      },
      {
        "name": "description",
        "label": "Description",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "urbina_id",
        "label": "Urbina ID",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "library",
        "label": "Library",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "country",
        "label": "Country",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "category",
        "label": "Category",
        "in_lists": True,
        "type": "cross_reference",
        "cross_reference_type": "EditionCategory",
      },
      {
        "name": "digitized",
        "label": "Digitized?",
        "in_lists": False,
        "type": "text",
      },
      {
        "name": "totalil",
        "label": "Total IL",
        "in_lists": False,
        "type": "number",
      },
      {
        "name": "obsolete",
        "label": "Obsolete?",
        "in_lists": False,
        "type": "text",
      }
]


def _get_db():
    return mysql.connect(
        os.environ.get('CERVANTES_HOST'),
        os.environ.get('CERVANTES_USER'),
        os.environ.get('CERVANTES_PWD'),
        os.environ.get('CERVANTES_DB')
    )


def _get_data(db, query):
    try:
        cursor = db.cursor()
        cursor.execute(query)
        desc = cursor.description
        return [dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()]
    except:
        print(traceback.format_exc())

    return []


def _get_extract(val, pattern):
    pattern = re.compile(pattern)
    matches = pattern.findall(val)
    if matches:
        return matches[0]
    return ""


def import_images():
    cache = redis.Redis(host='redis', decode_responses=True)
    cache_key_base = '/cervantes/import_images'
    ensure_connection()

    try:
        corpus = Corpus.objects(name="The Cervantes Project")[0]
    except:
        corpus = Corpus()
        corpus.name = "The Cervantes Project"
        corpus.description = "The Editions and Illustrations of Miguel Cervantes"
        corpus.save()

        for cervantes_content_type_schema in CONTENT_REGISTRY:
            corpus.save_content_type(cervantes_content_type_schema)

        document_schema = deepcopy(DOC_REGISTRY[0])
        document_schema['fields'] += CERVANTES_DOCUMENT_FIELDS
        corpus.save_content_type(document_schema)

    db = _get_db()

    # Edition Categories
    '''
    print("Loading edition categories...")
    query = 'select * from EditionCat'
    rows = _get_data(db, query)

    for row in rows:
        edcat = corpus.get_content('EditionCategory')
        edcat.sequence = row['sequence']
        edcat.name = row['display'].replace('&nbsp;', '').strip()
        edcat.save()
        cache.set("{0}/edition_category/{1}".format(cache_key_base, row['id']), str(edcat.id))
    '''

    # Editions
    '''
    print("Loading editions...")
    query = 'select * from EDITION'
    rows = _get_data(db, query)
    for row in rows:
        ed = corpus.get_content('Document')
        ed.title = row['title']
        ed.author = row['author']
        ed.translator = row['translator']
        ed.editor = row['editor']
        ed.year_desc = row['yearDesc']
        ed.year = row['year']
        ed.place = row['place']
        ed.publisher = row['publisher']
        ed.language = row['language']
        ed.volume = row['volume']
        ed.edition_size = row['size']
        ed.illustrations = row['illustrations']
        ed.urbina_id = row['urbinaid']
        ed.library = row['library']
        ed.country = row['country']

        edition_category_id = cache.get("{0}/edition_category/{1}".format(cache_key_base, row['catId']))
        ed.category = corpus.get_content_dbref("EditionCategory", edition_category_id)

        ed.save()
        cache.set("{0}/editions/{1}".format(cache_key_base, row['id']), str(ed.id))
    '''

    # Illustrations
    print("Loading illustrations...")
    query = "select * from IMAGE WHERE part IS NULL"
    rows = _get_data(db, query)
    for row in rows:
        try:
            img = corpus.get_content('Illustration')
            iiif_image = "http://iiif.dh.tamu.edu/iiif/2/cervantes%2F{0}%2F{1}".format(
                str(row['id']),
                row['image'].strip()
            )
            img.image = iiif_image

            img.edition = corpus.get_content_dbref(
                'Document',
                cache.get(
                    "{0}/editions/{1}".format(
                        cache_key_base,
                        str(row['id'])
                    )
                )
            )

            img.illustration_number = row['illNo']
            img.illustrator = row['illustrator']
            img.engraver = row['engraver']
            img.lithographer = row['lithographer']
            img.title_caption = row['titleCap']
            img.title_supplied = row['titleSup']

            part = ""
            chapter = ""
            section = ""
            description = ""

            if row['part']:
                part = row['part'].strip()

            if row['chapter']:
                chapter = _get_extract(row['chapter'].strip(), r'([^\.]*)\.')

            if row['subject']:
                section = _get_extract(row['subject'].strip(), r'([^ ]*) ')
                description = row['subject'].strip().replace(section, '')

            location_key = "{0}-{1}-{2}".format(
                part,
                chapter,
                section
            )

            cached_location_id = cache.get("{0}/locations/{1}".format(cache_key_base, location_key))
            if cached_location_id:
                img.location = corpus.get_content_dbref('DQLocation', cached_location_id)
            else:
                locations = corpus.get_content('DQLocation', {
                    'part': part,
                    'chapter': chapter,
                    'section': section
                })
                if locations and locations.count() == 1:
                    img.location = locations[0].to_dbref()
                    cache.set("{0}/locations/{1}".format(cache_key_base, location_key), str(locations[0].id))
                else:
                    location = corpus.get_content('DQLocation')
                    location.part = part
                    location.chapter = chapter
                    location.section = section
                    location.description = description
                    location.save()
                    img.location = location.to_dbref()
                    cache.set("{0}/locations/{1}".format(cache_key_base, location_key), str(location.id))

            img.illustration_type = row['type']
            img.illustration_technique = row['technique']
            img.color = row['color']
            img.page_number = row['pageNo']
            img.image_dimensions = row['imageDim']
            img.page_dimensions = row['pageDim']
            img.commentary = row['commentary']
            img.notes = row['notes']
            img.def_frozen = 'Y' if row['defFrozen'] == 1 else 'N'
            img.save()

        except:
            print("Error saving image w/ uid {0}".format(row['uid']))
            print(traceback.format_exc())
