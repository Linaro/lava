# -*- coding: utf-8 -*-
# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import yaml
import random
from django.contrib.admin.models import LogEntry
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.timesince import timesince
import django_tables2 as tables
from lava_results_app.models import TestCase
from lava_scheduler_app.models import TestJob, Device, DeviceType, Worker
from lava_server.lavatable import LavaTable
from django.db.models import Q
from django.utils import timezone


# The query_set is based in the view, so split that into a View class
# Avoid putting queryset functionality into tables.
# base new views on FiltereSingleTableView. These classes can go into
# views.py later.

# No function in this file is directly accessible via urls.py - those
# functions need to go in views.py

# pylint: disable=invalid-name


class IDLinkColumn(tables.Column):
    def __init__(self, verbose_name="ID", **kw):
        kw["verbose_name"] = verbose_name
        super().__init__(**kw)

    def render(
        self, record, table=None
    ):  # pylint: disable=arguments-differ,unused-argument
        return pklink(record)


class RestrictedIDLinkColumn(IDLinkColumn):
    def render(self, record, table=None):
        user = table.context.get("request").user
        if record.can_view(user):
            return pklink(record)
        else:
            return record.pk


def pklink(record):
    pk = record.pk
    if isinstance(record, TestJob):
        if record.sub_jobs_list:
            pk = record.sub_id
    verbose_name = record._meta.verbose_name.capitalize()
    return mark_safe(  # nosec - internal data
        '<a href="%s" title="%s summary">%s</a>'
        % (record.get_absolute_url(), escape(verbose_name), escape(pk))
    )


class ExpandedStatusColumn(tables.Column):
    def __init__(self, verbose_name="Expanded Status", **kw):
        kw["verbose_name"] = verbose_name
        super().__init__(**kw)

    def render(self, record):
        """
        Expands the device status to include details of the job if the
        device is Reserved or Running. Logs error if reserved or running
        with no current job.
        """
        if record.state == Device.STATE_RUNNING:
            current_job = record.current_job()
            return mark_safe(  # nosec - internal data
                "Running job #%s - %s submitted by %s"
                % (pklink(current_job), current_job.description, current_job.submitter)
            )
        elif record.state == Device.STATE_RESERVED:
            current_job = record.current_job()
            return mark_safe(  # nosec - internal data
                'Reserved for job #%s (%s) "%s" submitted by %s'
                % (
                    pklink(current_job),
                    current_job.get_state_display(),
                    current_job.description,
                    current_job.submitter,
                )
            )
        elif record.state == Device.STATE_IDLE and record.health in [
            Device.HEALTH_BAD,
            Device.HEALTH_MAINTENANCE,
            Device.HEALTH_RETIRED,
        ]:
            return ""
        else:
            return record.get_simple_state_display()


def visible_jobs_with_custom_sort(user):
    jobs = TestJob.objects.visible_by_user(user)
    return jobs.order_by("-submit_time")


class JobErrorsTable(LavaTable):
    job = tables.Column(verbose_name="Job", empty_values=[""])
    job.orderable = False
    end_time = tables.DateColumn(format="Nd, g:ia")
    end_time.orderable = False
    device = tables.Column(empty_values=[""])
    device.orderable = False
    error_type = tables.Column(empty_values=[""])
    error_type.orderable = False
    error_msg = tables.Column(empty_values=[""])
    error_msg.orderable = False

    def render_end_time(self, record):
        if record.suite.job is None:
            return ""
        return record.suite.job.end_time

    def render_device(self, record):
        if record.suite.job.actual_device is None:
            return ""
        else:
            return mark_safe(  # nosec - internal data
                '<a href="%s" title="device details">%s</a>'
                % (
                    record.suite.job.actual_device.get_absolute_url(),
                    escape(record.suite.job.actual_device.hostname),
                )
            )

    def render_error_type(self, record):
        return record.action_metadata["error_type"]

    def render_error_msg(self, record):
        return record.action_metadata["error_msg"]

    def render_job(self, record):
        return mark_safe(  # nosec - internal data
            '<a href="%s">%s</a>'
            % (record.suite.job.get_absolute_url(), record.suite.job.pk)
        )

    class Meta(LavaTable.Meta):
        model = TestCase
        fields = ("job", "end_time", "device", "error_type", "error_msg")
        sequence = ("job", "end_time", "device", "error_type", "error_msg")


class JobTable(LavaTable):
    """
    Common table for the TestJob model.
    There is no need to derive from this class merely
    to change the queryset - do that in the View.
    Do inherit from JobTable if you want to add new columns
    or change the exclusion list, i.e. the structure of the
    table, not the data shown by the table.
    To preserve custom handling of fields like id, device and duration,
    ensure those are copied into the new class.
    """

    id = tables.Column(verbose_name="ID")
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html"
    )
    actions.orderable = False
    device = tables.Column(accessor="actual_device", verbose_name="Device")
    device_type = tables.Column(
        accessor="requested_device_type", verbose_name="Device type"
    )
    duration = tables.Column()
    duration.orderable = False
    submit_time = tables.DateColumn(format="Nd, g:ia")
    end_time = tables.DateColumn(format="Nd, g:ia")
    state = tables.Column()
    state.orderable = False

    def render_state(self, record):
        if record.state == TestJob.STATE_RUNNING:
            return mark_safe(  # nosec - internal data
                '<span class="text-info"><strong>%s</strong></span>'
                % record.get_state_display()
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
            return mark_safe(  # nosec - internal data
                '<span class="%s"><strong>%s</strong></span>'
                % (text, record.get_health_display())
            )
        else:
            return mark_safe(  # nosec - internal data
                '<span class="text-muted"><strong>%s</strong></span>'
                % record.get_state_display()
            )

    def render_device_type(self, record):
        if record.requested_device_type:
            return pklink(record.requested_device_type)
        return record

    def render_device(self, record):
        if record.actual_device:
            retval = pklink(record.actual_device)
        elif record.dynamic_connection:
            return "connection"
        else:
            return "-"
        device_type = None
        if record.requested_device_type:
            device_type = record.requested_device_type
        if not device_type:
            return "Error"
        return retval

    def render_description(self, value):  # pylint: disable=no-self-use
        if value:
            return value
        else:
            return ""

    class Meta(
        LavaTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = TestJob
        # alternatively, use 'fields' value to include specific fields.
        exclude = [
            "is_public",
            "sub_id",
            "target_group",
            "health_check",
            "definition",
            "original_definition",
            "multinode_definition",
            "requested_device_type",
            "start_time",
            "log_file",
            "actual_device",
            "health",
        ]
        fields = (
            "id",
            "actions",
            "state",
            "health",
            "device",
            "device_type",
            "description",
            "submitter",
            "submit_time",
            "end_time",
            "duration",
        )
        sequence = (
            "id",
            "actions",
            "state",
            "device",
            "device_type",
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


class IndexJobTable(JobTable):

    id = tables.Column(verbose_name="ID")
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html"
    )
    actions.orderable = False
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    def render_health(self, record):
        if record.health == Device.HEALTH_GOOD:
            return mark_safe(  # nosec - internal data
                '<strong class="text-success">Good</strong>'
            )
        elif record.health in [Device.HEALTH_UNKNOWN, Device.HEALTH_LOOPING]:
            return mark_safe(  # nosec - internal data
                '<span class="text-info">%s</span>' % record.get_health_display()
            )
        elif record.health == Device.HEALTH_BAD:
            return mark_safe(  # nosec - internal data
                '<span class="text-danger">Bad</span>'
            )
        elif record.health == Device.HEALTH_MAINTENANCE:
            return mark_safe(  # nosec - internal data
                '<span class="text-warning">Maintenance</span>'
            )
        else:
            return mark_safe(  # nosec - internal data
                '<span class="text-muted">Retired</span>'
            )

    class Meta(
        JobTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = (
            "id",
            "actions",
            "state",
            "health",
            "priority",
            "device",
            "device_type",
            "health",
            "description",
            "submitter",
            "submit_time",
        )
        sequence = (
            "id",
            "actions",
            "state",
            "priority",
            "device",
            "device_type",
            "health",
            "description",
            "submitter",
            "submit_time",
        )
        exclude = ("end_time", "duration")


class TagsColumn(tables.Column):
    def render(self, value):
        tag_id = "tag-%s" % "".join(
            random.choice("abcdefghijklmnopqrstuvwxyz")  # nosec - not crypto
            for _ in range(8)
        )
        tags = ""
        values = list(value.all())
        if values:
            tags = '<p class="collapse" id="%s">' % tag_id
            tags += ",<br>".join(
                '<abbr data-toggle="tooltip" title="%s">%s</abbr>'
                % (tag.description, tag.name)
                for tag in values
            )
            tags += (
                '</p><a class="btn btn-xs btn-success" data-toggle="collapse" data-target="#%s"><span class="glyphicon glyphicon-eye-open"></span></a>'
                % tag_id
            )
        return mark_safe(tags)  # nosec - internal data


class FailedJobTable(JobTable):

    id = tables.Column(verbose_name="ID")
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html"
    )
    actions.orderable = False
    device = tables.Column(accessor="actual_device")
    duration = tables.Column()
    duration.orderable = False
    failure_tags = TagsColumn()
    failure_comment = tables.Column(empty_values=())
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    def render_failure_comment(self, record):
        if record.failure_comment:
            return record.failure_comment
        try:
            failure = TestCase.objects.get(
                suite__job=record,
                result=TestCase.RESULT_FAIL,
                suite__name="lava",
                name="job",
            )
        except TestCase.DoesNotExist:
            return ""
        action_metadata = failure.action_metadata
        if action_metadata is not None and "error_msg" in action_metadata:
            return yaml.dump(failure.action_metadata["error_msg"])
        else:
            return ""

    class Meta(
        JobTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = ("id", "actions", "state", "device", "submit_time")
        sequence = ("id", "actions", "state", "device", "submit_time")
        exclude = ("submitter", "end_time", "priority", "description")


class LongestJobTable(JobTable):

    id = tables.Column(verbose_name="ID")
    id.orderable = False
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html"
    )
    actions.orderable = False
    device = tables.Column(accessor="actual_device")
    device.orderable = False
    priority = tables.Column()
    priority.orderable = False
    description = tables.Column()
    description.orderable = False
    submitter = tables.Column()
    submitter.orderable = False
    start_time = tables.Column()
    start_time.orderable = True
    submit_time = tables.Column()
    submit_time.orderable = False
    running = tables.Column(accessor="start_time", verbose_name="Running")
    running.orderable = False

    def render_running(self, record):  # pylint: disable=no-self-use
        if not record.start_time:
            return ""
        return str(timezone.now() - record.start_time)

    def render_device(self, record):  # pylint: disable=no-self-use
        if record.actual_device:
            return pklink(record.actual_device)
        return ""

    class Meta(
        JobTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = ("id", "actions", "state", "device")
        sequence = ("id", "actions", "state", "device")
        exclude = ("duration", "end_time")


class OverviewJobsTable(JobTable):

    id = tables.Column(verbose_name="ID")
    id.orderable = False
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html"
    )
    actions.orderable = False
    device = tables.Column(accessor="actual_device", verbose_name="Device")
    duration = tables.Column()
    duration.orderable = False
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    class Meta(
        JobTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = (
            "id",
            "actions",
            "device",
            "description",
            "submitter",
            "submit_time",
            "end_time",
            "duration",
        )
        sequence = ("id", "actions", "device")
        exclude = ("device_type",)


class RecentJobsTable(JobTable):

    id = tables.Column(verbose_name="ID")
    id.orderable = False
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html"
    )
    actions.orderable = False
    duration = tables.Column()
    duration.orderable = False
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    class Meta(
        JobTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = (
            "id",
            "actions",
            "description",
            "submitter",
            "submit_time",
            "end_time",
            "duration",
        )
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
        exclude = ("device", "device_type", "actual_device", "requested_device_type")


class DeviceHealthTable(LavaTable):
    def render_last_health_report_job(self, record):  # pylint: disable=no-self-use
        report = record.last_health_report_job
        if report is None:
            return ""
        else:
            return pklink(report)

    hostname = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    """
    )
    worker_host = tables.TemplateColumn(
        """
    <a href="{{ record.worker_host.get_absolute_url }}">{{ record.worker_host }}</a>
    """
    )
    health = tables.Column()
    last_report_time = tables.DateColumn(
        verbose_name="last report time", accessor="last_health_report_job.end_time"
    )
    last_health_report_job = tables.Column("last report job")

    class Meta(
        LavaTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        sequence = [
            "hostname",
            "worker_host",
            "health",
            "last_report_time",
            "last_health_report_job",
        ]
        searches = {"hostname": "contains"}
        queries = {"device_health_query": "health"}


class DeviceTypeTable(LavaTable):
    def render_idle(self, record):  # pylint: disable=no-self-use
        return record["idle"] if record["idle"] > 0 else ""

    def render_offline(self, record):  # pylint: disable=no-self-use
        return record["offline"] if record["offline"] > 0 else ""

    def render_busy(self, record):  # pylint: disable=no-self-use
        return record["busy"] if record["busy"] > 0 else ""

    def render_name(self, record):  # pylint: disable=no-self-use
        return pklink(DeviceType.objects.get(name=record["device_type"]))

    def render_queue(self, record):  # pylint: disable=no-self-use
        count = TestJob.objects.filter(
            Q(state=TestJob.STATE_SUBMITTED),
            Q(requested_device_type=record["device_type"]),
        ).count()
        return count if count > 0 else ""

    name = tables.Column(accessor="idle", verbose_name="Name")
    # the change in the aggregation breaks the accessor.
    name.orderable = False
    idle = tables.Column()
    offline = tables.Column()
    busy = tables.Column()
    # sadly, this needs to be not orderable as it would otherwise sort by the accessor.
    queue = tables.Column(accessor="idle", verbose_name="Queue", orderable=False)

    class Meta(
        LavaTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = DeviceType
        exclude = [
            "display",
            "disable_health_check",
            "architecture",
            "health_denominator",
            "health_frequency",
            "processor",
            "cpu_model",
            "bits",
            "cores",
            "core_count",
            "description",
        ]


class DeviceTable(LavaTable):
    def render_device_type(self, record):  # pylint: disable=no-self-use
        return pklink(record.device_type)

    def render_worker_host(self, record):
        if not record.worker_host and record.health == Device.HEALTH_RETIRED:
            return mark_safe("<i>...</i>")  # nosec - internal data
        if not record.worker_host and record.health != Device.HEALTH_RETIRED:
            return mark_safe(  # nosec - internal data
                '<span class="text-danger"><i>No worker</i> <span class="glyphicon glyphicon-fire"></span></span>'
            )
        if (
            record.worker_host.state == Worker.STATE_ONLINE
            and record.worker_host.health == Worker.HEALTH_ACTIVE
        ):
            return mark_safe(  # nosec - internal data
                '<a href="%s">%s</a>'
                % (record.worker_host.get_absolute_url(), record.worker_host)
            )
        elif record.worker_host.health == Worker.HEALTH_ACTIVE:
            return mark_safe(  # nosec - internal data
                '<a href="%s" class="text-danger">%s <span class="glyphicon glyphicon-fire"></span></a>'
                % (record.worker_host.get_absolute_url(), record.worker_host)
            )
        else:
            return mark_safe(  # nosec - internal data
                '<a href="%s" class="text-warning">%s <span class="glyphicon glyphicon-minus-sign"></span></a>'
                % (record.worker_host.get_absolute_url(), record.worker_host)
            )

    def render_health(self, record):
        if record.health == Device.HEALTH_GOOD:
            return mark_safe(  # nosec - internal data
                '<strong class="text-success">Good</strong>'
            )
        elif record.health in [Device.HEALTH_UNKNOWN, Device.HEALTH_LOOPING]:
            return mark_safe(  # nosec - internal data
                '<span class="text-info">%s</span>' % record.get_health_display()
            )
        elif record.health == Device.HEALTH_BAD:
            return mark_safe(  # nosec - internal data
                '<span class="text-danger">Bad</span>'
            )
        elif record.health == Device.HEALTH_MAINTENANCE:
            return mark_safe(  # nosec - internal data
                '<span class="text-warning">Maintenance</span>'
            )
        else:
            return mark_safe(  # nosec - internal data
                '<span class="text-muted">Retired</span>'
            )

    hostname = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    """
    )
    worker_host = tables.TemplateColumn(
        """
    <a href="{{ record.worker_host.get_absolute_url }}">{{ record.worker_host }}</a>
    """
    )
    device_type = tables.Column()
    state = ExpandedStatusColumn("state")
    health = tables.Column(verbose_name="Health")
    tags = TagsColumn()

    class Meta(
        LavaTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = Device
        exclude = [
            "device_version",
            "physical_owner",
            "physical_group",
            "description",
            "current_job",
            "last_health_report_job",
        ]
        sequence = ["hostname", "worker_host", "device_type", "state", "health"]
        searches = {"hostname": "contains"}
        queries = {
            "device_type_query": "device_type",
            "device_state_query": "state",
            "device_health_query": "health",
            "tags_query": "tags",
        }


class WorkerTable(LavaTable):  # pylint: disable=too-few-public-methods,no-init
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_help = True

    hostname = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    """
    )

    def render_state(self, record):
        if record.state == Worker.STATE_ONLINE:
            return mark_safe(  # nosec - internal data
                '<span class="glyphicon glyphicon-ok text-success"></span> %s'
                % record.get_state_display()
            )
        elif record.health == Worker.HEALTH_ACTIVE:
            return mark_safe(  # nosec - internal data
                '<span class="glyphicon glyphicon-fire text-danger"></span> %s'
                % record.get_state_display()
            )
        else:
            return mark_safe(  # nosec - internal data
                '<span class="glyphicon glyphicon-remove text-danger"></span> %s'
                % record.get_state_display()
            )

    def render_health(self, record):
        if record.health == Worker.HEALTH_ACTIVE:
            return mark_safe(  # nosec - internal data
                '<span class="glyphicon glyphicon-ok text-success"></span> %s'
                % record.get_health_display()
            )
        elif record.health == Worker.HEALTH_MAINTENANCE:
            return mark_safe(  # nosec - internal data
                '<span class="glyphicon glyphicon-wrench text-warning"></span> %s'
                % record.get_health_display()
            )
        else:
            return mark_safe(  # nosec - internal data
                '<span class="glyphicon glyphicon-remove text-danger"></span> %s'
                % record.get_health_display()
            )

    def render_last_ping(self, record):
        return timesince(record.last_ping)

    class Meta(
        LavaTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = Worker
        sequence = ["hostname", "state", "health", "description"]


class LogEntryTable(LavaTable):
    action_time = tables.DateColumn(format="Nd, g:ia")
    object_id = tables.Column(verbose_name="Name")
    change_message = tables.Column(verbose_name="Reason", empty_values=[None])
    change_message.orderable = False

    def render_change_message(self, record):
        message = record.get_change_message()
        if record.is_change():
            return message
        elif record.is_addition():
            return mark_safe(  # nosec - internal data
                '<span class="glyphicon glyphicon-plus text-success"></span> %s'
                % message
            )
        else:
            return mark_safe(  # nosec - internal data
                '<span class="glyphicon glyphicon-remove text-danger"></span> %s'
                % message
            )

    class Meta(LavaTable.Meta):
        model = LogEntry
        fields = ("action_time", "object_id", "user", "change_message")
        sequence = ("action_time", "object_id", "user", "change_message")


class DeviceLogEntryTable(LogEntryTable):
    class Meta(LogEntryTable.Meta):
        sequence = ("action_time", "user", "change_message")
        exclude = ["object_id"]


class NoWorkerDeviceTable(DeviceTable):
    class Meta(
        LavaTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        exclude = [
            "worker_host",
            "device_version",
            "physical_owner",
            "physical_group",
            "description",
            "last_health_report_job",
        ]
        searches = {"hostname": "contains"}
        queries = {"device_state_query": "state", "device_health_query": "health"}


class HealthJobSummaryTable(tables.Table):  # pylint: disable=too-few-public-methods

    length = 10
    Duration = tables.Column()
    Complete = tables.Column()
    Failed = tables.Column()

    class Meta(
        LavaTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = None


class QueueJobsTable(JobTable):

    id = tables.Column(verbose_name="ID")
    id.orderable = False
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html"
    )

    def render_requested_device_type(self, record):  # pylint: disable=no-self-use
        return mark_safe(  # nosec - internal data
            '<a href="%s" title="%s device_type">%s</a>'
            % (
                record.requested_device_type.get_absolute_url(),
                record.requested_device_type,
                record.requested_device_type,
            )
        )

    actions.orderable = False
    requested_device_type = tables.Column()
    in_queue = tables.TemplateColumn(
        """
    for {{ record.submit_time|timesince }}
    """
    )
    in_queue.orderable = False
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    class Meta(JobTable.Meta):
        fields = (
            "id",
            "actions",
            "requested_device_type",
            "description",
            "submitter",
            "submit_time",
            "in_queue",
        )
        sequence = (
            "id",
            "actions",
            "requested_device_type",
            "description",
            "submitter",
            "submit_time",
            "in_queue",
        )
        exclude = (
            "state",
            "health",
            "priority",
            "end_time",
            "duration",
            "device_type",
            "device",
        )


class PassingHealthTable(DeviceHealthTable):
    def render_device_type(self, record):  # pylint: disable=no-self-use
        return pklink(record.device_type)

    def render_last_health_report_job(self, record):  # pylint: disable=no-self-use
        report = record.last_health_report_job
        return mark_safe(  # nosec - internal data
            '<a href="%s">%s</a>' % (report.get_absolute_url(), report)
        )

    device_type = tables.Column()

    class Meta(
        LavaTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        exclude = ["worker_host", "last_report_time"]
        sequence = ["hostname", "device_type", "health", "last_health_report_job"]
        searches = {"hostname": "contains"}
        queries = {"device_health_query": "health"}


class RunningTable(LavaTable):
    """
    Provide the admins with some information on the activity of the instance.
    Multinode jobs reserve devices whilst still in SUBMITITED
    Except for dynamic connections, there should not be more active jobs than active devices of
    any particular DeviceType.
    """

    # deprecated: dynamic connections are TestJob without a device

    def render_jobs(self, record):  # pylint: disable=no-self-use
        count = TestJob.objects.filter(
            Q(state=TestJob.STATE_RUNNING),
            Q(requested_device_type=record.name)
            | Q(actual_device__in=Device.objects.filter(device_type=record.name)),
        ).count()
        return count if count > 0 else ""

    def render_reserved(self, record):  # pylint: disable=no-self-use
        count = Device.objects.filter(
            device_type=record.name, state=Device.STATE_RESERVED
        ).count()
        return count if count > 0 else ""

    def render_running(self, record):  # pylint: disable=no-self-use
        count = Device.objects.filter(
            device_type=record.name, state=Device.STATE_RUNNING
        ).count()
        return count if count > 0 else ""

    name = IDLinkColumn(accessor="name")

    reserved = tables.Column(
        accessor="display", orderable=False, verbose_name="Reserved"
    )
    running = tables.Column(accessor="display", orderable=False, verbose_name="Running")
    jobs = tables.Column(accessor="display", orderable=False, verbose_name="Jobs")

    class Meta(
        LavaTable.Meta
    ):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = DeviceType
        sequence = ["name", "reserved", "running", "jobs"]
        exclude = [
            "display",
            "disable_health_check",
            "architecture",
            "processor",
            "cpu_model",
            "bits",
            "cores",
            "core_count",
            "description",
        ]
