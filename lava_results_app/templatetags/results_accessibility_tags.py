# -*- coding: utf-8 -*-
# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Stevan Radakovic <stevan.radakovic@linaro.org>
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


register = template.Library()


@register.simple_tag
def is_accessible_by(record, user):
    try:
        return record.is_accessible_by(user)
    except (TypeError, AttributeError, IndexError):
        return False


@register.filter
def check_chart_access(record, user):
    access = True
    for query in record.queries.all():
        if not query.is_accessible_by(user):
            access = False
    return access


@register.simple_tag
def get_extra_source(record, data):
    if not data:
        return ""
    if record.id in data:
        return data[record.id]
    return ""
