# -*- coding: utf-8 -*-
# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
@stringfilter
def make_jquery_safe(value):
    chars = "!()<>=$%&^!@+*#?~|'\\;`"
    for char in chars:
        value = mark_safe(value.replace(char, "\\\\%s" % char))
    return value
