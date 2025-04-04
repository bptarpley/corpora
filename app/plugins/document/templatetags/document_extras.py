import json
from plugins.document.content import PageNavigator
from django import template

register = template.Library()


@register.filter(name='get_static_file_path')
def get_static_file_path(value):
    path_parts = value.split('/')
    return f"/{'/'.join(path_parts[3:])}"


@register.filter(name='get_ordered_pages')
def get_ordered_pages(value):
    return PageNavigator(value)
