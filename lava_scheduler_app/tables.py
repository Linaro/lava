# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import random

import django_tables2 as tables
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.timesince import timesince

from lava_scheduler_app.models import Device, DeviceType, TestJob, Worker
from lava_server.lavatable import LavaTable

# The query_set is based in the view, so split that into a View class
# Avoid putting queryset functionality into tables.
# base new views on FiltereSingleTableView. These classes can go into
# views.py later.

# No function in this file is directly accessible via urls.py - those
# functions need to go in views.py


def pklink(record):
    pk = record.pk
    if isinstance(record, TestJob):
        if record.sub_jobs_list:
            pk = record.sub_id
    verbose_name = record._meta.verbose_name.capitalize()
    return format_html(
        '<a href="{}" title="{} summary">{}</a>',
        record.get_absolute_url(),
        verbose_name,
        pk,
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
            if current_job:
                return format_html(
                    "Running #{} {} [{}]",
                    pklink(current_job),
                    current_job.description,
                    current_job.submitter,
                )
            else:
                return "Running"
        elif record.state == Device.STATE_RESERVED:
            current_job = record.current_job()
            if current_job:
                return format_html(
                    'Reserved for {} ({}) "{}" [{}]',
                    pklink(current_job),
                    current_job.get_state_display(),
                    current_job.description,
                    current_job.submitter,
                )
            else:
                return "Reserved"
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
    id = tables.Column(
        verbose_name="Job",
        orderable=False,
        linkify=("lava.scheduler.job.detail", (tables.A("pk"),)),
    )
    end_time = tables.DateColumn(
        format=settings.DATETIME_FORMAT,
        orderable=False,
        default="",
    )
    actual_device_id = tables.Column(
        verbose_name="Device",
        orderable=False,
        linkify=("lava.scheduler.device.detail", (tables.A("actual_device_id"),)),
        default="",
    )
    error_type = tables.Column(
        accessor=tables.A("failure_metadata.error_type"),
        orderable=False,
    )
    error_msg = tables.Column(
        accessor=tables.A("failure_metadata.error_msg"),
        orderable=False,
    )

    class Meta(LavaTable.Meta):
        model = TestJob
        template_name = "lazytables.html"
        fields = ()
        sequence = ("id", "end_time", "actual_device_id", "error_type", "error_msg")


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


class DeviceHealthTable(LavaTable):
    hostname = tables.Column(
        linkify=("lava.scheduler.device.detail", (tables.A("hostname"),))
    )
    worker_host = tables.Column(
        linkify=("lava.scheduler.worker.detail", (tables.A("worker_host"),))
    )
    health_verbose = tables.Column(verbose_name="Health")
    last_report_time = tables.DateTimeColumn(
        verbose_name="Last report time", accessor="last_health_report_job__end_time"
    )
    last_health_report_job = tables.Column(
        verbose_name="Last report job",
        linkify=("lava.scheduler.job.detail", (tables.A("last_health_report_job"),)),
    )

    class Meta(LavaTable.Meta):
        sequence = [
            "hostname",
            "worker_host",
            "health_verbose",
            "last_report_time",
            "last_health_report_job",
        ]
        searches = {"hostname": "contains"}
        queries = {"device_health_query": "health"}


class DeviceTypeOverviewTable(LavaTable):
    device_type = tables.Column(
        accessor="device_type",
        verbose_name="Device type",
        linkify=("lava.scheduler.device_type.detail", (tables.A("device_type"),)),
    )
    idle = tables.Column(default="", empty_values=(0,))
    maintenance = tables.Column(default="", empty_values=(0,))
    offline = tables.Column(default="", empty_values=(0,))
    busy = tables.Column(default="", empty_values=(0,))
    queued_jobs = tables.Column(verbose_name="Queue", default="", empty_values=(0,))

    class Meta(LavaTable.Meta):
        model = Device
        fields = ()


class DeviceTable(LavaTable):
    def render_device_type(self, record):
        return pklink(record.device_type)

    def render_worker_host(self, record):
        if not record.worker_host and record.health == Device.HEALTH_RETIRED:
            return mark_safe("<i>...</i>")  # nosec - static string
        if not record.worker_host and record.health != Device.HEALTH_RETIRED:
            return mark_safe(  # nosec - static string
                '<span class="text-danger"><i>No worker</i> <span class="glyphicon glyphicon-fire"></span></span>'
            )
        if (
            record.worker_host.state == Worker.STATE_ONLINE
            and record.worker_host.health == Worker.HEALTH_ACTIVE
        ):
            return format_html(
                '<a href="{}">{}</a>',
                record.worker_host.get_absolute_url(),
                record.worker_host,
            )
        elif record.worker_host.health == Worker.HEALTH_ACTIVE:
            return format_html(
                '<a href="{}" class="text-danger">{} <span class="glyphicon glyphicon-fire"></span></a>',
                record.worker_host.get_absolute_url(),
                record.worker_host,
            )
        else:
            return format_html(
                '<a href="{}" class="text-warning">{} <span class="glyphicon glyphicon-minus-sign"></span></a>',
                record.worker_host.get_absolute_url(),
                record.worker_host,
            )

    def render_health(self, record):
        if record.health == Device.HEALTH_GOOD:
            return mark_safe(  # nosec - static string
                '<strong class="text-success">Good</strong>'
            )
        elif record.health in [Device.HEALTH_UNKNOWN, Device.HEALTH_LOOPING]:
            return format_html(
                '<span class="text-info">{}</span>', record.get_health_display()
            )
        elif record.health == Device.HEALTH_BAD:
            return mark_safe(  # nosec - static string
                '<span class="text-danger">Bad</span>'
            )
        elif record.health == Device.HEALTH_MAINTENANCE:
            return mark_safe(  # nosec - static string
                '<span class="text-warning">Maintenance</span>'
            )
        else:
            return mark_safe(  # nosec - static string
                '<span class="text-muted">Retired</span>'
            )

    def render_last_job_end_time(self, record):
        return mark_safe(f"{naturaltime(record.last_job_end_time)}")

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
    state = ExpandedStatusColumn(verbose_name="State")
    health = tables.Column(verbose_name="Health")
    last_job_end_time = tables.Column(verbose_name="Last Job", orderable=False)
    tags = TagsColumn()

    class Meta(LavaTable.Meta):
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


class WorkerTable(LavaTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_help = True

    hostname = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    """
    )
    description = tables.Column(accessor="description", verbose_name="Description")
    version = tables.Column(accessor="version", verbose_name="Version")

    def render_state(self, record):
        if record.state == Worker.STATE_ONLINE:
            return format_html(
                '<span class="glyphicon glyphicon-ok text-success"></span> {}',
                record.get_state_display(),
            )
        elif record.health == Worker.HEALTH_ACTIVE:
            return format_html(
                '<span class="glyphicon glyphicon-fire text-danger"></span> {}',
                record.get_state_display(),
            )
        else:
            return format_html(
                '<span class="glyphicon glyphicon-remove text-danger"></span> {}',
                record.get_state_display(),
            )

    def render_health(self, record):
        if record.health == Worker.HEALTH_ACTIVE:
            return format_html(
                '<span class="glyphicon glyphicon-ok text-success"></span> {}',
                record.get_health_display(),
            )
        elif record.health == Worker.HEALTH_MAINTENANCE:
            return format_html(
                '<span class="glyphicon glyphicon-wrench text-warning"></span> {}',
                record.get_health_display(),
            )
        else:
            return format_html(
                '<span class="glyphicon glyphicon-remove text-danger"></span> {}',
                record.get_health_display(),
            )

    def render_last_ping(self, record):
        return timesince(record.last_ping)

    class Meta(LavaTable.Meta):
        model = Worker
        sequence = ["hostname", "state", "health", "description"]
        exclude = ["token"]


class LogEntryTable(LavaTable):
    action_time = tables.DateColumn(format=settings.DATETIME_FORMAT)
    object_id = tables.Column(verbose_name="Name")
    change_message = tables.Column(verbose_name="Reason", empty_values=[None])
    change_message.orderable = False

    def render_change_message(self, record):
        message = record.get_change_message()
        if record.is_change():
            return mark_safe(message)
        elif record.is_addition():
            return mark_safe(
                '<span class="glyphicon glyphicon-plus text-success"></span> %s'
                % message
            )
        else:
            return mark_safe(
                '<span class="glyphicon glyphicon-remove text-danger"></span> %s'
                % message
            )

    class Meta(LavaTable.Meta):
        model = LogEntry
        template_name = "lazytables.html"
        fields = ("action_time", "object_id", "user", "change_message")
        sequence = ("action_time", "object_id", "user", "change_message")


class DeviceLogEntryTable(LogEntryTable):
    class Meta(LogEntryTable.Meta):
        sequence = ("action_time", "user", "change_message")
        exclude = ["object_id"]


class NoWorkerDeviceTable(DeviceTable):
    class Meta(LavaTable.Meta):
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


class HealthJobSummaryTable(tables.Table):
    length = 10
    Duration = tables.Column()
    Complete = tables.Column(default=0)
    Failed = tables.Column(default=0)

    class Meta(LavaTable.Meta):
        model = None


class PassingHealthTable(LavaTable):
    hostname = tables.Column(linkify=True)
    device_type = tables.Column(linkify=True)
    health = tables.Column()
    last_health_report_job = tables.Column(linkify=True)

    class Meta(LavaTable.Meta):
        exclude = ["worker_host", "last_report_time"]
        sequence = ["hostname", "device_type", "health", "last_health_report_job"]
        searches = {"hostname": "contains"}
        queries = {"device_health_query": "health"}


class RunningTable(LavaTable):
    """
    Provide the admins with some information on the activity of the instance.
    Multinode jobs reserve devices whilst still in SUBMITITED
    Except for dynamic connections, there should not be more active jobs than active
    devices of any particular DeviceType.
    """

    # deprecated: dynamic connections are TestJob without a device

    name = tables.Column(
        linkify=True,
        verbose_name="Device name",
    )

    reserved_devices = tables.Column(
        orderable=False, verbose_name="Reserved", default=""
    )
    running_devices = tables.Column(orderable=False, verbose_name="Running", default="")
    running_jobs = tables.Column(orderable=False, verbose_name="Jobs", default="")
    health_frequency = tables.Column()
    health_denominator = tables.Column()

    class Meta(LavaTable.Meta):
        model = DeviceType
        fields = ()
        sequence = (
            "name",
            "reserved_devices",
            "running_devices",
            "running_jobs",
            "health_frequency",
            "health_denominator",
        )
