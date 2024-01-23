# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from django.db.models import OuterRef, Subquery
from rest_framework import serializers, viewsets
from rest_framework.pagination import CursorPagination

from lava_results_app.models import TestCase
from lava_scheduler_app.models import TestJob
from lava_server.dbutils import YamlField


class TestJobSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    sub_id = serializers.CharField(read_only=True)
    is_public = serializers.BooleanField(read_only=True)
    target_group = serializers.CharField(read_only=True)
    submitter = serializers.CharField(read_only=True, source="submitter.username")
    description = serializers.CharField(read_only=True)
    health_check = serializers.BooleanField(read_only=True)
    requested_device_type_id = serializers.CharField(read_only=True)
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
                    ).values("metadata"),
                    output_field=YamlField(),
                )
            )
        )
