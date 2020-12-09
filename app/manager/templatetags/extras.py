import json
from django import template
from corpus import get_field_value_from_path

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


@register.filter(name='remove_str')
def remove_str(obj, value):
    if isinstance(obj, str):
        return obj.replace(value, '')
    return obj


@register.filter(name='to_int')
def to_int(obj):
    if hasattr(obj, 'isdigit') and obj.isdigit():
        return int(obj)
    return 0
