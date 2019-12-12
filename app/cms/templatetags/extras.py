import os
from django import template

register = template.Library()


@register.filter(name='format_date')
def format_date(date, format_string):
    if date:
        return date.strftime(format_string)
    else:
        return ''


@register.filter(name='get_basename')
def get_basename(file_path):
    if file_path:
        return os.path.basename(file_path)
    else:
        return ''