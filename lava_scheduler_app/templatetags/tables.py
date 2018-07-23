# -*- coding: utf-8 -*-
# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

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
    if 'search' in data:
        return data['search']
    return data


@register.filter
def get_terms_data(data, prefix):
    if not data:
        return []
    if prefix in data:
        return data[prefix].values()
    if 'terms' in data:
        return data['terms'].values()
    return data


@register.filter
def get_discrete_data(data, prefix):
    if not data:
        return []
    if prefix in data:
        return data[prefix]
    if 'discrete' in data:
        return data['discrete']
    return data


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
