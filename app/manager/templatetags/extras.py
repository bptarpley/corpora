import json
from django import template
from manager.utilities import get_field_value_from_path

register = template.Library()


@register.filter(name='jsonify')
def jsonify(value):
    return json.dumps(value)


@register.filter(name='get_field')
def get_field(obj, field):
    return get_field_value_from_path(obj, field)


@register.filter('startswith')
def startswith(obj, value):
    if isinstance(obj, str):
        return obj.startswith(value)
    return False


@register.filter(name='endswith')
def endswith(obj, value):
    if isinstance(obj, str):
        return obj.endswith(value)
    return False
