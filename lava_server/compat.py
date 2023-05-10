# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import rest_framework_filters as filters
from django_tables2.paginators import LazyPaginator

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


FilterBackend = RestFrameworkFilterBackend


class NoMarkupFilterBackend(FilterBackend):
    def to_html(self, request, queryset, view):
        # In order to prevent a huge performance issue when rendering the
        # browsable API, do not render the choice fields.
        return ""


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
