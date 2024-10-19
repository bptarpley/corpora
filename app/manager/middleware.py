from django.conf import settings

class SiteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        host_conf = settings.CORPORA_SITES.get(host, None)
        if host_conf:
            request.urlconf = host_conf['url_conf']
            setattr(request, 'corpus_id', host_conf['corpus_id'])
        response = self.get_response(request)
        return response

class ChunkedTransferMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'CONTENT_TYPE' in request.headers and request.headers['CONTENT_TYPE'] == 'application%2Foffset%2Boctet-stream':
            request.META['CONTENT_TYPE'] = 'application/offset+octet-stream'

        response = self.get_response(request)
        return response
