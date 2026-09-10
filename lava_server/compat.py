# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django_tables2.paginators import LazyPaginator
from rest_framework_filters.backends import RestFrameworkFilterBackend


class NoMarkupFilterBackend(RestFrameworkFilterBackend):
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
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def register_job_id_converter() -> None:
    """
    Register JobIdConverter as "job_id", once.

    Several apps route on job ids and each has to make sure the converter
    exists before its urlpatterns are built. Converters are global and
    Django 5.1 turned re-registering one into a ValueError, so the
    registration has to be idempotent.

    This lives here rather than beside JobIdConverter because lava_common
    is Django-free: lava_dispatcher imports it on workers that have no
    Django installed, and mypy checks it without Django available.
    """
    from django.urls import register_converter
    from django.urls.converters import get_converters

    from lava_common.converters import JobIdConverter

    if "job_id" in get_converters():
        return
    register_converter(JobIdConverter, "job_id")
