# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: GPL-2.0-or-later
"""
MetadataFilterMixin only depends on django-filter. Filtering it through a
plain django-filter FilterSet keeps it that way.
"""

import django_filters.rest_framework as drf_filters
import pytest
from django.http import QueryDict

from lava_rest_app.filters import MetadataFilterMixin
from lava_scheduler_app.models import TestJob, User


class PlainJobFilter(MetadataFilterMixin, drf_filters.FilterSet):
    class Meta:
        model = TestJob
        fields = {"id": ["exact"]}


def test_contains_lookups():
    # backends without jsonb containment, SQLite for instance, compare the
    # keys of the containment query one by one
    assert MetadataFilterMixin._contains_lookups({"build_id": "1234"}) == {
        "metadata__build_id": "1234"
    }
    assert MetadataFilterMixin._contains_lookups(
        {"branch": "main", "build": {"id": "5678"}}
    ) == {"metadata__branch": "main", "metadata__build__id": "5678"}
    assert MetadataFilterMixin._contains_lookups({"arches": ["arm64"]}) == {
        "metadata__arches": ["arm64"]
    }
    assert MetadataFilterMixin._contains_lookups({"build": {}}) == {
        "metadata__build": {}
    }


@pytest.mark.django_db
def test_metadata_filter_on_plain_filterset():
    user = User.objects.create_user("user")
    TestJob.objects.create(submitter=user, metadata={"build_id": "1234"})
    TestJob.objects.create(submitter=user, metadata={"build_id": "5678"})

    def qs(query):
        return PlainJobFilter(data=QueryDict(query), queryset=TestJob.objects.all()).qs

    assert qs("metadata__build_id=1234").count() == 1
    assert qs("metadata__build_id__startswith=12").count() == 1
    assert qs("metadata__has_key=build_id").count() == 2
    assert qs('metadata__contains={"build_id": "5678"}').count() == 1
