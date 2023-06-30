# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import contextlib
import datetime
import io
import logging
import os
import re
import tarfile
from json import dumps as json_dumps
from pathlib import Path

import voluptuous
import yaml
from django import forms
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.db import transaction
from django.db.models import Count, IntegerField, OuterRef, Prefetch, Q, Subquery
from django.db.utils import DatabaseError
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.html import escape
from django.utils.timesince import timeuntil
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django_tables2 import RequestConfig

from lava_common.log import dump
from lava_common.schemas import validate
from lava_common.version import __version__
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_results_app.dbutils import create_metadata_store, map_scanned_results
from lava_results_app.models import (
    NamedTestAttribute,
    Query,
    QueryCondition,
    TestCase,
    TestData,
)
from lava_results_app.utils import (
    check_request_auth,
    description_data,
    description_filename,
)
from lava_scheduler_app.dbutils import (
    device_summary,
    device_type_summary,
    invalid_template,
    load_devicetype_template,
    testjob_submission,
    validate_job,
)
from lava_scheduler_app.logutils import logs_instance
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    RemoteArtifactsAuth,
    Tag,
    TestJob,
    TestJobUser,
    Worker,
)
from lava_scheduler_app.signals import send_event
from lava_scheduler_app.tables import (
    DeviceHealthTable,
    DeviceLogEntryTable,
    DeviceTable,
    DeviceTypeOverviewTable,
    HealthJobSummaryTable,
    JobErrorsTable,
    LogEntryTable,
    NoWorkerDeviceTable,
    PassingHealthTable,
    RunningTable,
    WorkerTable,
    visible_jobs_with_custom_sort,
)
from lava_scheduler_app.tables_jobs import (
    ActiveJobsTable,
    AllJobsTable,
    DeviceJobsTable,
    DeviceTypeJobsTable,
    FailedJobsTable,
    LongestJobsTable,
    QueuedJobsTable,
)
from lava_scheduler_app.templatetags.utils import udecode
from lava_scheduler_app.utils import get_user_ip, is_ip_allowed
from lava_server.bread_crumbs import BreadCrumb, BreadCrumbTrail
from lava_server.compat import djt2_paginator_class, is_ajax
from lava_server.dbutils import annotate_int_field_verbose
from lava_server.files import File
from lava_server.lavatable import LavaView
from lava_server.views import index as lava_index


def request_config(request, paginate):
    return RequestConfig(request, paginate={**paginate, **djt2_paginator_class()})


# The only functions which need to go in this file are those directly
# referenced in urls.py - other support functions can go in tables.py or similar.


def _str_to_bool(string):
    return string.lower() in ["1", "true", "yes"]


class JobTableView(LavaView):
    def device_query(self, term):
        device = list(
            Device.objects.filter(hostname__contains=term).visible_by_user(
                self.request.user
            )
        )
        return Q(actual_device__in=device)

    def tags_query(self, term):
        tagnames = list(Tag.objects.filter(name__icontains=term))
        return Q(tags__in=tagnames)

    def owner_query(self, term):
        owner = list(User.objects.filter(username__contains=term))
        return Q(submitter__in=owner)

    def requested_device_type_query(self, term):
        dt = list(
            DeviceType.objects.filter(name__contains=term).visible_by_user(
                self.request.user
            )
        )
        return Q(requested_device_type__in=dt)

    def device_type_query(self, term):
        dt = list(
            DeviceType.objects.filter(name__contains=term).visible_by_user(
                self.request.user
            )
        )
        return Q(device_type__in=dt)

    def job_state_query(self, term):
        # could use .lower() but that prevents
        # matching Complete discrete from Incomplete
        matches = [p[0] for p in TestJob.STATE_CHOICES if term in p[1]]
        return Q(state__in=matches)

    def device_state_query(self, term):
        # could use .lower() but that prevents
        # matching Complete discrete from Incomplete
        matches = [p[0] for p in Device.STATE_CHOICES if term in p[1]]
        return Q(state__in=matches)

    def device_health_query(self, term):
        # could use .lower() but that prevents matching
        # Complete discrete from Incomplete
        matches = [p[0] for p in Device.HEALTH_CHOICES if term in p[1]]
        return Q(health__in=matches)


class FailedJobsTableView(JobTableView):
    def get_queryset(self):
        failures = [TestJob.HEALTH_INCOMPLETE, TestJob.HEALTH_CANCELED]
        jobs = visible_jobs_with_custom_sort(self.request.user).filter(
            health__in=failures
        )
        jobs = jobs.prefetch_related("failure_tags")

        health = self.request.GET.get("health_check")
        if health:
            jobs = jobs.filter(health_check=_str_to_bool(health))

        dt = self.request.GET.get("device_type")
        if dt:
            jobs = jobs.filter(actual_device__device_type__name=dt)

        device = self.request.GET.get("device")
        if device:
            jobs = jobs.filter(actual_device__hostname=device)

        start = self.request.GET.get("start")
        if start:
            now = timezone.now()
            start = now + datetime.timedelta(int(start))

            end = self.request.GET.get("end")
            if end:
                end = now + datetime.timedelta(int(end))
                jobs = jobs.filter(start_time__range=(start, end))

        metadata_subquery = Subquery(
            TestCase.objects.filter(
                suite__job=OuterRef("pk"),
                result=TestCase.RESULT_FAIL,
                suite__name="lava",
                name="job",
            ).values("metadata")
        )

        jobs = jobs.annotate(failure_metadata=metadata_subquery)
        return jobs


class WorkerView(JobTableView):
    def get_queryset(self):
        return Worker.objects.exclude(health=Worker.HEALTH_RETIRED).order_by("hostname")


class WorkersLogView(LavaView):
    def get_queryset(self):
        worker_ct = ContentType.objects.get_for_model(Worker)
        return (
            LogEntry.objects.filter(content_type=worker_ct)
            .order_by("-action_time")
            .select_related("user")
        )


class WorkerLogView(LavaView):
    def __init__(self, worker, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.worker = worker

    def get_queryset(self):
        worker_ct = ContentType.objects.get_for_model(Worker)
        device_ct = ContentType.objects.get_for_model(Device)
        return (
            LogEntry.objects.filter(
                (Q(content_type=worker_ct) & Q(object_id=self.worker.hostname))
                | (
                    Q(content_type=device_ct)
                    & Q(
                        object_id__in=self.worker.device_set.visible_by_user(
                            self.request.user
                        )
                    )
                )
            )
            .order_by("-action_time")
            .select_related("user")
        )


class DevicesLogView(LavaView):
    def __init__(self, devices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.devices = devices

    def get_queryset(self):
        q = LogEntry.objects.filter(object_id__in=[d.hostname for d in self.devices])
        return q.select_related("user").order_by("-action_time")


class DeviceLogView(LavaView):
    def __init__(self, device, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device = device

    def get_queryset(self):
        return (
            LogEntry.objects.filter(object_id=self.device.hostname)
            .order_by("-action_time")
            .select_related("user")
        )


class ActiveJobsTableView(JobTableView):
    def get_queryset(self):
        query = visible_jobs_with_custom_sort(self.request.user)
        query = query.filter(state__in=[TestJob.STATE_RUNNING, TestJob.STATE_CANCELING])
        return query.select_related("submitter")


class DeviceTableView(JobTableView):
    def get_queryset(self):
        q = (
            Device.objects.select_related("device_type", "worker_host")
            .prefetch_related("tags")
            .visible_by_user(self.request.user)
            .order_by("hostname")
            .distinct()
        )
        return q.prefetch_related(
            Prefetch(
                "testjobs",
                queryset=TestJob.objects.filter(
                    ~Q(state=TestJob.STATE_FINISHED)
                ).select_related("submitter"),
                to_attr="running_jobs",
            )
        )


class JobErrorsView(LavaView):
    def get_queryset(self):
        metadata_subquery = Subquery(
            TestCase.objects.filter(
                Q(metadata__contains="error_type: Configuration")
                | Q(metadata__contains="error_type: Infrastructure")
                | Q(metadata__contains="error_type: Bug"),
                suite__job=OuterRef("pk"),
                result=TestCase.RESULT_FAIL,
                suite__name="lava",
                name="job",
            ).values("metadata")[:1]
            # HACK: Add LIMIT to fix edge case
            # when job has multiple failure testcases
        )

        return (
            visible_jobs_with_custom_sort(self.request.user)
            .filter(health__in=(TestJob.HEALTH_INCOMPLETE, TestJob.HEALTH_CANCELED))
            .annotate(
                failure_metadata_str=metadata_subquery,
            )
            .filter(failure_metadata_str__isnull=False)
            .order_by("-end_time")
        )


@BreadCrumb("Scheduler", parent=lava_index)
def index(request):
    data = DeviceTypeOverView(
        request, model=DeviceType, table_class=DeviceTypeOverviewTable
    )
    ptable = DeviceTypeOverviewTable(
        data.get_table_data(), request=request, prefix="device_type_"
    )
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)

    (device_stats, running_jobs_count) = device_summary()
    return render(
        request,
        "lava_scheduler_app/index.html",
        {
            "num_online": device_stats["num_online"],
            "num_not_retired": device_stats["num_not_retired"],
            "num_jobs_running": running_jobs_count,
            "num_devices_running": device_stats["active_devices"],
            "hc_completed": device_stats["health_checks_complete"],
            "hc_total": device_stats["health_checks_total"],
            "device_type_table": ptable,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(index),
            "context_help": BreadCrumbTrail.leading_to(index),
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
        },
    )


@BreadCrumb("Workers", parent=index)
def workers(request):
    worker_data = WorkerView(request, model=Worker, table_class=WorkerTable)
    worker_ptable = WorkerTable(
        worker_data.get_table_data(), request=request, prefix="worker_"
    )
    RequestConfig(request, paginate={"per_page": worker_ptable.length}).configure(
        worker_ptable
    )

    worker_log_data = WorkersLogView(request, model=LogEntry, table_class=LogEntryTable)
    worker_log_ptable = LogEntryTable(
        worker_log_data.get_table_data(), prefix="worker_log_"
    )
    request_config(request, paginate={"per_page": worker_log_ptable.length}).configure(
        worker_log_ptable
    )

    return render(
        request,
        "lava_scheduler_app/allworkers.html",
        {
            "worker_table": worker_ptable,
            "worker_log_table": worker_log_ptable,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(workers),
        },
    )


def report_data(start_day, end_day, devices, url_param):
    now = timezone.now()
    start_date = now + datetime.timedelta(start_day)
    end_date = now + datetime.timedelta(end_day)

    res = TestJob.objects.filter(state=TestJob.STATE_FINISHED)
    res = res.filter(start_time__range=(start_date, end_date))
    if devices is not None:
        res = res.filter(actual_device__in=devices)

    res = res.values("health", "health_check")
    res = res.aggregate(
        health_pass=Count(
            "pk",
            filter=Q(health=TestJob.HEALTH_COMPLETE, health_check=True),
        ),
        job_pass=Count(
            "pk",
            filter=Q(health=TestJob.HEALTH_COMPLETE, health_check=False),
        ),
        health_fail=Count(
            "pk",
            filter=Q(
                health__in=(TestJob.HEALTH_CANCELED, TestJob.HEALTH_INCOMPLETE),
                health_check=True,
            ),
        ),
        job_fail=Count(
            "pk",
            filter=Q(
                health__in=(TestJob.HEALTH_CANCELED, TestJob.HEALTH_INCOMPLETE),
                health_check=False,
            ),
        ),
    )

    url = reverse("lava.scheduler.failure_report")
    params = "start=%s&end=%s%s" % (start_day, end_day, url_param)
    return (
        {
            "pass": res["health_pass"] or 0,
            "fail": res["health_fail"] or 0,
            "date": start_date.strftime("%m-%d"),
            "failure_url": "%s?%s&health_check=1" % (url, params),
        },
        {
            "pass": res["job_pass"] or 0,
            "fail": res["job_fail"] or 0,
            "date": start_date.strftime("%m-%d"),
            "failure_url": "%s?%s&health_check=0" % (url, params),
        },
    )


def type_report_data(start_day, end_day, dt):
    devices = Device.objects.filter(device_type=dt)
    return report_data(start_day, end_day, devices, f"&device_type={dt}")


def device_report_data(start_day, end_day, device):
    return report_data(start_day, end_day, [device], f"&device={device}")


def job_report_data(start_day, end_day):
    return report_data(start_day, end_day, None, "")


@BreadCrumb("Reports", parent=index)
def reports(request):
    health_day_report = []
    health_week_report = []
    job_day_report = []
    job_week_report = []
    for day in reversed(range(7)):
        data = job_report_data(day * -1 - 1, day * -1)
        health_day_report.append(data[0])
        job_day_report.append(data[1])

    for week in reversed(range(10)):
        data = job_report_data(week * -7 - 7, week * -7)
        health_week_report.append(data[0])
        job_week_report.append(data[1])

    return render(
        request,
        "lava_scheduler_app/reports.html",
        {
            "health_week_report": health_week_report,
            "health_day_report": health_day_report,
            "job_week_report": job_week_report,
            "job_day_report": job_day_report,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(index),
        },
    )


@BreadCrumb("Failure Report", parent=reports)
def failure_report(request):
    data = FailedJobsTableView(request)
    ptable = FailedJobsTable(data.get_table_data())
    request_config(request, {"per_page": ptable.length}).configure(ptable)

    return render(
        request,
        "lava_scheduler_app/failure_report.html",
        {
            "device_type": request.GET.get("device_type"),
            "device": request.GET.get("device"),
            "failed_job_table": ptable,
            "sort": "-submit_time",
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(failure_report),
        },
    )


@BreadCrumb("Devices", parent=index)
def device_list(request):
    data = DeviceTableView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data(), request=request)
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/alldevices.html",
        {
            "devices_table": ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(device_list),
        },
    )


@BreadCrumb("Active", parent=device_list)
def active_device_list(request):
    data = ActiveDeviceView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data(), request=request)
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/activedevices.html",
        {
            "active_devices_table": ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(active_device_list),
        },
    )


class OnlineDeviceView(DeviceTableView):
    def get_queryset(self):
        q = super().get_queryset()
        return q.filter(
            health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN],
            worker_host__state=Worker.STATE_ONLINE,
        )


@BreadCrumb("Online Devices", parent=device_list)
def online_device_list(request):
    data = OnlineDeviceView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data(), request=request)
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/onlinedevices.html",
        {
            "online_devices_table": ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(online_device_list),
        },
    )


class PassingHealthTableView(DeviceTableView):
    def get_queryset(self):
        q = super().get_queryset()
        q = q.exclude(health=Device.HEALTH_RETIRED)
        q = q.select_related(
            "last_health_report_job", "last_health_report_job__actual_device"
        )
        return q.order_by("-health", "device_type", "hostname")


@BreadCrumb("Passing Health Checks", parent=device_list)
def passing_health_checks(request):
    data = PassingHealthTableView(request, model=Device, table_class=PassingHealthTable)
    ptable = PassingHealthTable(data.get_table_data(), request=request)
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/passinghealthchecks.html",
        {
            "passing_health_checks_table": ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(passing_health_checks),
        },
    )


class MyDeviceView(DeviceTableView):
    def get_queryset(self):
        return (
            Device.objects.accessible_by_user(
                self.request.user, Device.CHANGE_PERMISSION
            )
            .select_related("device_type", "worker_host")
            .prefetch_related("tags")
            .order_by("hostname")
        )


@BreadCrumb("My Devices", parent=index)
def mydevice_list(request):
    data = MyDeviceView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data(), request=request)
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/mydevices.html",
        {
            "my_device_table": ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(mydevice_list),
        },
    )


@BreadCrumb("My Devices Health History", parent=index)
def mydevices_health_history_log(request):
    devices = Device.objects.accessible_by_user(request.user, Device.CHANGE_PERMISSION)
    devices_log_data = DevicesLogView(
        devices, request, model=LogEntry, table_class=DeviceLogEntryTable
    )
    devices_log_ptable = DeviceLogEntryTable(
        devices_log_data.get_table_data(), prefix="devices_log_"
    )
    request_config(request, paginate={"per_page": devices_log_ptable.length}).configure(
        devices_log_ptable
    )
    return render(
        request,
        "lava_scheduler_app/mydevices_health_history_log.html",
        {
            "mydeviceshealthhistory_table": devices_log_ptable,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(
                mydevices_health_history_log
            ),
        },
    )


def get_restricted_job(user, pk, request=None, for_update=False):
    """Returns JOB which is a TestJob object after checking for USER
    accessibility to the object via the UI login AND via the REST API.
    """
    try:
        job = TestJob.get_by_job_number(pk, for_update)
    except TestJob.DoesNotExist:
        raise Http404("No TestJob matches the given query.")
    # handle REST API querystring as well as UI logins
    if request:
        check_request_auth(request, job)
    return job


class ActiveDeviceView(DeviceTableView):
    def get_queryset(self):
        q = super().get_queryset()
        return q.exclude(health=Device.HEALTH_RETIRED)


class MaintenanceDeviceView(DeviceTableView):
    def get_queryset(self):
        return super().get_queryset().filter(health=Device.HEALTH_MAINTENANCE)


class DeviceHealthView(DeviceTableView):
    def get_queryset(self):
        return (
            Device.objects.visible_by_user(self.request.user)
            .order_by("hostname")
            .exclude(health=Device.HEALTH_RETIRED)
            .select_related("last_health_report_job")
            .annotate(
                health_verbose=(
                    annotate_int_field_verbose(Device._meta.get_field("health"))
                )
            )
            .values(
                "hostname",
                "worker_host",
                "health_verbose",
                "last_health_report_job__end_time",
                "last_health_report_job",
            )
        )


class DeviceTypeOverView(JobTableView):
    def get_queryset(self):
        return device_type_summary(self.request.user).annotate(
            queued_jobs=Subquery(
                TestJob.objects.filter(
                    Q(state=TestJob.STATE_SUBMITTED),
                    Q(requested_device_type=OuterRef("device_type")),
                )
                .values("requested_device_type")
                .annotate(queued_jobs=Count("pk"))
                .values("queued_jobs"),
                output_field=IntegerField(),
            ),
        )


class NoDTDeviceView(DeviceTableView):
    def get_queryset(self):
        q = (
            Device.objects.exclude(health=Device.HEALTH_RETIRED)
            .visible_by_user(self.request.user)
            .select_related("device_type", "worker_host")
            .prefetch_related("tags")
            .order_by("hostname")
        )
        return q.prefetch_related(
            Prefetch(
                "testjobs",
                queryset=TestJob.objects.filter(
                    ~Q(state=TestJob.STATE_FINISHED)
                ).select_related("submitter"),
                to_attr="running_jobs",
            )
        )


@BreadCrumb("Maintenance", parent=device_list)
def maintenance_devices(request):
    data = MaintenanceDeviceView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data(), request=request)
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/maintenance_devices.html",
        {
            "maintenance_devices_table": ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(maintenance_devices),
        },
    )


@BreadCrumb("Device Types", parent=index)
def all_device_types(request):
    data = DeviceTypeOverView(
        request, model=DeviceType, table_class=DeviceTypeOverviewTable
    )
    ptable = DeviceTypeOverviewTable(data.get_table_data(), request=request)
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)

    return render(
        request,
        "lava_scheduler_app/alldevice_types.html",
        {
            "dt_table": ptable,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(all_device_types),
        },
    )


@BreadCrumb("{pk}", parent=all_device_types, needs=["pk"])
def device_type_detail(request, pk):
    try:
        dt = DeviceType.objects.select_related("architecture", "bits", "processor").get(
            pk=pk
        )
    except DeviceType.DoesNotExist:
        raise Http404()

    if not dt.can_view(request.user):
        raise PermissionDenied()

    # Get some test job statistics
    now = timezone.now()

    (
        _,
        daily_complete,
        daily_failed,
        weekly_complete,
        weekly_failed,
        monthly_complete,
        monthly_failed,
        queued_jobs_count,
    ) = (
        DeviceType.objects.filter(pk=pk)
        .values_list("pk")
        .annotate(
            daily_complete=Subquery(
                TestJob.objects.filter(
                    requested_device_type=OuterRef("pk"),
                    health_check=True,
                    submit_time__gte=(now - datetime.timedelta(days=1)),
                    health=TestJob.HEALTH_COMPLETE,
                )
                .values("requested_device_type")
                .annotate(daily_complete=Count("pk"))
                .values("daily_complete"),
                output_field=IntegerField(),
            ),
            daily_failed=Subquery(
                TestJob.objects.filter(
                    requested_device_type=OuterRef("pk"),
                    health_check=True,
                    submit_time__gte=(now - datetime.timedelta(days=1)),
                    health__in=(TestJob.HEALTH_CANCELED, TestJob.HEALTH_INCOMPLETE),
                )
                .values("requested_device_type")
                .annotate(daily_failed=Count("pk"))
                .values("daily_failed"),
                output_field=IntegerField(),
            ),
            weekly_complete=Subquery(
                TestJob.objects.filter(
                    requested_device_type=OuterRef("pk"),
                    health_check=True,
                    submit_time__gte=(now - datetime.timedelta(days=7)),
                    health=TestJob.HEALTH_COMPLETE,
                )
                .values("requested_device_type")
                .annotate(weekly_complete=Count("pk"))
                .values("weekly_complete"),
                output_field=IntegerField(),
            ),
            weekly_failed=Subquery(
                TestJob.objects.filter(
                    requested_device_type=OuterRef("pk"),
                    health_check=True,
                    submit_time__gte=(now - datetime.timedelta(days=7)),
                    health__in=(TestJob.HEALTH_CANCELED, TestJob.HEALTH_INCOMPLETE),
                )
                .values("requested_device_type")
                .annotate(weekly_failed=Count("pk"))
                .values("weekly_failed"),
                output_field=IntegerField(),
            ),
            monthly_complete=Subquery(
                TestJob.objects.filter(
                    requested_device_type=OuterRef("pk"),
                    health_check=True,
                    submit_time__gte=(now - datetime.timedelta(days=30)),
                    health=TestJob.HEALTH_COMPLETE,
                )
                .values("requested_device_type")
                .annotate(monthly_complete=Count("pk"))
                .values("monthly_complete"),
                output_field=IntegerField(),
            ),
            monthly_failed=Subquery(
                TestJob.objects.filter(
                    requested_device_type=OuterRef("pk"),
                    health_check=True,
                    submit_time__gte=(now - datetime.timedelta(days=30)),
                    health__in=(TestJob.HEALTH_CANCELED, TestJob.HEALTH_INCOMPLETE),
                )
                .values("requested_device_type")
                .annotate(monthly_failed=Count("pk"))
                .values("monthly_failed"),
                output_field=IntegerField(),
            ),
            queued_jobs_count=Subquery(
                TestJob.objects.filter(
                    requested_device_type=OuterRef("pk"),
                    state=TestJob.STATE_SUBMITTED,
                )
                .values("requested_device_type")
                .annotate(queued_jobs_count=Count("pk"))
                .values("queued_jobs_count"),
                output_field=IntegerField(),
            ),
        )
        .first()
    )
    health_summary_data = [
        {"Duration": "24hours", "Complete": daily_complete, "Failed": daily_failed},
        {"Duration": "Week", "Complete": weekly_complete, "Failed": weekly_failed},
        {"Duration": "Month", "Complete": monthly_complete, "Failed": monthly_failed},
    ]

    prefix = "no_dt_"
    no_dt_data = NoDTDeviceView(request, model=Device, table_class=DeviceTable)
    no_dt_ptable = DeviceTable(
        no_dt_data.get_table_data(prefix).filter(device_type=dt),
        request=request,
        prefix=prefix,
    )
    config = RequestConfig(request, paginate={"per_page": no_dt_ptable.length})
    config.configure(no_dt_ptable)

    prefix = "dt_"
    dt_jobs_data = AllJobsView(request, model=TestJob, table_class=DeviceTypeJobsTable)
    dt_jobs_ptable = DeviceTypeJobsTable(
        dt_jobs_data.get_table_data(prefix).filter(requested_device_type=pk),
        prefix=prefix,
    )
    config = request_config(request, {"per_page": dt_jobs_ptable.length})
    config.configure(dt_jobs_ptable)

    prefix = "health_"
    health_table = HealthJobSummaryTable(
        health_summary_data, request=request, prefix=prefix
    )
    config = RequestConfig(request, paginate={"per_page": health_table.length})
    config.configure(health_table)

    search_data = no_dt_ptable.prepare_search_data(no_dt_data)
    search_data.update(dt_jobs_ptable.prepare_search_data(dt_jobs_data))

    terms_data = no_dt_ptable.prepare_terms_data(no_dt_data)
    terms_data.update(dt_jobs_ptable.prepare_terms_data(dt_jobs_data))

    times_data = no_dt_ptable.prepare_times_data(no_dt_data)
    times_data.update(dt_jobs_ptable.prepare_times_data(dt_jobs_data))

    discrete_data = no_dt_ptable.prepare_discrete_data(no_dt_data)
    discrete_data.update(dt_jobs_ptable.prepare_discrete_data(dt_jobs_data))

    if dt.cores.all():
        core_string = "%s x %s" % (
            dt.core_count if dt.core_count else 1,
            ",".join([core.name for core in dt.cores.all().order_by("name")]),
        )
    else:
        core_string = ""

    aliases = ", ".join([alias.name for alias in dt.aliases.order_by("name")])

    all_devices = dt.device_set.count()
    available_devices = dt.device_set.filter(
        state=Device.STATE_IDLE,
        health__in=[Device.HEALTH_UNKNOWN, Device.HEALTH_GOOD],
        worker_host__state=Worker.STATE_ONLINE,
    ).count()
    running_devices = dt.device_set.filter(
        state__in=[Device.STATE_RUNNING, Device.STATE_RESERVED]
    ).count()
    if available_devices:
        if available_devices == all_devices:
            available_devices_label = "success"
        else:
            available_devices_label = "warning"
    else:
        if running_devices:
            available_devices_label = "warning"
        else:
            available_devices_label = "danger"

    if dt.disable_health_check:
        health_freq_str = "disabled"
    elif dt.health_denominator == DeviceType.HEALTH_PER_JOB:
        health_freq_str = "one every %d jobs" % dt.health_frequency
    else:
        health_freq_str = "one every %d hours" % dt.health_frequency

    return render(
        request,
        "lava_scheduler_app/device_type.html",
        {
            "dt": dt,
            "cores": core_string,
            "aliases": aliases,
            "all_devices_count": all_devices,
            "retired_devices_count": dt.device_set.filter(
                health=Device.HEALTH_RETIRED
            ).count(),
            "available_devices_count": available_devices,
            "available_devices_label": available_devices_label,
            "running_devices_count": running_devices,
            "queued_jobs_count": queued_jobs_count or 0,
            "search_data": search_data,
            "discrete_data": discrete_data,
            "terms_data": terms_data,
            "times_data": times_data,
            "health_job_summary_table": health_table,
            "device_type_jobs_table": dt_jobs_ptable,
            "devices_table_no_dt": no_dt_ptable,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(device_type_detail, pk=pk),
            "context_help": BreadCrumbTrail.leading_to(device_type_detail, pk="help"),
            "health_freq": health_freq_str,
            "invalid_template": invalid_template(dt),
        },
    )


@BreadCrumb("Health history", parent=device_type_detail, needs=["pk"])
def device_type_health_history_log(request, pk):
    device_type = get_object_or_404(DeviceType, pk=pk)
    devices = device_type.device_set.visible_by_user(request.user)
    devices_log_data = DevicesLogView(
        devices, request, model=LogEntry, table_class=DeviceLogEntryTable
    )
    devices_log_ptable = DeviceLogEntryTable(
        devices_log_data.get_table_data(), prefix="devices_log_"
    )
    request_config(request, paginate={"per_page": devices_log_ptable.length}).configure(
        devices_log_ptable
    )

    return render(
        request,
        "lava_scheduler_app/device_type_health_history_log.html",
        {
            "device_type": device_type,
            "dthealthhistory_table": devices_log_ptable,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(
                device_type_health_history_log, pk=pk
            ),
        },
    )


@BreadCrumb("Report", parent=device_type_detail, needs=["pk"])
def device_type_reports(request, pk):
    device_type = get_object_or_404(DeviceType, pk=pk)
    if not device_type.can_view(request.user):
        raise PermissionDenied()

    health_day_report = []
    health_week_report = []
    job_day_report = []
    job_week_report = []
    for day in reversed(range(7)):
        data = type_report_data(day * -1 - 1, day * -1, device_type)
        health_day_report.append(data[0])
        job_day_report.append(data[1])

    for week in reversed(range(10)):
        data = type_report_data(week * -7 - 7, week * -7, device_type)
        health_week_report.append(data[0])
        job_week_report.append(data[1])

    long_running = (
        TestJob.objects.filter(
            actual_device__in=Device.objects.filter(device_type=device_type),
            state__in=[TestJob.STATE_RUNNING, TestJob.STATE_CANCELING],
        )
        .visible_by_user(request.user)
        .order_by("start_time")[:5]
    )
    return render(
        request,
        "lava_scheduler_app/devicetype_reports.html",
        {
            "device_type": device_type,
            "health_week_report": health_week_report,
            "health_day_report": health_day_report,
            "job_week_report": job_week_report,
            "job_day_report": job_day_report,
            "long_running": long_running,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(device_type_reports, pk=pk),
        },
    )


def device_dictionary_plain(request, pk):
    device = get_object_or_404(Device, pk=pk)
    device_configuration = device.load_configuration(output_format="yaml")
    response = HttpResponse(device_configuration, content_type="text/yaml")
    response["Content-Disposition"] = "attachment; filename=%s.yaml" % pk
    return response


@BreadCrumb("All Device Health", parent=index)
def lab_health(request):
    data = DeviceHealthView(request, model=Device, table_class=DeviceHealthTable)
    ptable = DeviceHealthTable(data.get_table_data(), request=request)
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/labhealth.html",
        {
            "device_health_table": ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(lab_health),
        },
    )


@BreadCrumb("All Health Jobs on Device {pk}", parent=index, needs=["pk"])
def health_job_list(request, pk):
    device = get_object_or_404(Device, pk=pk)

    health_data = AllJobsView(request)
    health_table = AllJobsTable(
        health_data.get_table_data().filter(actual_device=device, health_check=True),
        request=request,
    )
    config = RequestConfig(request, paginate={"per_page": health_table.length})
    config.configure(health_table)

    device_can_change = device.can_change(request.user)
    return render(
        request,
        "lava_scheduler_app/health_jobs.html",
        {
            "device": device,
            "health_job_table": health_table,
            "can_change": device_can_change,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(health_job_list, pk=pk),
        },
    )


@require_http_methods(["GET", "POST"])
@csrf_exempt
def internal_v1_jobs(request, pk):
    try:
        job = TestJob.objects.get(pk=pk)
    except TestJob.DoesNotExist:
        return JsonResponse({"error": f"Unknown job '{pk}'"}, status=404)

    token = request.META.get("HTTP_LAVA_TOKEN")
    if token is None:
        return JsonResponse({"error": "Missing 'token'"}, status=400)
    if not constant_time_compare(token, job.token):
        return JsonResponse({"error": "Invalid 'token'"}, status=400)

    if request.method == "GET":
        job_def = yaml_safe_load(job.definition)
        job_def["compatibility"] = job.pipeline_compatibility
        job_def_str_safe = yaml_safe_dump(job_def)

        tokens = {
            x["name"]: x["token"]
            for x in RemoteArtifactsAuth.objects.filter(user=job.submitter).values(
                "name", "token"
            )
        }

        def update_token(headers_dict):
            for key in headers_dict["headers"]:
                token_name = headers_dict["headers"][key]
                if token_name in tokens.keys():
                    headers_dict["headers"][key] = tokens[token_name]

        if "actions" in job_def:
            for action in job_def["actions"]:
                for k, v in action.items():
                    if k == "deploy":
                        for a, b in v.items():
                            if isinstance(b, dict):
                                if "url" in b and "headers" in b:
                                    update_token(b)
                                for i, j in b.items():
                                    if isinstance(j, dict):
                                        if "url" in j and "headers" in j:
                                            update_token(j)

        if "secrets" in job_def:
            for k, v in job_def["secrets"].items():
                if v in tokens.keys():
                    job_def["secrets"][k] = tokens[v]

        job_def_str = yaml_safe_dump(job_def)
        job_ctx = job_def.get("context", {})

        if job.dynamic_connection:
            host = job.dynamic_host()
            device = host.actual_device
            worker = device.worker_host
            host_device_cfg = device.load_configuration(job_ctx)
            device_cfg_str = yaml_safe_dump(
                device.minimise_configuration(host_device_cfg)
            )
        else:
            device = job.actual_device
            worker = device.worker_host
            device_cfg_str = device.load_configuration(job_ctx, output_format="yaml")

        def config(kind):
            try:
                data = File(kind, worker.hostname).read(raising=False)
                yaml_safe_load(data)
                return data
            except yaml.YAMLError:
                # Raise an OSError because the caller uses yaml.YAMLError for a
                # specific usage. Allows here to specify the faulty filename.
                raise OSError(
                    "", f"Invalid YAML file for {worker.hostname}: {kind} file"
                )

        env_str = config("env")
        env_dut_str = config("env-dut")
        dispatcher_cfg = config("dispatcher")

        # Save the configuration
        path = Path(job.output_dir)
        path.mkdir(mode=0o755, parents=True, exist_ok=True)
        (path / "job.yaml").write_text(job_def_str_safe, encoding="utf-8")
        (path / "device.yaml").write_text(device_cfg_str, encoding="utf-8")
        if dispatcher_cfg:
            (path / "dispatcher.yaml").write_text(dispatcher_cfg, encoding="utf-8")
        if env_str:
            (path / "env.yaml").write_text(env_str)
        if env_dut_str:
            (path / "env-dut.yaml").write_text(env_dut_str, encoding="utf-8")

        return JsonResponse(
            {
                "definition": job_def_str,
                "device": device_cfg_str,
                "dispatcher": dispatcher_cfg,
                "env": env_str,
                "env-dut": env_dut_str,
            }
        )
    else:
        # POST request
        state = request.POST.get("state", "").capitalize()
        if state not in TestJob.STATE_REVERSE:
            return JsonResponse({"error": f"Invalid state '{state}'"}, status=400)

        with transaction.atomic():
            # TODO: find a way to lock actual_device
            job = TestJob.objects.select_for_update().get(pk=pk)
            if TestJob.STATE_REVERSE[state] == TestJob.STATE_RUNNING:
                job.go_state_running()
            elif TestJob.STATE_REVERSE[state] == TestJob.STATE_FINISHED:
                # Check the result
                health = request.POST.get("result", "")
                error_type = request.POST.get("error_type", "")
                errors = request.POST.get("errors")
                description = request.POST.get("description", "")
                if health not in ["pass", "fail"]:
                    return JsonResponse(
                        {"error": f"Invalid health '{health}'"}, status=400
                    )

                health = (
                    TestJob.HEALTH_COMPLETE
                    if health == "pass"
                    else TestJob.HEALTH_INCOMPLETE
                )
                infrastructure_error = error_type in [
                    "Bug",
                    "Configuration",
                    "Infrastructure",
                ]
                job.go_state_finished(health, infrastructure_error)
                if errors:
                    job.failure_comment = errors
                Path(job.output_dir).mkdir(mode=0o755, parents=True, exist_ok=True)
                (Path(job.output_dir) / "description.yaml").write_text(
                    description, encoding="utf-8"
                )
            else:
                return JsonResponse(
                    {"error": f"Not handled state '{state}'"}, status=400
                )
            job.save()

        return JsonResponse({})


@require_POST
@csrf_exempt
def internal_v1_jobs_logs(request, pk):
    try:
        job = TestJob.objects.get(pk=pk)
    except TestJob.DoesNotExist:
        return JsonResponse({"error": f"Unknown job '{pk}'"}, status=404)

    # Check authentication
    token = request.META.get("HTTP_LAVA_TOKEN")
    if token is None:
        return JsonResponse({"error": "Missing 'token'"}, status=400)
    if not constant_time_compare(token, job.token):
        return JsonResponse({"error": "Invalid 'token'"}, status=400)

    # check data
    lines = request.POST.get("lines")
    if not lines:
        return JsonResponse({"error": "Missing 'lines'"}, status=400)
    line_idx = request.POST.get("index")
    if line_idx is None:
        return JsonResponse({"error": "Missing 'index'"}, status=400)
    try:
        # Index sent by lava-run to know if some lines are resent.
        line_idx = int(line_idx)
    except ValueError:
        return JsonResponse({"error": "Invalid 'index'"}, status=400)

    # TODO: leaky logutils abstraction
    path = Path(job.output_dir)
    path.mkdir(mode=0o755, parents=True, exist_ok=True)
    output = (path / "output.yaml").open("ab")
    index = (path / "output.idx").open("ab")
    line_skip = logs_instance.line_count(job) - line_idx

    # TODO: use a database transaction so all or none objects are saved
    # TODO: except exceptions and return the number
    #       of lines that where actually parsed !!
    test_cases = []
    line_count = 0
    for line, string in zip(yaml_safe_load(lines), lines.split("\n")):
        # skip lines that where already saved to disk
        duplicated = False
        if line_skip > 0:
            duplicated = True
            line_skip -= 1
        else:
            # Handle lava-event
            if line["lvl"] == "event":
                send_event(
                    ".event", "lavaserver", {"message": line["msg"], "job": job.id}
                )
                line["lvl"] = "debug"
                string = "- " + dump(line)

            # Save the log line
            logs_instance.write(job, (string + "\n").encode("utf-8"), output, index)

        # handle test case results
        if line["lvl"] == "results":
            starttc = endtc = None
            with contextlib.suppress(KeyError):
                starttc = line["msg"]["starttc"]
                del line["msg"]["starttc"]
            with contextlib.suppress(KeyError):
                endtc = line["msg"]["endtc"]
                del line["msg"]["endtc"]
            meta_filename = create_metadata_store(line["msg"], job)
            new_test_case = map_scanned_results(
                results=line["msg"],
                job=job,
                starttc=starttc,
                endtc=endtc,
                meta_filename=meta_filename,
            )

            if new_test_case is not None:
                # If the log lines are a resubmission of a previous failed
                # submission, count the number of TestCase that are identical
                # to the new one. This will avoid saving multiple time the same
                # TestCase
                count = 0
                if duplicated:
                    count = TestCase.objects.filter(
                        name=new_test_case.name,
                        units=new_test_case.units,
                        result=new_test_case.result,
                        measurement=new_test_case.measurement,
                        metadata=new_test_case.metadata,
                        suite=new_test_case.suite,
                        start_log_line=new_test_case.start_log_line,
                        end_log_line=new_test_case.end_log_line,
                        test_set=new_test_case.test_set,
                    ).count()
                if count == 0:
                    test_cases.append(new_test_case)
        line_count += 1

    # Save the new test cases
    try:
        TestCase.objects.bulk_create(test_cases)
    except (DatabaseError, ValueError):
        for tc in test_cases:
            with contextlib.suppress(DatabaseError, ValueError):
                tc.save()

    return JsonResponse({"line_count": line_count})


@require_http_methods(["GET", "POST"])
@csrf_exempt
def internal_v1_workers(request, pk=None):
    if request.method == "GET":
        try:
            worker = Worker.objects.get(hostname=pk)
        except Worker.DoesNotExist:
            return JsonResponse({"error": f"Unknown worker '{pk}'"}, status=404)

        token = request.META.get("HTTP_LAVA_TOKEN")
        if token is None:
            return JsonResponse({"error": "Missing 'token'"}, status=400)
        if not constant_time_compare(token, worker.token):
            return JsonResponse({"error": "Invalid 'token'"}, status=400)

        # Update the version
        version = request.GET.get("version")
        if version is None:
            return JsonResponse({"error": "Missing 'version'"}, status=400)

        # Check the version
        version_mismatch = bool(version != __version__)

        # Save worker version
        worker.version = version
        if version_mismatch and not settings.ALLOW_VERSION_MISMATCH:
            # If the version does not match, go offline
            worker.go_state_offline()
        else:
            # Set last_ping
            worker.last_ping = timezone.now()

            # Go online if needed
            if worker.state == Worker.STATE_OFFLINE:
                worker.go_state_online()
        worker.save()

        # Grab the jobs for this dispatcher
        query = TestJob.objects.filter(actual_device__worker_host=worker)

        # Scheduled
        starts = []
        if not version_mismatch or settings.ALLOW_VERSION_MISMATCH:
            start_query = query.filter(state=TestJob.STATE_SCHEDULED)
            starts = list(start_query.values("id", "token"))
            for job in start_query.filter(target_group__isnull=False):
                starts += [{"id": j.id, "token": j.token} for j in job.dynamic_jobs()]

        # Canceling
        cancel_query = query.filter(state=TestJob.STATE_CANCELING)
        cancels = list(cancel_query.values("id", "token"))
        for job in cancel_query.filter(target_group__isnull=False):
            cancels += [{"id": j.id, "token": j.token} for j in job.dynamic_jobs()]

        # Running
        running_query = query.filter(state=TestJob.STATE_RUNNING)
        runnings = list(running_query.values("id", "token"))
        for job in running_query.filter(target_group__isnull=False):
            runnings += [{"id": j.id, "token": j.token} for j in job.dynamic_jobs()]

        if (
            version_mismatch
            and not cancels
            and not runnings
            and not settings.ALLOW_VERSION_MISMATCH
        ):
            return JsonResponse(
                {"error": f"Version mismatch '{version}' vs '{__version__}'"},
                status=409,  # Conflict
            )

        # Return starting, canceling and running jobs
        return JsonResponse({"cancel": cancels, "running": runnings, "start": starts})

    else:
        if pk is not None:
            return JsonResponse({"error": "POST is forbidden for such url"}, status=403)

        if not settings.WORKER_AUTO_REGISTER:
            return JsonResponse({"error": "Auto registration is disabled"}, status=403)

        name = request.POST.get("name")
        if name is None:
            return JsonResponse({"error": "Missing 'name'"}, status=400)

        # Get username and password if available
        username = request.POST.get("username")
        password = request.POST.get("password")

        if username and password:
            user = authenticate(username=username, password=password)
            if user is None:
                return JsonResponse({"error": f"Unknown user {username}"}, status=403)

            try:
                worker = Worker.objects.get(hostname=name)
                if not user.is_superuser:
                    return JsonResponse(
                        {"error": f"Worker '{name}' already registered"}, status=403
                    )
            except Worker.DoesNotExist:
                worker = Worker.objects.create(
                    hostname=name, description=f"Auto registered by {username}"
                )
        else:
            user_ip = get_user_ip(request)
            if user_ip is None:
                return JsonResponse({"error": "Missing client ip"}, status=400)

            if not is_ip_allowed(user_ip, settings.WORKER_AUTO_REGISTER_NETMASK):
                return JsonResponse(
                    {"error": f"Auto registration is forbidden for '{user_ip}'"},
                    status=403,
                )

            with contextlib.suppress(Worker.DoesNotExist):
                worker = Worker.objects.get(hostname=name)
                return JsonResponse(
                    {"error": f"Worker '{name}' already registered"}, status=403
                )

            # TODO: ask for a specific user to give admin access to the worker
            worker = Worker.objects.create(
                hostname=name, description=f"Auto registered by {user_ip}"
            )
        return JsonResponse({"name": name, "token": worker.token})


class MyJobsView(JobTableView):
    def get_queryset(self):
        query = visible_jobs_with_custom_sort(self.request.user)
        query = query.filter(submitter=self.request.user)
        return query.select_related("submitter")


class MyActiveJobsView(JobTableView):
    def get_queryset(self):
        query = visible_jobs_with_custom_sort(self.request.user)
        query = query.filter(submitter=self.request.user).filter(
            state__in=[TestJob.STATE_RUNNING, TestJob.STATE_CANCELING]
        )
        return query.select_related("submitter")


class MyQueuedJobsView(JobTableView):
    def get_queryset(self):
        query = visible_jobs_with_custom_sort(self.request.user)
        query = query.filter(submitter=self.request.user).filter(
            state=TestJob.STATE_SUBMITTED
        )
        return query.select_related("submitter")


class MyErrorJobsView(JobTableView):
    def get_queryset(self):
        q = TestCase.objects.filter(
            suite__name="lava", result=TestCase.RESULT_FAIL
        ).visible_by_user(self.request.user)
        q = q.filter(
            Q(metadata__contains="error_type: Configuration")
            | Q(metadata__contains="error_type: Infrastructure")
            | Q(metadata__contains="error_type: Bug")
        )
        q = q.select_related("suite", "suite__job__actual_device")
        return q.order_by("-suite__job__id").filter(
            suite__job__submitter=self.request.user
        )


class LongestJobsView(JobTableView):
    def get_queryset(self):
        jobs = (
            TestJob.objects.select_related("submitter")
            .visible_by_user(self.request.user)
            .filter(state__in=[TestJob.STATE_RUNNING, TestJob.STATE_CANCELING])
        )
        return jobs.order_by("start_time")


class FavoriteJobsView(JobTableView):
    def get_queryset(self):
        user = self.user if self.user else self.request.user

        query = visible_jobs_with_custom_sort(self.request.user)
        query = query.filter(testjobuser__user=user, testjobuser__is_favorite=True)
        return query.select_related("submitter")


class AllJobsView(JobTableView):
    def get_queryset(self):
        return visible_jobs_with_custom_sort(self.request.user).select_related(
            "submitter"
        )


@BreadCrumb("Jobs", parent=index)
def job_list(request):
    data = AllJobsView(request, model=TestJob, table_class=AllJobsTable)
    ptable = AllJobsTable(data.get_table_data())
    request_config(request, {"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/alljobs.html",
        {
            "bread_crumb_trail": BreadCrumbTrail.leading_to(job_list),
            "alljobs_table": ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
    )


@BreadCrumb("Errors", parent=job_list)
def job_errors(request):
    data = JobErrorsView(request, model=TestCase, table_class=JobErrorsTable)
    ptable = JobErrorsTable(data.get_table_data(), prefix="job_errors_")
    request_config(request, {"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/job_errors.html",
        {
            "job_errors_table": ptable,
            "sort": "-submit_time",
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(job_errors),
        },
    )


@BreadCrumb("Active", parent=job_list)
def active_jobs(request):
    data = ActiveJobsTableView(request, model=TestJob, table_class=ActiveJobsTable)
    ptable = ActiveJobsTable(data.get_table_data())
    request_config(request, {"per_page": ptable.length}).configure(ptable)

    return render(
        request,
        "lava_scheduler_app/active_jobs.html",
        {
            "active_jobs_table": ptable,
            "sort": "-submit_time",
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(active_jobs),
        },
    )


@BreadCrumb("Submit", parent=job_list)
def job_submit(request):
    response_data = {
        "is_authorized": request.user.is_authenticated,
        "bread_crumb_trail": BreadCrumbTrail.leading_to(job_submit),
    }

    if request.method == "POST" and request.user.is_authenticated:
        if is_ajax(request):
            warnings = ""
            errors = ""
            try:
                validate_job(request.POST.get("definition-input"))
                try:
                    validate(
                        yaml_safe_load(request.POST.get("definition-input")),
                        extra_context_variables=settings.EXTRA_CONTEXT_VARIABLES,
                    )
                except voluptuous.Invalid as exc:
                    warnings = str(exc)
            except Exception as e:
                errors = str(e)
            return JsonResponse(
                {
                    "result": "failure" if errors else "success",
                    "errors": errors,
                    "warnings": warnings,
                }
            )

        else:
            try:
                definition_data = request.POST.get("definition-input")
                job = testjob_submission(definition_data, request.user)

                if isinstance(job, list):
                    response_data["job_list"] = [j.sub_id for j in job]
                    # Refer to first job in list for job info.
                    job = job[0]
                else:
                    response_data["job_id"] = job.id

                is_favorite = request.POST.get("is_favorite")
                if is_favorite:
                    testjob_user, _ = TestJobUser.objects.get_or_create(
                        user=request.user, test_job=job
                    )
                    testjob_user.is_favorite = True
                    testjob_user.save()

                return HttpResponseRedirect(
                    reverse("lava.scheduler.job.detail", args=[job.pk])
                )

            except Exception as e:
                response_data["error"] = str(e)
                response_data["context_help"] = "lava scheduler submit job"
                response_data["definition_input"] = request.POST.get("definition-input")
                response_data["is_favorite"] = request.POST.get("is_favorite")
                return render(
                    request, "lava_scheduler_app/job_submit.html", response_data
                )

    else:
        return render(request, "lava_scheduler_app/job_submit.html", response_data)


@BreadCrumb("{pk}", parent=job_list, needs=["pk"])
def job_detail(request, pk):
    job = get_restricted_job(request.user, pk, request=request)

    # Is the job favorite?
    is_favorite = False
    if request.user.is_authenticated:
        try:
            testjob_user = TestJobUser.objects.get(user=request.user, test_job=job)
            is_favorite = testjob_user.is_favorite
        except TestJobUser.DoesNotExist:
            is_favorite = False

    pipeline = description_data(job).get("pipeline", {})

    # Validate the job definition
    validation_errors = ""
    try:
        job_def = (
            job.multinode_definition if job.is_multinode else job.original_definition
        )
        validate(
            yaml_safe_load(job_def),
            extra_context_variables=settings.EXTRA_CONTEXT_VARIABLES,
        )
    except voluptuous.Invalid as exc:
        validation_errors = str(exc)

    data = {
        "job": job,
        "show_cancel": job.can_cancel(request.user),
        "show_fail": job.state == TestJob.STATE_CANCELING and request.user.is_superuser,
        "show_failure": job.can_annotate(request.user),
        "show_resubmit": job.can_resubmit(request.user),
        "bread_crumb_trail": BreadCrumbTrail.leading_to(job_detail, pk=pk),
        "change_priority": job.can_change_priority(request.user),
        "context_help": BreadCrumbTrail.leading_to(job_detail, pk="detail"),
        "is_favorite": is_favorite,
        "condition_choices": json_dumps(QueryCondition.get_condition_choices(job)),
        "available_content_types": json_dumps(
            QueryCondition.get_similar_job_content_types()
        ),
        "pipeline_data": pipeline,
        "job_tags": job.tags.all(),
        "size_limit": job.size_limit,
        "validation_errors": validation_errors,
    }

    try:
        job_file_size = logs_instance.size(job)
        if job_file_size is not None and job_file_size >= job.size_limit:
            log_data = []
            data["size_warning"] = True
        else:
            log_data = logs_instance.read(job)
            log_data = yaml_safe_load(log_data)
    except OSError:
        log_data = []
    except yaml.YAMLError:
        log_data = None

    if log_data:
        test_case_count = TestCase.objects.filter(suite__job=job).count()
        if test_case_count <= settings.TESTCASE_COUNT_LIMIT:
            results = {
                (t.suite.name, t.name): t.id
                for t in TestCase.objects.filter(suite__job=job).select_related("suite")
            }
            # list all related results
            for line in [line for line in log_data if line["lvl"] == "results"]:
                key = (line["msg"].get("definition"), line["msg"].get("case"))
                if key in results:
                    line["msg"]["case_id"] = results[key]

    # Get lava.job result if available
    lava_job_result = None
    with contextlib.suppress(TestCase.DoesNotExist):
        lava_job_obj = TestCase.objects.get(
            suite__job=job, suite__name="lava", name="job"
        )
        # Only print it if it's a failure
        if lava_job_obj.result == TestCase.RESULT_FAIL:
            lava_job_result = lava_job_obj.action_metadata

    data.update(
        {
            "log_data": log_data if log_data else [],
            "invalid_log_data": log_data is None,
            "lava_job_result": lava_job_result,
        }
    )

    return render(request, "lava_scheduler_app/job.html", data)


@BreadCrumb("Definition", parent=job_detail, needs=["pk"])
def job_definition(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    return render(
        request,
        "lava_scheduler_app/job_definition.html",
        {
            "job": job,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(job_definition, pk=pk),
            "show_cancel": job.can_cancel(request.user),
            "show_fail": job.state == TestJob.STATE_CANCELING
            and request.user.is_superuser,
            "show_resubmit": job.can_resubmit(request.user),
        },
    )


def job_description_yaml(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    filename = description_filename(job)
    if not filename:
        raise Http404()
    with open(filename) as desc:
        data = desc.read()
    response = HttpResponse(data, content_type="text/yaml")
    response["Content-Disposition"] = (
        "attachment; filename=job_description_%d.yaml" % job.id
    )
    return response


def job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    response = HttpResponse(job.display_definition, content_type="text/plain")
    filename = "job_%d.yaml" % job.id
    response["Content-Disposition"] = "attachment; filename=%s" % filename
    return response


@BreadCrumb("Multinode definition", parent=job_detail, needs=["pk"])
def multinode_job_definition(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    return render(
        request,
        "lava_scheduler_app/multinode_job_definition.html",
        {
            "job": job,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(
                multinode_job_definition, pk=pk
            ),
            "show_cancel": job.can_cancel(request.user),
            "show_fail": job.state == TestJob.STATE_CANCELING
            and request.user.is_superuser,
            "show_resubmit": job.can_resubmit(request.user),
        },
    )


def multinode_job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    response = HttpResponse(job.multinode_definition, content_type="text/plain")
    filename = "job_%d.yaml" % job.id
    response["Content-Disposition"] = "attachment; filename=multinode_%s" % filename
    return response


def job_fetch_data(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    if job.state != TestJob.STATE_FINISHED:
        raise Http404()
    path = os.path.join(job.output_dir, "job_data.gz")
    if not os.path.exists(path):
        raise Http404()
    # FileResponse could be used here with Django2.0 but
    # currently it doesn't set a useful extension.
    with open(path, "rb") as data:
        response = HttpResponse(data, content_type="application/gzip")
    response["Content-Disposition"] = 'attachment; filename="%s"' % os.path.basename(
        path
    )
    # response['Content-Encoding'] = 'gzip'
    return response


@BreadCrumb("My Jobs", parent=index)
def myjobs(request):
    get_object_or_404(User, pk=request.user.id)
    data = MyJobsView(request, model=TestJob, table_class=AllJobsTable)
    ptable = AllJobsTable(data.get_table_data())
    request_config(request, {"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/myjobs.html",
        {
            "bread_crumb_trail": BreadCrumbTrail.leading_to(myjobs),
            "myjobs_table": ptable,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
    )


@BreadCrumb("My Active Jobs", parent=index)
def my_active_jobs(request):
    get_object_or_404(User, pk=request.user.id)
    data = MyActiveJobsView(request, model=TestJob, table_class=ActiveJobsTable)
    ptable = ActiveJobsTable(data.get_table_data())
    request_config(request, {"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/myjobs_active.html",
        {
            "bread_crumb_trail": BreadCrumbTrail.leading_to(my_active_jobs),
            "sort": "-submit_time",
            "myjobs_active_table": ptable,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
    )


@BreadCrumb("My Queued Jobs", parent=index)
def my_queued_jobs(request):
    get_object_or_404(User, pk=request.user.id)
    data = MyQueuedJobsView(request, model=TestJob, table_class=QueuedJobsTable)
    ptable = QueuedJobsTable(data.get_table_data())
    request_config(request, {"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/myjobs_queued.html",
        {
            "bread_crumb_trail": BreadCrumbTrail.leading_to(my_queued_jobs),
            "sort": "-submit_time",
            "myjobs_queued_table": ptable,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
    )


@BreadCrumb("My Error Jobs", parent=index)
def my_error_jobs(request):
    get_object_or_404(User, pk=request.user.id)
    data = MyErrorJobsView(request, model=TestJob, table_class=AllJobsTable)
    ptable = JobErrorsTable(data.get_table_data(), prefix="job_errors_")
    request_config(request, {"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/myjobs_error.html",
        {
            "bread_crumb_trail": BreadCrumbTrail.leading_to(my_error_jobs),
            "sort": "-submit_time",
            "myjobs_error_table": ptable,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
    )


@BreadCrumb("Longest Running Jobs", parent=reports)
def longest_jobs(request, username=None):
    data = LongestJobsView(request, model=TestJob, table_class=LongestJobsTable)
    ptable = LongestJobsTable(data.get_table_data())
    request_config(request, {"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/longestjobs.html",
        {
            "bread_crumb_trail": BreadCrumbTrail.leading_to(longest_jobs),
            "longestjobs_table": ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
    )


@BreadCrumb("Favorite Jobs", parent=index)
def favorite_jobs(request):
    username = request.POST.get("username")
    if not username:
        username = request.user.username
    user = get_object_or_404(User, username=username)
    data = FavoriteJobsView(request, model=TestJob, table_class=AllJobsTable, user=user)
    ptable = AllJobsTable(data.get_table_data())
    request_config(request, {"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/favorite_jobs.html",
        {
            "bread_crumb_trail": BreadCrumbTrail.leading_to(favorite_jobs),
            "favoritejobs_table": ptable,
            "username": username,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
    )


def job_status(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    response_dict = {
        "actual_device": "<i>...</i>",
        "duration": "<i>...</i>",
        "job_state": job.get_state_display(),
        "failure_comment": job.failure_comment,
        "started": "<i>...</i>",
        "subjobs": [],
    }

    if job.actual_device:
        url = job.actual_device.get_absolute_url()
        host = job.actual_device.hostname
        html = '<a href="%s">%s</a> ' % (url, host)
        html += '<a href="%s"><span class="glyphicon glyphicon-stats"></span></a>' % (
            reverse("lava.scheduler.device_report", args=[job.actual_device.pk])
        )
        response_dict["actual_device"] = html

    if job.start_time:
        response_dict["started"] = str(naturaltime(job.start_time))
        response_dict["duration"] = timeuntil(timezone.now(), job.start_time)

    if job.state != job.STATE_FINISHED:
        response_dict["job_state"] = job.get_state_display()
    elif job.health == job.HEALTH_COMPLETE:
        response_dict["job_state"] = '<span class="label label-success">Complete</span>'
    elif job.health == job.HEALTH_INCOMPLETE:
        response_dict["job_state"] = (
            '<span class="label label-danger">%s</span>' % job.get_health_display()
        )
    else:
        response_dict["job_state"] = (
            '<span class="label label-warning">%s</span>' % job.get_health_display()
        )

    if job.is_multinode:
        for subjob in job.sub_jobs_list:
            response_dict["subjobs"].append((subjob.id, subjob.get_state_display()))

    if job.state == TestJob.STATE_FINISHED:
        response_dict["X-JobState"] = "1"

    return JsonResponse(response_dict)


def job_timing(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    try:
        data = logs_instance.read(job)
        logs = yaml_safe_load(data)
    except OSError:
        raise Http404

    # start and end patterns
    pattern_start = re.compile(
        "^start: (?P<level>[\\d.]+) (?P<action>[\\w_-]+) "
        "\\(timeout (?P<timeout>\\d+:\\d+:\\d+)\\)"
    )
    pattern_end = re.compile(
        "^end: (?P<level>[\\d.]+) (?P<action>[\\w_-]+) "
        "\\(duration (?P<duration>\\d+:\\d+:\\d+)\\)"
    )

    timings = {}
    total_duration = 0
    max_duration = 0
    summary = []
    for line in logs:
        # Only parse debug and info levels
        if line["lvl"] not in ["debug", "info"]:
            continue

        # Will raise if the log message is a python object
        try:
            match = pattern_start.match(line["msg"])
        except TypeError:
            continue

        if match is not None:
            d = match.groupdict()
            parts = d["timeout"].split(":")
            timeout = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            timings[d["level"]] = {"name": d["action"], "timeout": float(timeout)}
            continue

        # No need to catch TypeError here as we know it's a string
        match = pattern_end.match(line["msg"])
        if match is not None:
            d = match.groupdict()
            # TODO: validate does not have a proper start line
            if d["action"] == "validate":
                continue
            level = d["level"]
            parts = d["duration"].split(":")
            duration = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            # We create the entry because with some timeout, the start line
            # might be missing.
            timings.setdefault(level, {})["duration"] = duration

            max_duration = max(max_duration, duration)
            if "." not in level:
                total_duration += duration
                summary.append([d["action"], duration, 0])

    levels = sorted(timings.keys())

    # Construct the report
    pipeline = []
    for lvl in levels:
        duration = timings[lvl].get("duration", 0.0)
        timeout = timings[lvl].get("timeout", 0.0)
        name = timings[lvl].get("name", "???")
        pipeline.append(
            (lvl, name, duration, timeout, bool(duration >= (timeout * 0.85)))
        )

    # Compute the percentage
    if total_duration:
        for index, action in enumerate(summary):
            summary[index][2] = action[1] / total_duration * 100

    if not pipeline:
        response_dict = {"timing": "", "graph": []}
    else:
        timing = render_to_string(
            "lava_scheduler_app/job_timing.html",
            {
                "job": job,
                "pipeline": pipeline,
                "summary": summary,
                "total_duration": total_duration,
                "mean_duration": total_duration / len(pipeline),
                "max_duration": max_duration,
            },
        )

        response_dict = {"timing": timing, "graph": pipeline}

    return JsonResponse(response_dict)


def job_configuration(request, pk):
    def add_optional_file(tar, filename):
        with contextlib.suppress(OSError):
            tar.add(filename)

    job = get_restricted_job(request.user, pk, request=request)
    data = ""
    pwd = os.getcwd()
    try:
        with contextlib.suppress(FileNotFoundError):
            os.chdir(job.output_dir)
            fileobj = io.BytesIO()
            with tarfile.open(fileobj=fileobj, mode="w:bz2") as tar:
                add_optional_file(tar, "job.yaml")
                add_optional_file(tar, "device.yaml")
                add_optional_file(tar, "dispatcher.yaml")
                add_optional_file(tar, "env.yaml")
                add_optional_file(tar, "env-dut.yaml")
            fileobj.seek(0)
            data = fileobj.read()
            fileobj.close()
    finally:
        os.chdir(pwd)
    response = HttpResponse(data, content_type="application/tar")
    response["content-Disposition"] = "attachment; filename=configuration.tar.bz2"
    return response


def job_log_file_plain(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    try:
        data = logs_instance.open(job)
        response = FileResponse(data, content_type="application/yaml")
        response["Content-Disposition"] = "attachment; filename=job_%d.log" % job.id
        return response
    except OSError:
        raise Http404


def job_log_incremental(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    # Start from this line
    try:
        first_line = int(request.GET.get("line", 0))
    except ValueError:
        first_line = 0

    job_file_size = logs_instance.size(job)
    if job_file_size is not None and job_file_size >= job.size_limit:
        response = JsonResponse([], safe=False)
        response["X-Size-Warning"] = "1"
        return response

    try:
        data = logs_instance.read(job, first_line)
        data = yaml_safe_load(data)
        # When reaching EOF, yaml.load does return None instead of []
        if not data:
            data = []
        else:
            for line in data:
                line["msg"] = udecode(line["msg"])
                if line["lvl"] == "results":
                    definition = line["msg"].get("definition")
                    case = line["msg"].get("case")
                    if definition and case:
                        case_id = TestCase.objects.filter(
                            suite__job=job, suite__name=definition, name=case
                        ).values_list("id", flat=True)
                        if case_id:
                            line["msg"]["case_id"] = case_id[0]

    except (OSError, StopIteration, yaml.YAMLError):
        data = []

    response = JsonResponse(data, safe=False)

    if job.state == TestJob.STATE_FINISHED:
        response["X-Is-Finished"] = "1"

    return response


@transaction.atomic
def job_cancel(request, pk):
    job = get_restricted_job(request.user, pk, request=request, for_update=True)
    try:
        job.cancel(request.user)
        return redirect(job)
    except PermissionDenied:
        return HttpResponseForbidden(
            "you cannot cancel this job", content_type="text/plain"
        )


def job_fail(request, pk):
    if not request.user.is_superuser:
        return HttpResponseForbidden(
            "Only superusers can fail a job", content_type="text/plain"
        )

    with transaction.atomic():
        job = get_restricted_job(request.user, pk, request=request, for_update=True)
        if job.state != TestJob.STATE_CANCELING:
            return HttpResponseForbidden(
                "Job should be canceled before being failed", content_type="text/plain"
            )
        job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        job.save()
        return redirect(job)


def job_resubmit(request, pk):
    is_resubmit = request.POST.get("is_resubmit", False)

    response_data = {
        "is_authorized": False,
        "bread_crumb_trail": BreadCrumbTrail.leading_to(job_list),
    }

    job = get_restricted_job(request.user, pk, request=request)
    if job.can_resubmit(request.user):
        response_data["is_authorized"] = True

        if is_resubmit:
            try:
                original = job
                job = testjob_submission(
                    request.POST.get("definition-input"),
                    request.user,
                    original_job=original,
                )
                if isinstance(job, list):
                    response_data["job_list"] = [j.sub_id for j in job]
                    # Refer to first job in list for job info.
                    job = job[0]
                else:
                    response_data["job_id"] = job.id

                return HttpResponseRedirect(
                    reverse("lava.scheduler.job.detail", args=[job.pk])
                )

            except Exception as e:
                response_data["error"] = str(e)
                response_data["definition_input"] = request.POST.get("definition-input")
                return render(
                    request, "lava_scheduler_app/job_submit.html", response_data
                )
        else:
            if is_ajax(request):
                warnings = ""
                errors = ""
                try:
                    validate_job(request.POST.get("definition-input"))
                    try:
                        validate(
                            yaml_safe_load(request.POST.get("definition-input")),
                            extra_context_variables=settings.EXTRA_CONTEXT_VARIABLES,
                        )
                    except voluptuous.Invalid as exc:
                        warnings = str(exc)
                except Exception as e:
                    errors = str(e)
                return JsonResponse(
                    {
                        "result": "failure" if errors else "success",
                        "errors": errors,
                        "warnings": warnings,
                    }
                )

            if job.is_multinode:
                definition = job.multinode_definition
            else:
                definition = job.display_definition

            response_data["definition_input"] = definition
            return render(request, "lava_scheduler_app/job_submit.html", response_data)

    else:
        return HttpResponseForbidden(
            "you cannot re-submit this job", content_type="text/plain"
        )


class FailureForm(forms.ModelForm):
    class Meta:
        model = TestJob
        fields = ("failure_tags", "failure_comment")


@require_POST
def job_change_priority(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    if not job.can_change_priority(request.user):
        raise PermissionDenied()
    requested_priority = request.POST["priority"]
    if job.priority != requested_priority:
        job.priority = requested_priority
        job.save()
    return redirect(job)


def job_toggle_favorite(request, pk):
    if not request.user.is_authenticated:
        raise PermissionDenied()

    job = TestJob.objects.get(pk=pk)
    testjob_user, _ = TestJobUser.objects.get_or_create(user=request.user, test_job=job)

    testjob_user.is_favorite = not testjob_user.is_favorite
    testjob_user.save()
    return redirect(job)


def job_annotate_failure(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    if not job.can_annotate(request.user):
        raise PermissionDenied()

    if request.method == "POST":
        form = FailureForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            return redirect(job)
    else:
        form = FailureForm(instance=job)
    return render(
        request,
        "lava_scheduler_app/job_annotate_failure.html",
        {"form": form, "job": job},
    )


class RecentJobsView(JobTableView):
    def __init__(self, request, device, **kwargs):
        super().__init__(request, **kwargs)
        self.device = device

    def get_queryset(self):
        return (
            visible_jobs_with_custom_sort(self.request.user)
            .filter(actual_device=self.device)
            .select_related("submitter")
        )


@BreadCrumb("{pk}", parent=device_list, needs=["pk"])
def device_detail(request, pk):
    # Find the device and raise 404 if we are not allowed to see it
    try:
        device = Device.objects.select_related("device_type", "worker_host").get(pk=pk)
    except Device.DoesNotExist:
        raise Http404("No device matches the given query.")

    if not device.can_view(request.user):
        raise PermissionDenied()

    # Find previous and next device
    devices = (
        Device.objects.filter(device_type_id=device.device_type_id)
        .visible_by_user(request.user)
        .only("hostname", "state", "health")
        .order_by("hostname")
    )
    previous_device = None
    next_device = None
    devices_iter = iter(devices)
    for d in devices_iter:
        if d.hostname == device.hostname:
            try:
                next_device = next(devices_iter).hostname
            except StopIteration:
                next_device = None
            break
        previous_device = d.hostname

    prefix = "recent_"
    recent_data = RecentJobsView(
        request, device, model=TestJob, table_class=DeviceJobsTable
    )
    recent_ptable = DeviceJobsTable(recent_data.get_table_data(prefix), prefix=prefix)
    request_config(request, {"per_page": recent_ptable.length}).configure(recent_ptable)

    search_data = recent_ptable.prepare_search_data(recent_data)
    discrete_data = recent_ptable.prepare_discrete_data(recent_data)
    terms_data = recent_ptable.prepare_terms_data(recent_data)
    times_data = recent_ptable.prepare_times_data(recent_data)

    device_log_data = DeviceLogView(
        device, request, model=LogEntry, table_class=DeviceLogEntryTable
    )
    device_log_ptable = DeviceLogEntryTable(
        device_log_data.get_table_data(), prefix="device_log_"
    )
    request_config(request, paginate={"per_page": device_log_ptable.length}).configure(
        device_log_ptable
    )

    overrides = []
    try:
        mismatch = not bool(device.load_configuration())
    except yaml.YAMLError:
        mismatch = True

    device_can_change = device.can_change(request.user)
    return render(
        request,
        "lava_scheduler_app/device.html",
        {
            "device": device,
            "times_data": times_data,
            "terms_data": terms_data,
            "search_data": search_data,
            "discrete_data": discrete_data,
            "recent_job_table": recent_ptable,
            "device_log_table": device_log_ptable,
            "can_change": device_can_change,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(device_detail, pk=pk),
            "context_help": BreadCrumbTrail.show_help(device_detail, pk="help"),
            "next_device": next_device,
            "previous_device": previous_device,
            "overrides": overrides,
            "template_mismatch": mismatch,
        },
    )


@BreadCrumb("dictionary", parent=device_detail, needs=["pk"])
def device_dictionary(request, pk):
    # Find the device and raise 404 if we are not allowed to see it
    try:
        device = Device.objects.select_related("device_type").get(pk=pk)
    except Device.DoesNotExist:
        raise Http404("No device matches the given query.")

    if not device.can_view(request.user):
        raise PermissionDenied()

    raw_device_dict = device.load_configuration(output_format="raw")
    if not raw_device_dict:
        raise Http404

    # Parse the template
    device_yaml = device.load_configuration(output_format="yaml")

    return render(
        request,
        "lava_scheduler_app/devicedictionary.html",
        {
            "device": device,
            "dictionary": raw_device_dict,
            "device_yaml": device_yaml,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(device_dictionary, pk=pk),
            "context_help": ["lava-scheduler-device-dictionary"],
        },
    )


@BreadCrumb("Report", parent=device_detail, needs=["pk"])
def device_reports(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if not device.can_view(request.user):
        raise PermissionDenied()

    health_day_report = []
    health_week_report = []
    job_day_report = []
    job_week_report = []
    for day in reversed(range(7)):
        data = device_report_data(day * -1 - 1, day * -1, device)
        health_day_report.append(data[0])
        job_day_report.append(data[1])

    for week in reversed(range(10)):
        data = device_report_data(week * -7 - 7, week * -7, device)
        health_week_report.append(data[0])
        job_week_report.append(data[1])

    long_running = (
        TestJob.objects.filter(
            actual_device=device,
            state__in=[TestJob.STATE_RUNNING, TestJob.STATE_CANCELING],
        )
        .visible_by_user(request.user)
        .order_by("start_time")[:5]
    )
    return render(
        request,
        "lava_scheduler_app/device_reports.html",
        {
            "device": device,
            "health_week_report": health_week_report,
            "health_day_report": health_day_report,
            "job_week_report": job_week_report,
            "job_day_report": job_day_report,
            "long_running": long_running,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(device_reports, pk=pk),
        },
    )


def __set_device_health__(device, user, health, reason):
    with transaction.atomic():
        if not device.can_change(user):
            return HttpResponseForbidden("Permission denied")

        if health not in Device.HEALTH_REVERSE:
            return HttpResponseBadRequest("Wrong device health %s" % health)

        old_health_display = device.get_health_display()
        device.health = Device.HEALTH_REVERSE[health]
        device.save()
        if reason:
            device.log_admin_entry(
                user,
                "%s → %s (%s)"
                % (old_health_display, device.get_health_display(), reason),
            )
        else:
            device.log_admin_entry(
                user, "%s → %s" % (old_health_display, device.get_health_display())
            )


@require_POST
def device_health(request, pk):
    try:
        with transaction.atomic():
            device = Device.objects.select_for_update().get(pk=pk)
            health = request.POST.get("health").upper()
            reason = escape(request.POST.get("reason"))
            response = __set_device_health__(device, request.user, health, reason)
            if response is None:
                return HttpResponseRedirect(
                    reverse("lava.scheduler.device.detail", args=[device.pk])
                )
            else:
                return response
    except Device.DoesNotExist:
        raise Http404("Device %s not found" % pk)


@BreadCrumb("{pk}", parent=workers, needs=["pk"])
def worker_detail(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    data = DeviceTableView(request)
    ptable = NoWorkerDeviceTable(
        data.get_table_data()
        .filter(worker_host=worker)
        .exclude(health=Device.HEALTH_RETIRED)
        .order_by("hostname"),
        request=request,
    )
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)

    worker_log_data = WorkerLogView(
        worker, request, model=LogEntry, table_class=LogEntryTable
    )
    worker_log_ptable = LogEntryTable(
        worker_log_data.get_table_data(), prefix="worker_log_"
    )
    request_config(request, paginate={"per_page": worker_log_ptable.length}).configure(
        worker_log_ptable
    )

    return render(
        request,
        "lava_scheduler_app/worker.html",
        {
            "worker": worker,
            "worker_device_table": ptable,
            "worker_log_table": worker_log_ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "can_change": worker.can_change(request.user),
            "bread_crumb_trail": BreadCrumbTrail.leading_to(worker_detail, pk=pk),
        },
    )


@require_POST
def worker_health(request, pk):
    try:
        with transaction.atomic():
            worker = Worker.objects.select_for_update().get(pk=pk)
            if not worker.can_change(request.user):
                return HttpResponseForbidden("Permission denied")

            health = request.POST.get("health")
            reason = escape(request.POST.get("reason"))
            if health == "Active":
                worker.go_health_active(request.user, reason)
            elif health == "Maintenance":
                worker.go_health_maintenance(request.user, reason)
            elif health == "Retired":
                worker.go_health_retired(request.user, reason)
            else:
                return HttpResponseBadRequest("Wrong worker health %s" % health)

            worker.save()
            return HttpResponseRedirect(
                reverse("lava.scheduler.worker.detail", args=[pk])
            )
    except Worker.DoesNotExist:
        raise Http404("Worker %s not found" % pk)


def username_list_json(request):
    if not request.user.is_authenticated:
        raise PermissionDenied()

    term = request.GET["term"]
    users = []
    for user in User.objects.filter(Q(username__istartswith=term)):
        users.append({"id": user.id, "name": user.username, "label": user.username})
    return JsonResponse(users, safe=False)


class HealthCheckJobsView(JobTableView):
    def get_queryset(self):
        return (
            visible_jobs_with_custom_sort(self.request.user)
            .filter(health_check=True)
            .select_related("submitter")
        )


@BreadCrumb("Healthcheck", parent=job_list)
def healthcheck(request):
    health_check_data = HealthCheckJobsView(
        request,
        model=TestJob,
        table_class=AllJobsTable,
    )
    health_check_ptable = AllJobsTable(health_check_data.get_table_data())
    request_config(request, {"per_page": health_check_ptable.length}).configure(
        health_check_ptable
    )
    return render(
        request,
        "lava_scheduler_app/health_check_jobs.html",
        {
            "times_data": health_check_ptable.prepare_times_data(health_check_data),
            "terms_data": health_check_ptable.prepare_terms_data(health_check_data),
            "search_data": health_check_ptable.prepare_search_data(health_check_data),
            "discrete_data": health_check_ptable.prepare_discrete_data(
                health_check_data
            ),
            "health_check_table": health_check_ptable,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(healthcheck),
        },
    )


class QueueJobsView(JobTableView):
    def get_queryset(self):
        query = visible_jobs_with_custom_sort(self.request.user)
        query = query.filter(state=TestJob.STATE_SUBMITTED)
        return query.select_related("submitter")


@BreadCrumb("Queue", parent=job_list)
def queue(request):
    queue_data = QueueJobsView(request, model=TestJob, table_class=QueuedJobsTable)
    queue_ptable = QueuedJobsTable(queue_data.get_table_data())
    request_config(request, {"per_page": queue_ptable.length}).configure(queue_ptable)
    return render(
        request,
        "lava_scheduler_app/queue.html",
        {
            "times_data": queue_ptable.prepare_times_data(queue_data),
            "terms_data": queue_ptable.prepare_terms_data(queue_data),
            "search_data": queue_ptable.prepare_search_data(queue_data),
            "discrete_data": queue_ptable.prepare_discrete_data(queue_data),
            "queue_table": queue_ptable,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(queue),
        },
    )


class RunningView(LavaView):
    def get_queryset(self):
        return (
            DeviceType.objects.filter(display=True)
            .visible_by_user(self.request.user)
            .order_by("name")
        )


@BreadCrumb("Running", parent=index)
def running(request):
    running_data = RunningView(request, model=DeviceType, table_class=RunningTable)
    running_ptable = RunningTable(running_data.get_table_data(), request=request)
    config = RequestConfig(request, paginate={"per_page": running_ptable.length})
    config.configure(running_ptable)

    retirements = []
    for dt in running_data.get_queryset():
        if not Device.objects.filter(
            ~Q(health=Device.HEALTH_RETIRED) & Q(device_type=dt)
        ).visible_by_user(request.user):
            retirements.append(dt.name)

    return render(
        request,
        "lava_scheduler_app/running.html",
        {
            "running_table": running_ptable,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(running),
            "is_admin": request.user.has_perm(DeviceType.CHANGE_PERMISSION),
            "retirements": retirements,
        },
    )


def download_device_type_template(request, pk):
    dt = get_object_or_404(DeviceType, name=pk)

    if not dt.can_view(request.user):
        raise PermissionDenied()

    data = load_devicetype_template(dt.name, raw=True)
    if not data:
        raise Http404
    response = HttpResponse(data, content_type="text/plain; charset=utf-8")
    response["Content-Transfer-Encoding"] = "quoted-printable"
    response["Content-Disposition"] = "attachment; filename=%s_template.yaml" % dt.name
    return response


@require_POST
def similar_jobs(request, pk):
    logger = logging.getLogger("lava-scheduler")
    job = get_restricted_job(request.user, pk, request=request)

    entity = ContentType.objects.get_for_model(TestJob).model

    tables = request.POST.getlist("table")
    fields = request.POST.getlist("field")

    conditions = []
    for key, value in enumerate(tables):
        table = ContentType.objects.get(pk=value)
        operator = QueryCondition.EXACT
        job_field_value = None
        if table.model_class() == TestJob:
            try:
                field_obj = TestJob._meta.get_field(fields[key])
                job_field_value = getattr(job, fields[key])
                # Handle choice fields.
                if field_obj.choices:
                    job_field_value = dict(field_obj.choices)[job_field_value]

            except FieldDoesNotExist:
                logger.info("Test job does not contain field '%s'.", fields[key])
                continue

            # Handle Foreign key values and dates
            if job_field_value.__class__ == User:
                job_field_value = job_field_value.username
            elif job_field_value.__class__ == Device:
                job_field_value = job_field_value.hostname

            # For dates, use date of the job, not the exact moment in time.
            with contextlib.suppress(AttributeError):
                job_field_value = job_field_value.date()
                operator = QueryCondition.ICONTAINS

        else:  # NamedTestAttribute
            try:
                testdata = TestData.objects.filter(testjob=job).first()
                job_field_value = NamedTestAttribute.objects.get(
                    object_id=testdata.id,
                    content_type=ContentType.objects.get_for_model(TestData),
                    name=fields[key],
                ).value
            except NamedTestAttribute.DoesNotExist:
                # Ignore this condition.
                logger.info(
                    "Named attribute %s does not exist for similar jobs search.",
                    fields[key],
                )
                continue

        if job_field_value:
            condition = QueryCondition()
            condition.table = table
            condition.field = fields[key]
            condition.operator = operator
            condition.value = job_field_value
            conditions.append(condition)

    conditions = Query.serialize_conditions(conditions)

    return HttpResponseRedirect(
        "%s?entity=%s&conditions=%s"
        % (reverse("lava.results.query_custom"), entity, conditions)
    )
