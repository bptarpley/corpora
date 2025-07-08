import os
import zlib
import requests
import mongoengine
from django.conf import settings
from PIL import Image
from ..utilities import run_neo


class File(mongoengine.EmbeddedDocument):
    uri = mongoengine.StringField(blank=True)
    primary_witness = mongoengine.BooleanField()
    path = mongoengine.StringField()
    basename = mongoengine.StringField()
    extension = mongoengine.StringField()
    byte_size = mongoengine.IntField()
    description = mongoengine.StringField()
    provenance_type = mongoengine.StringField()
    provenance_id = mongoengine.StringField()
    height = mongoengine.IntField(required=False)
    width = mongoengine.IntField(required=False)
    iiif_info = mongoengine.DictField()

    @property
    def key(self):
        if not hasattr(self, '_key'):
            self._key = self.generate_key(self.path)
        return self._key

    @property
    def collection_label(self):
        if not hasattr(self, '_collection_label'):
            self._collection_label = "{0}{1} from {2} ({3})".format(
                "Primary " if self.primary_witness else "",
                self.description,
                self.provenance_type,
                self.provenance_id
            ).strip()
        return self._collection_label

    @property
    def is_image(self):
        return self.extension in settings.VALID_IMAGE_EXTENSIONS

    def _do_linking(self, content_type, content_uri):
        uri_parts = [part for part in content_uri.split('/') if part]
        if uri_parts[0] == 'corpus' and len(uri_parts) > 1:
            corpus_id = uri_parts[1]

            run_neo(
                '''
                    MATCH (n:{content_type} {{ uri: $content_uri }})
                    MERGE (f:_File {{ uri: $file_uri }})
                    SET f.path = $file_path
                    SET f.corpus_id = $corpus_id
                    SET f.is_image = $is_image
                    SET f.external = $is_external
                    MERGE (n) -[rel:hasFile]-> (f)
                '''.format(content_type=content_type),
                {
                    'content_uri': content_uri,
                    'file_uri': "{0}/file/{1}".format(content_uri, self.key),
                    'corpus_id': corpus_id,
                    'file_path': self.path,
                    'is_image': self.is_image,
                    'is_external': bool(self.iiif_info)
                }
            )

    def _unlink(self, content_uri):
        run_neo(
            '''
                MATCH (f:_File { uri: $file_uri })
                DETACH DELETE f
            ''',
            {
                'file_uri': "{0}/file/{1}".format(content_uri, self.key)
            }
        )

    @classmethod
    def process(cls, path, desc=None, prov_type=None, prov_id=None, primary=False, external_iiif=False, parent_uri=''):
        file = None

        if os.path.exists(path):
            file = File()
            file.path = path
            file.primary_witness = primary
            file.basename = os.path.basename(path)
            file.extension = path.split('.')[-1].lower()
            file.byte_size = os.path.getsize(path)
            file.description = desc
            file.provenance_type = prov_type
            file.provenance_id = prov_id

            if file.extension.lower() in settings.VALID_IMAGE_EXTENSIONS:
                img = Image.open(file.path)
                file.width, file.height = img.size

        elif external_iiif:
            req = requests.get(path + '/info.json')
            if req.status_code == 200:
                iiif_info = req.json()
                if 'height' in iiif_info and 'width' in iiif_info:
                    file = File()
                    file.path = path
                    file.primary_witness = primary
                    file.basename = ''
                    file.extension = path.split('.')[-1].lower()
                    file.byte_size = 0
                    file.description = desc
                    file.provenance_type = prov_type
                    file.provenance_id = prov_id
                    file.width = iiif_info['width']
                    file.height = iiif_info['height']
                    file.iiif_info = iiif_info

        return file

    @classmethod
    def generate_key(cls, path):
        return zlib.compress(path.encode('utf-8')).hex()

    def get_url(self, parent_uri, url_type="auto"):
        uri = "{0}/file/{1}".format(parent_uri, self.key)
        url = "/file/uri/{0}/".format(uri.replace('/', '|'))
        if (url_type == "auto" and self.is_image) or url_type == "image":
            url = "/image/uri/{0}/".format(uri.replace('/', '|'))
        return url

    @classmethod
    def from_dict(cls, file_dict):
        file = File()
        valid = True
        for attr in ['uri', 'primary_witness', 'path', 'basename', 'extension', 'byte_size',
                     'description', 'provenance_type', 'provenance_id', 'height', 'width', 'iiif_info']:
            if attr in file_dict:
                setattr(file, attr, file_dict[attr])
            else:
                valid = False
                break

        if valid:
            return file
        return None

    def to_dict(self, parent_uri):
        return {
            'uri': "{0}/file/{1}".format(parent_uri, self.key),
            'primary_witness': self.primary_witness,
            'key': self.key,
            'path': self.path,
            'basename': self.basename,
            'extension': self.extension,
            'byte_size': self.byte_size,
            'description': self.description,
            'provenance_type': self.provenance_type,
            'provenance_id': self.provenance_id,
            'height': self.height,
            'width': self.width,
            'is_image': self.is_image,
            'iiif_info': self.iiif_info,
            'collection_label': self.collection_label
        }