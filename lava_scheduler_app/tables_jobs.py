# Copyright (C) 2023 Linaro Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import django_tables2 as tables
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_scheduler_app.models import Device, TestJob
from lava_scheduler_app.tables import TagsColumn
from lava_server.lavatable import LavaTable


class BaseJobTable(LavaTable):
    id = tables.Column(
        verbose_name="ID", linkify=("lava.scheduler.job.detail", (tables.A("pk"),))
    )
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html"
    )
    actions.orderable = False
    submit_time = tables.DateColumn(format="Nd, g:ia")

    class Meta(LavaTable.Meta):
        model = TestJob
        template_name = "lazytables.html"
        fields = ()


class JobStateColumnMixin(LavaTable):
    state = tables.Column()
    state.orderable = False

    def render_state(self, record):
        if record.state == TestJob.STATE_RUNNING:
            return format_html(
                '<span class="text-info"><strong>{}</strong></span>',
                record.get_state_display(),
            )
        elif record.state == TestJob.STATE_FINISHED:
            if record.health == TestJob.HEALTH_UNKNOWN:
                text = "text-default"
            elif record.health == TestJob.HEALTH_COMPLETE:
                text = "text-success"
            elif record.health == TestJob.HEALTH_INCOMPLETE:
                text = "text-danger"
            elif record.health == TestJob.HEALTH_CANCELED:
                text = "text-warning"
            return format_html(
                '<span class="{}"><strong>{}</strong></span>',
                text,
                record.get_health_display(),
            )
        else:
            return format_html(
                '<span class="text-muted"><strong>{}</strong></span>',
                record.get_state_display(),
            )


class JobActualDeviceColumMixin(LavaTable):
    actual_device_id = tables.Column(
        verbose_name="Device",
    )

    def render_actual_device_id(self, record):
        if record.actual_device_id:
            retval = format_html(
                '<a href="{}" title="Device summary">{}</a>',
                reverse(
                    "lava.scheduler.device.detail", args=(record.actual_device_id,)
                ),
                record.actual_device_id,
            )
        elif record.dynamic_connection:
            return "connection"
        else:
            return "-"
        device_type = None
        if record.requested_device_type_id:
            device_type = record.requested_device_type_id
        if not device_type:
            return "Error"
        return retval


class JobRequestedDeviceTypeColumnMixin(LavaTable):
    requested_device_type_id = tables.Column(
        verbose_name="Device type",
        linkify=(
            "lava.scheduler.device_type.detail",
            (tables.A("requested_device_type_id"),),
        ),
    )


class JobDescriptionColumnMixin(LavaTable):
    description = tables.Column(
        default="",
    )


class JobSubmitterColumnMixin(LavaTable):
    submitter = tables.Column()

    def render_submitter(self, record):
        user_name = record.submitter.username
        full_name = record.submitter.get_full_name()

        if settings.SHOW_SUBMITTER_FULL_NAME and full_name:
            show_text = full_name
            hover_text = user_name
        else:
            show_text = user_name
            hover_text = full_name or user_name

        return format_html('<span title="{}">{}</span>', hover_text, show_text)


class JobEndTimeColumnMixin(LavaTable):
    end_time = tables.DateColumn(format="Nd, g:ia")


class JobDurationColumnMixin(LavaTable):
    duration = tables.Column(
        orderable=False,
    )


class JobPriorityColumnMixin(LavaTable):
    priority = tables.Column()


class JobHealthColumnMixin(LavaTable):
    health = tables.Column()

    def render_health(self, record):
        if record.health == Device.HEALTH_GOOD:
            return format_html('<strong class="text-success">Good</strong>')
        elif record.health in (Device.HEALTH_UNKNOWN, Device.HEALTH_LOOPING):
            return format_html(
                '<span class="text-info">{}</span>', record.get_health_display()
            )
        elif record.health == Device.HEALTH_BAD:
            return format_html('<span class="text-danger">Bad</span>')
        elif record.health == Device.HEALTH_MAINTENANCE:
            return format_html('<span class="text-warning">Maintenance</span>')
        else:
            return format_html('<span class="text-muted">Retired</span>')


# Table definitions


class AllJobsTable(
    BaseJobTable,
    JobStateColumnMixin,
    JobActualDeviceColumMixin,
    JobRequestedDeviceTypeColumnMixin,
    JobDescriptionColumnMixin,
    JobSubmitterColumnMixin,
    JobEndTimeColumnMixin,
    JobDurationColumnMixin,
):
    class Meta(BaseJobTable.Meta):
        sequence = (
            "id",
            "actions",
            "state",
            "actual_device_id",
            "requested_device_type_id",
            "description",
            "submitter",
            "submit_time",
            "end_time",
            "duration",
        )
        # filter view functions supporting relational mappings and returning a Q()
        queries = {
            "device_query": "device",  # active_device
            "owner_query": "submitter",  # submitter
            "job_state_query": "state",
            "requested_device_type_query": "requested_device_type",
        }
        # fields which can be searched with default __contains queries
        # note the enums cannot be searched this way.
        searches = {"id": "contains", "sub_id": "contains", "description": "contains"}
        # dedicated time-based search fields
        times = {"submit_time": "hours", "end_time": "hours"}


class ActiveJobsTable(
    BaseJobTable,
    JobStateColumnMixin,
    JobPriorityColumnMixin,
    JobActualDeviceColumMixin,
    JobRequestedDeviceTypeColumnMixin,
    JobHealthColumnMixin,
    JobDescriptionColumnMixin,
    JobSubmitterColumnMixin,
):
    class Meta(AllJobsTable.Meta):
        sequence = (
            "id",
            "actions",
            "state",
            "priority",
            "actual_device_id",
            "requested_device_type_id",
            "health",
            "description",
            "submitter",
            "submit_time",
        )


class FailedJobsTable(
    BaseJobTable,
    JobStateColumnMixin,
    JobActualDeviceColumMixin,
    JobRequestedDeviceTypeColumnMixin,
    JobDurationColumnMixin,
):
    failure_tags = TagsColumn(orderable=False)
    failure_comment = tables.Column(orderable=False, empty_values=())

    def render_failure_comment(self, record):
        if record.failure_comment:
            return record.failure_comment

        failure_metadata = record.failure_metadata
        if not failure_metadata:
            return ""

        if "error_msg" in failure_metadata:
            return yaml_safe_dump(yaml_safe_load(failure_metadata)["error_msg"])
        else:
            return ""

    class Meta(AllJobsTable.Meta):
        sequence = (
            "id",
            "actions",
            "state",
            "actual_device_id",
            "submit_time",
            "requested_device_type_id",
            "duration",
            "failure_tags",
            "failure_comment",
        )


class LongestJobsTable(
    BaseJobTable,
    JobStateColumnMixin,
    JobActualDeviceColumMixin,
    JobRequestedDeviceTypeColumnMixin,
    JobDescriptionColumnMixin,
    JobSubmitterColumnMixin,
    JobPriorityColumnMixin,
):
    start_time = tables.Column(
        orderable=False,
    )
    running = tables.Column(
        accessor="start_time",
        verbose_name="Running",
        default="",
        orderable=False,
    )

    def render_running(self, record):
        if not record.start_time:
            return ""
        return str(timezone.now() - record.start_time)

    class Meta(AllJobsTable.Meta):
        sequence = (
            "id",
            "actions",
            "state",
            "actual_device_id",
            "requested_device_type_id",
            "description",
            "submitter",
            "submit_time",
            "priority",
            "start_time",
            "running",
        )


class DeviceTypeJobsTable(
    BaseJobTable,
    JobActualDeviceColumMixin,
    JobStateColumnMixin,
    JobDescriptionColumnMixin,
    JobSubmitterColumnMixin,
    JobEndTimeColumnMixin,
    JobDurationColumnMixin,
):
    class Meta(AllJobsTable.Meta):
        sequence = (
            "id",
            "actions",
            "actual_device_id",
            "state",
            "description",
            "submitter",
            "submit_time",
            "end_time",
            "duration",
        )


class DeviceJobsTable(
    BaseJobTable,
    JobStateColumnMixin,
    JobDescriptionColumnMixin,
    JobSubmitterColumnMixin,
    JobEndTimeColumnMixin,
    JobDurationColumnMixin,
):
    class Meta(AllJobsTable.Meta):
        sequence = (
            "id",
            "actions",
            "state",
            "description",
            "submitter",
            "submit_time",
            "end_time",
            "duration",
        )


class QueuedJobsTable(
    BaseJobTable,
    JobRequestedDeviceTypeColumnMixin,
    JobDescriptionColumnMixin,
    JobSubmitterColumnMixin,
):
    in_queue = tables.TemplateColumn(
        """
    for {{ record.submit_time|timesince }}
    """,
        orderable=False,
    )

    class Meta(AllJobsTable.Meta):
        sequence = (
            "id",
            "actions",
            "requested_device_type_id",
            "description",
            "submitter",
            "submit_time",
            "in_queue",
        )
