# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from django.contrib.auth.models import Group
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from rest_framework import serializers, viewsets
from rest_framework.pagination import CursorPagination

from lava_results_app.models import TestCase
from lava_scheduler_app.models import JobFailureTag, Tag, TestJob
from lava_server.dbutils import YamlField


class TestJobSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    sub_id = serializers.CharField(read_only=True)
    is_public = serializers.BooleanField(read_only=True)
    target_group = serializers.CharField(read_only=True)
    submitter = serializers.CharField(read_only=True, source="submitter.username")
    viewing_groups = serializers.ListField(
        child=serializers.CharField(read_only=True),
        read_only=True,
        source="_viewing_groups_names",
    )
    description = serializers.CharField(read_only=True)
    health_check = serializers.BooleanField(read_only=True)
    requested_device_type_id = serializers.CharField(read_only=True)
    tags = serializers.ListField(
        child=serializers.CharField(read_only=True),
        read_only=True,
        source="_tags_names",
    )
    actual_device_id = serializers.CharField(read_only=True)
    submit_time = serializers.DateTimeField(read_only=True)
    start_time = serializers.DateTimeField(read_only=True)
    end_time = serializers.DateTimeField(read_only=True)
    health = serializers.CharField(read_only=True, source="get_health_display")
    state = serializers.CharField(read_only=True, source="get_state_display")
    priority = serializers.IntegerField(read_only=True)
    definition = serializers.CharField(read_only=True)
    original_definition = serializers.CharField(read_only=True)
    multinode_definition = serializers.CharField(read_only=True)
    pipeline_compatibility = serializers.IntegerField(read_only=True)
    queue_timeout = serializers.IntegerField(read_only=True)
    failure_tags = serializers.ListField(
        child=serializers.CharField(read_only=True),
        read_only=True,
        source="_failure_tags_names",
    )
    failure_comment = serializers.CharField(read_only=True)
    error_msg = serializers.CharField(
        read_only=True,
        source="_job_testcase_metadata.error_msg",
        default=None,
    )
    error_type = serializers.CharField(
        read_only=True,
        source="_job_testcase_metadata.error_type",
        default=None,
    )


class TestJobPaginator(CursorPagination):
    page_size_query_param = "page_size"
    max_page_size = 1000


class TestJobViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = TestJobSerializer
    pagination_class = TestJobPaginator
    queryset = TestJob.objects.all()

    ordering_fields = ("id", "submit_time")
    ordering = ("-id",)

    def get_queryset(self):
        return (
            self.queryset.select_related("submitter")
            .visible_by_user(self.request.user)
            .annotate(
                _job_testcase_metadata=Subquery(
                    TestCase.objects.filter(
                        suite__job=OuterRef("pk"),
                        suite__name="lava",
                        name="job",
                    )
                    .annotate(dummy_group_by=Value(1))  # Disable GROUP BY
                    .values("dummy_group_by")
                    .values("metadata"),
                    output_field=YamlField(),
                ),
                _viewing_groups_names=Coalesce(
                    Subquery(
                        Group.objects.filter(viewing_groups=OuterRef("pk"))
                        .annotate(dummy_group_by=Value(1))  # Disable GROUP BY
                        .values("dummy_group_by")
                        .annotate(_group_names=ArrayAgg(F("name")))
                        .values("_group_names")
                    ),
                    Value([]),
                ),
                _tags_names=Coalesce(
                    Subquery(
                        Tag.objects.filter(testjob=OuterRef("pk"))
                        .annotate(dummy_group_by=Value(1))  # Disable GROUP BY
                        .values("dummy_group_by")
                        .annotate(_tag_names=ArrayAgg(F("name")))
                        .values("_tag_names")
                    ),
                    Value([]),
                ),
                _failure_tags_names=Coalesce(
                    Subquery(
                        JobFailureTag.objects.filter(failure_tags=OuterRef("pk"))
                        .annotate(dummy_group_by=Value(1))  # Disable GROUP BY
                        .values("dummy_group_by")
                        .annotate(_failure_tag_names=ArrayAgg(F("name")))
                        .values("_failure_tag_names")
                    ),
                    Value([]),
                ),
            )
        )
