import os
import shutil
import traceback
from mongoengine import connect
from corpus import *

corpora_db = {
    'host': 'db01.dh.tamu.edu',
    'user': 'dh_dashboard_user',
    'pwd': 'W#wmqrPP@tAw*^#.$$',
    'database': 'dh_dashboard'
}

connect(
    corpora_db['database'],
    host=corpora_db['host'],
    username=corpora_db['user'],
    password=corpora_db['pwd'],
    authentication_source=corpora_db['database']
)

docs = os.listdir('/tw')
for doc_name in docs:
    doc_path = "/tw/" + doc_name
    if os.path.isdir(doc_path) and doc_name.startswith("ECCO_"):
        path_parts = doc_name.split('_')
        ecco_num = path_parts[1]
        try:
            doc = Document("5c1c5b177e32a47d04eb6819").objects(corpus="5c1c5b177e32a47d04eb6819", kvp__ecco_no=ecco_num)[0]
        except:
            print(traceback.format_exc())
            doc = None

        if doc:
            print(doc.path)
            images = os.listdir(doc.path)
            for image in images:
                if image.lower().endswith('.tif') or image.lower().endswith('.tiff'):
                    image_path = "{0}/{1}".format(doc.path, image)
                    shutil.copy(image_path, doc_path)
