from django.utils.html import escape
from corpus import Scholar
import traceback


def _get_context(req):
    resp = {
        'errors': [],
        'messages': [],
        'scholar': {},
        'url': req.build_absolute_uri(req.get_full_path()),
        'page': int(_clean(req.GET, 'page', 1)),
        'per_page': int(_clean(req.GET, 'per-page', 50)),
    }

    resp['start_index'] = (resp['page'] - 1) * resp['per_page']
    resp['end_index'] = resp['start_index'] + resp['per_page']

    if 'msg' in req.GET:
        resp['messages'].append(req.GET['msg'])

    if req.user.is_authenticated:
        try:
            resp['scholar'] = Scholar.objects(username=req.user.username)[0]
        except:
            print(traceback.format_exc())
            resp['scholar'] = {}

    if not resp['scholar'] and resp['url'].startswith('https'):
        if _contains(req.POST, ['username', 'token']):
            try:
                resp['scholar'] = Scholar.objects(username=_clean(req.POST, 'username'), auth_token=_clean(req.POST, 'token'))[0]
            except:
                print(traceback.format_exc())
                resp['scholar'] = {}

    return resp


def _contains(obj, keys):
    for key in keys:
        if key not in obj:
            return False
    return True


def _clean(obj, key, default_value=''):
    val = obj.get(key, False)
    if val:
        return escape(val)
    else:
        return default_value
