"""
IIIF Image API passthrough to Cantaloupe.

Requests under /iiif/2/ are handed to Cantaloupe through nginx's internal /media/ location
via X-Accel-Redirect. Two callers share the parsing here so they cannot disagree about what
a request names:

- OpenAccessIIIFFastPath, an ASGI middleware in front of Django, answers requests for open
  access corpora on its own -- the bulk of tile traffic -- since those need no session.
- manager.views.iiif_passthrough handles everything else, including the access check for
  corpora that are not open access.
"""
import re
import mimetypes
import redis
import redis.asyncio
from dataclasses import dataclass
from urllib.parse import quote
from django.conf import settings


IIIF_PREFIX = '/iiif/2/'

# The key get_open_access_corpora (manager.utilities) caches the open access list under, as
# comma-delimited corpus ids. That function is the only writer; the fast path only reads it.
OPEN_ACCESS_CACHE_KEY = '/open_access_corpora'


@dataclass
class IIIFRequest:
    corpus_id: str
    x_accel_redirect: str
    content_type: str | None


def parse_iiif_request(req_path):
    """
    Parses the part of an IIIF Image API URL after /iiif/2/, already percent-decoded.

    Returns an IIIFRequest, or None when the path doesn't name a file under
    corpora/<corpus_id>/. That containment is the whole basis of the access check, so the
    path is normalized before it is tested:

    - The file path arrives in more than one form: with real slashes, with Cantaloupe's $!$
      slash substitute (the form info.json's @id uses, which viewers build tile URLs from),
      or a mix, and content-table thumbnails add a leading slash. It is split on both, so
      the corpus id is read off the same path Cantaloupe resolves.
    - '..', '.' and empty segments are refused outright: the corpus id comes off the front
      of the path, so corpora/<open access id>/../<private id>/... would otherwise pass as
      the former.
    """
    req_path_parts = req_path.split('/')
    if req_path.endswith('/info.json'):
        file_parts, iiif_params = req_path_parts[:-1], req_path_parts[-1:]
    else:
        # region/size/rotation/quality.format
        file_parts, iiif_params = req_path_parts[:-4], req_path_parts[-4:]

    path_segments = [segment for part in file_parts for segment in part.split('$!$')]
    while path_segments and path_segments[0] == '':
        path_segments.pop(0)

    if len(path_segments) < 3 or \
            path_segments[0] != 'corpora' or \
            not re.fullmatch(r'[0-9a-f]{24}', path_segments[1]) or \
            any(segment in ('', '.', '..') for segment in path_segments):
        return None

    if iiif_params == ['info.json']:
        content_type = 'application/json'
    else:
        content_type, encoding = mimetypes.guess_type("/".join(path_segments))

    return IIIFRequest(
        corpus_id=path_segments[1],
        x_accel_redirect=media_redirect(path_segments, iiif_params),
        content_type=content_type,
    )


def media_redirect(path_segments, iiif_params):
    """
    The X-Accel-Redirect value that hands a request to Cantaloupe through nginx's internal
    /media/ location, for a file path (as segments, decoded) and the IIIF parameters that
    follow the identifier: ['info.json'], or region, size, rotation and quality.format.

    Every piece is percent-encoded, and the identifier's segments are joined by Cantaloupe's
    $!$ slash substitute. That keeps the header plain ASCII: Django RFC 2047-encodes any
    non-latin-1 header value, and a raw space would pass straight into Cantaloupe's request
    line. nginx unescapes the header and re-escapes the URI on the way upstream, because
    /media/ is a prefix location with a variable-free proxy_pass -- see the note on that
    block in corpora.conf.
    """
    iiif_identifier = "$!$".join(quote(segment, safe='') for segment in path_segments)
    iiif_params = "/".join(quote(param, safe='') for param in iiif_params)
    return f"/media/{iiif_identifier}/{iiif_params}"


class OpenAccessIIIFFastPath:
    """
    ASGI middleware that answers IIIF requests for open access corpora without entering
    Django, and passes every other request through to the wrapped application unchanged.

    Under Daphne, Django costs ~3ms of per-request overhead before a view runs: every
    request gets its own thread-sensitive executor, async views included. A viewer fetching
    tiles makes many such requests at once. An open access corpus needs no session or scholar, so its requests
    are answered here with one async Redis read; nginx then serves the file from Cantaloupe,
    whose response headers are the only ones the client sees.

    Anything it can't positively answer falls through to Django: a path parse_iiif_request
    rejects (the view raises the 404), a corpus that isn't open access (the view runs the
    access check), and a missing or unreadable open access list (the view rebuilds it).
    """

    def __init__(self, app):
        self.app = app
        # the same host get_open_access_corpora writes the key to; redis.asyncio connects
        # lazily, on the event loop of first use
        self.cache = redis.asyncio.Redis(host=settings.REDIS_HOST, decode_responses=True)

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and \
                scope['method'] in ('GET', 'HEAD') and \
                scope['path'].startswith(IIIF_PREFIX):

            iiif_request = parse_iiif_request(scope['path'][len(IIIF_PREFIX):])
            if iiif_request and await self.is_open_access(iiif_request.corpus_id):
                headers = [(b'x-accel-redirect', iiif_request.x_accel_redirect.encode('ascii'))]
                if iiif_request.content_type:
                    headers.append((b'content-type', iiif_request.content_type.encode('ascii')))

                await send({'type': 'http.response.start', 'status': 200, 'headers': headers})
                await send({'type': 'http.response.body', 'body': b''})
                return

        await self.app(scope, receive, send)

    async def is_open_access(self, corpus_id):
        try:
            open_access_corpora = await self.cache.get(OPEN_ACCESS_CACHE_KEY)
        except redis.RedisError:
            return False
        return bool(open_access_corpora) and corpus_id in open_access_corpora.split(',')
