# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib

from django import template
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
    if "search" in data:
        return data["search"]
    return data


@register.filter
def get_terms_data(data, prefix):
    if not data:
        return []
    if prefix in data:
        return data[prefix].values()
    if "terms" in data:
        return data["terms"].values()
    return data


@register.filter
def get_discrete_data(data, prefix):
    if not data:
        return []
    if prefix in data:
        return data[prefix]
    if "discrete" in data:
        return data["discrete"]
    return data


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
