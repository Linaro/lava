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

import junit_xml
import rest_framework_filters as filters
from django_tables2.paginators import LazyPaginator
from rest_framework_extensions import __version__ as DRFE_VERSION_STR

DRFE_VERSION = [int(n) for n in DRFE_VERSION_STR.split(".")]


try:
    # pylint: disable=unused-import
    from django.urls import re_path as url  # noqa
except ImportError:
    # pylint: disable=unused-import
    from django.conf.urls import url  # noqa

# Handles compatibility for django_restframework_filters
try:
    from rest_framework_filters.backends import RestFrameworkFilterBackend  # noqa

    # RelatedFilter argument "name" as been renamed "field_name"
    def RelatedFilter(cls, name, queryset):
        return filters.RelatedFilter(cls, field_name=name, queryset=queryset)

except ImportError:
    from rest_framework_filters.backends import (  # noqa
        DjangoFilterBackend as RestFrameworkFilterBackend,
    )

    # Keep the original version
    def RelatedFilter(cls, name, queryset):
        return filters.RelatedFilter(cls, name=name, queryset=queryset)


if not getattr(junit_xml, "to_xml_report_string", None):
    junit_xml.to_xml_report_string = junit_xml.TestSuite.to_xml_string


FilterBackend = RestFrameworkFilterBackend


class NoMarkupFilterBackend(FilterBackend):
    def to_html(self, request, queryset, view):
        # In order to prevent a huge performance issue when rendering the
        # browsable API, do not render the choice fields.
        return ""


def drf_basename(name):
    """
    Handles compatibility with different versions of djangorestframework, in
    terms of the deprecation of `base_name` when registering ViewSets on DRF >=
    3.10.
    """
    if DRFE_VERSION >= [0, 6]:
        return {"basename": name}
    else:
        return {"base_name": name}


def djt2_paginator_class():
    import django_tables2

    if django_tables2.__version__ < "2.3.1":

        class FixedLazyPaginator(LazyPaginator):
            def page(self, number):
                number = self.validate_number(number or 1)
                return super().page(number)

        return {"paginator_class": FixedLazyPaginator}

    return {"paginator_class": LazyPaginator}


def is_ajax(request):
    return request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
