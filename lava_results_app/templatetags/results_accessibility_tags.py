# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
