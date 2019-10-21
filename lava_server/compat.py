# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from django.utils.version import get_version
from django.core.management.base import CommandParser
import rest_framework_filters as filters


DJANGO_VERSION = get_version()


# Handles compatibility for django_restframework_filters
try:
    from rest_framework_filters.backends import RestFrameworkFilterBackend  # noqa

    # RelatedFilter argument "name" as been renamed "field_name"
    def RelatedFilter(cls, name, queryset):
        return filters.RelatedFilter(cls, field_name=name, queryset=queryset)


except ImportError:
    from rest_framework_filters.backends import (
        DjangoFilterBackend as RestFrameworkFilterBackend,
    )  # noqa

    # Keep the original version
    def RelatedFilter(cls, name, queryset):
        return filters.RelatedFilter(cls, name=name, queryset=queryset)


FilterBackend = RestFrameworkFilterBackend


class NoMarkupFilterBackend(FilterBackend):
    def to_html(self, request, queryset, view):
        # In order to prevent a huge performance issue when rendering the
        # browsable API, do not render the choice fields.
        return ""


def add_permissions(default_in_django2, local):
    if DJANGO_VERSION >= "2":
        return local
    else:
        return default_in_django2 + local


def get_sub_parser_class(cmd):
    class SubParser(CommandParser):
        """
        Sub-parsers constructor that mimic Django constructor.
        See http://stackoverflow.com/a/37414551
        """

        def __init__(self, **kwargs):
            if DJANGO_VERSION >= "2":
                super().__init__(**kwargs)
            else:
                super().__init__(cmd, **kwargs)

    return SubParser
