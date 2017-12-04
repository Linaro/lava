from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter
@stringfilter
def make_jquery_safe(value):
    chars = "!()<>=$%&^!@+*#?~|'\\;`"
    for char in chars:
        value = mark_safe(value.replace(char, '\\\\%s' % char))
    return value
