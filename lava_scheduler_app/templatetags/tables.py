from django import template
from django.db.models import fields
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_prefix_length(table, string):
    name = "%s%s" % (table.prefix, "length")
    if name in string:
        return string[name]
    return table.length


@register.filter
def get_search_data(data, prefix):
    if not data:
        return []
    if prefix in data:
        return data[prefix]
    if 'search' in data:
        return data['search']
    return []


@register.filter
def get_terms_data(data, prefix):
    if not data:
        return []
    if prefix in data:
        return data[prefix].values()
    if 'terms' in data:
        return data['terms'].values()
    return []


@register.filter
def get_discrete_data(data, prefix):
    if not data:
        return []
    if prefix in data:
        return data[prefix]
    if 'discrete' in data:
        return data['discrete']
    return []


@register.filter
def get_length_select(table, string):
    select = ""
    val = [10, 25, 50, 100]
    name = "%s%s" % (table.prefix, "length")
    if name in string:
        num = int(string[name])
    else:
        num = table.length
    if num and num not in val:
        val.append(num)
        val.sort()
    for option in val:
        select += "<option selected>%d</option>" % option if option == num else "<option>%d</option>" % option
    return mark_safe(select)


@register.filter
def get_health_job_toggle_select(table, string):
    select = ""
    val = ["yes", "no"]
    name = "%s%s" % (table.prefix, "includehealthcheck")
    if name in string:
        selection = string[name]
    else:
        selection = table.includehealthcheck
    for option in val:
        select += "<option selected>%s</option>" % option if option == selection else "<option>%s</option>" % option
    return mark_safe(select)
