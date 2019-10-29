from django import template
import json

register = template.Library()


@register.filter(name='jsonify')
def jsonify(value):
    return json.dumps(value)


@register.filter(name='get_field')
def get_field(obj, field):
    field_parts = field.split('.')
    value = obj

    for part in field_parts:
        if hasattr(obj, part):
            value = getattr(obj, part)
        elif part in value:
            value = value[part]

    return value


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
