# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib

from django import template
from django.utils.safestring import mark_safe

# django-tables2 < 2.9 used `querystring` and 2.9+ renamed it to `querystring_replace`.
# Register whichever exists as `lava_querystring` for use in LAVA templates.
from django_tables2.templatetags.django_tables2 import (
    register as _django_tables2_register,
)

try:
    from django_tables2.templatetags.django_tables2 import querystring as _querystring
except ImportError:
    from django_tables2.templatetags.django_tables2 import (
        querystring_replace as _querystring,
    )

register = template.Library()

_django_tables2_register.tag("lava_querystring", _querystring)


@register.filter
def get_prefix_length(table, string):
    name = "%s%s" % (table.prefix, "length")
    if name in string:
        return string[name]
    return table.length


@register.filter
def get_prefix_search(table, string):
    name = "%s%s" % (table.prefix, "search")
    if name in string:
        return string[name]
    return ""


@register.filter
def get_length_select(table, string):
    select = ""
    val = [10, 25, 50, 100]
    name = "%s%s" % (table.prefix, "length")
    num = table.length
    if name in string:
        with contextlib.suppress(ValueError):
            num = int(string[name])

    if num and num not in val:
        val.append(num)
        val.sort()
    for option in val:
        select += (
            "<option selected>%d</option>" % option
            if option == num
            else "<option>%d</option>" % option
        )
    return mark_safe(select)
