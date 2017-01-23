# pylint: disable=too-many-lines,invalid-name
from collections import defaultdict, OrderedDict
import copy
import yaml
import json
import logging
import os
import simplejson
import StringIO
import datetime
import urllib2
import re
import sys

from django import forms

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, FieldDoesNotExist
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.template import loader
from django.db.models import Q, Count
from django.utils import timezone
from django_tables2 import (
    RequestConfig,
)

from lava_server.views import index as lava_index
from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from lava_scheduler_app.decorators import post_only
from lava_scheduler_app.logfile_helper import (
    formatLogFile,
    getDispatcherErrors,
    getDispatcherLogMessages
)
from lava_scheduler_app.models import (
    Device,
    DeviceDictionary,
    DeviceType,
    DeviceStateTransition,
    Tag,
    TestJob,
    TestJobUser,
    JSONDataError,
    validate_job,
    DevicesUnavailableException,
    Worker,
)
from lava_scheduler_app import utils
from lava_scheduler_app.dbutils import (
    initiate_health_check_job,
    device_type_summary,
    testjob_submission
)
from dashboard_app.models import BundleStream

from lava.utils.lavatable import LavaView
from lava_results_app.utils import description_data, description_filename
from lava_results_app.models import (
    NamedTestAttribute,
    Query,
    QueryCondition,
    TestSet,
    TestSuite,
    TestCase
)

from lava_scheduler_app.template_helper import expand_template
from lava_scheduler_app.job_templates import (
    DEFAULT_TEMPLATE,
    DEPLOY_IMAGE,
    DEPLOY_IMAGE_HWPACK,
    DEPLOY_IMAGE_KERNEL,
    LAVA_TEST_SHELL_REPO,
    LAVA_TEST_SHELL_URL,
    ACTIONS_LINARO,
    ACTIONS_LINARO_BOOT,
    ACTIONS_LINARO_ANDROID_IMAGE,
    COMMAND_SUBMIT_RESULTS,
    COMMAND_TEST_SHELL,
    ANDROID_BOOT_NO_CMDS,
    ANDROID_BOOT_WITH_CMDS
)

from django.contrib.auth.models import User, Group
from lava_scheduler_app.tables import (
    JobTable,
    all_jobs_with_custom_sort,
    IndexJobTable,
    FailedJobTable,
    LongestJobTable,
    DeviceTable,
    NoDTDeviceTable,
    RecentJobsTable,
    DeviceHealthTable,
    DeviceTypeTable,
    WorkerTable,
    HealthJobSummaryTable,
    DeviceTransitionTable,
    OverviewJobsTable,
    NoWorkerDeviceTable,
    QueueJobsTable,
    DeviceTypeTransitionTable,
    OnlineDeviceTable,
    PassingHealthTable,
    RunningTable,
)

# pylint: disable=too-many-attributes,too-many-ancestors,too-many-arguments,too-many-locals
# pylint: disable=too-many-statements,too-many-branches,too-many-return-statements
# pylint: disable=no-self-use,too-many-nested-blocks,too-few-public-methods

# The only functions which need to go in this file are those directly
# referenced in urls.py - other support functions can go in tables.py or similar.


def _str_to_bool(string):
    return string.lower() in ['1', 'true', 'yes']


class JobTableView(LavaView):

    def __init__(self, request, **kwargs):
        super(JobTableView, self).__init__(request, **kwargs)

    def device_query(self, term):  # pylint: disable=no-self-use
        visible = filter_device_types(self.request.user)
        device = list(Device.objects.filter(hostname__contains=term, device_type__in=visible))
        return Q(actual_device__in=device)

    def tags_query(self, term):
        tagnames = list(Tag.objects.filter(name__icontains=term))
        return Q(tags__in=tagnames)

    def owner_query(self, term):
        owner = list(User.objects.filter(username__contains=term))
        return Q(submitter__in=owner)

    def device_type_query(self, term):
        visible = filter_device_types(self.request.user)
        dt = list(DeviceType.objects.filter(name__contains=term, name__in=visible))
        return Q(device_type__in=dt)

    def job_status_query(self, term):
        # could use .lower() but that prevents matching Complete discrete from Incomplete
        matches = [p[0] for p in TestJob.STATUS_CHOICES if term in p[1]]
        return Q(status__in=matches)

    def device_status_query(self, term):
        # could use .lower() but that prevents matching Complete discrete from Incomplete
        matches = [p[0] for p in Device.STATUS_CHOICES if term in p[1]]
        return Q(status__in=matches)

    def health_status_query(self, term):
        # could use .lower() but that prevents matching Complete discrete from Incomplete
        matches = [p[0] for p in Device.HEALTH_CHOICES if term in p[1]]
        return Q(health_status__in=matches)

    def restriction_query(self, term):
        """
        This may turn out to be too much work for search to support.
        :param term: user submitted string
        :return: a query for devices which match the rendered restriction text
        """
        q = Q()

        query_list = []
        device_list = []
        user_list = User.objects.filter(
            id__in=Device.objects.filter(
                user__isnull=False).values('user'))
        for users in user_list:
            query_list.append(users.id)
        if len(query_list) > 0:
            device_list = User.objects.filter(id__in=query_list).filter(email__contains=term)
        query_list = []
        for users in device_list:
            query_list.append(users.id)
        if len(query_list) > 0:
            q = q.__or__(Q(user__in=query_list))

        query_list = []
        device_list = []
        group_list = Group.objects.filter(
            id__in=Device.objects.filter(
                group__isnull=False).values('group'))
        for groups in group_list:
            query_list.append(groups.id)
        if len(query_list) > 0:
            device_list = Group.objects.filter(id__in=query_list).filter(name__contains=term)
        query_list = []
        for groups in device_list:
            query_list.append(groups.id)
        if len(query_list) > 0:
            q = q.__or__(Q(group__in=query_list))

        # if the render function is changed, these will need to change too
        if term in "all users in group":
            q = q.__or__(Q(group__isnull=False))
        if term in "Unrestricted usage" or term in "Device owner by":
            q = q.__or__(Q(is_public=True))
        elif term in "Job submissions restricted to %s":
            q = q.__or__(Q(is_public=False))
        return q


class FailureTableView(JobTableView):

    def get_queryset(self):
        failures = [TestJob.INCOMPLETE, TestJob.CANCELED, TestJob.CANCELING]
        jobs = all_jobs_with_custom_sort().filter(status__in=failures)

        health = self.request.GET.get('health_check', None)
        if health:
            jobs = jobs.filter(health_check=_str_to_bool(health))

        dt = self.request.GET.get('device_type', None)
        if dt:
            jobs = jobs.filter(actual_device__device_type__name=dt)

        device = self.request.GET.get('device', None)
        if device:
            jobs = jobs.filter(actual_device__hostname=device)

        start = self.request.GET.get('start', None)
        if start:
            now = timezone.now()
            start = now + datetime.timedelta(int(start))

            end = self.request.GET.get('end', None)
            if end:
                end = now + datetime.timedelta(int(end))
                jobs = jobs.filter(start_time__range=(start, end))
        return jobs


class WorkerView(JobTableView):

    def get_queryset(self):
        return Worker.objects.filter(display=True).order_by('hostname')


def health_jobs_in_hr():
    return TestJob.objects.values('actual_device').filter(
        Q(health_check=True) & ~Q(actual_device=None)).exclude(
            actual_device__status__in=[Device.RETIRED]).exclude(
                status__in=[TestJob.SUBMITTED, TestJob.RUNNING]).distinct()


def _online_total():
    """ returns a tuple of (num_online, num_not_retired) """
    r = Device.objects.all().values('status').annotate(count=Count('status'))
    offline = total = 0
    for res in r:
        if res['status'] in [Device.OFFLINE, Device.OFFLINING]:
            offline += res['count']
        if res['status'] != Device.RETIRED:
            total += res['count']

    return total - offline, total


class IndexTableView(JobTableView):

    def get_queryset(self):
        return all_jobs_with_custom_sort()\
            .filter(status__in=[TestJob.CANCELING, TestJob.RUNNING])


class DeviceTableView(JobTableView):

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        return Device.objects.select_related("device_type").order_by(
            "hostname").filter(temporarydevice=None,
                               device_type__in=visible)


@BreadCrumb("Scheduler", parent=lava_index)
def index(request):
    data = DeviceTypeOverView(request, model=DeviceType, table_class=DeviceTypeTable)
    ptable = DeviceTypeTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)

    (num_online, num_not_retired) = _online_total()
    health_check_completed = health_jobs_in_hr().filter(
        status=TestJob.COMPLETE).count()
    health_check_total = health_jobs_in_hr().count()
    running_jobs_count = TestJob.objects.filter(
        status=TestJob.RUNNING, actual_device__isnull=False).count()
    active_devices_count = Device.objects.filter(
        status__in=[Device.RESERVED, Device.RUNNING]).count()
    return render(
        request,
        "lava_scheduler_app/index.html",
        {
            'device_status': "%d/%d" % (num_online, num_not_retired),
            'num_online': num_online,
            'num_not_retired': num_not_retired,
            'num_jobs_running': running_jobs_count,
            'num_devices_running': active_devices_count,
            'hc_completed': health_check_completed,
            'hc_total': health_check_total,
            'device_type_table': ptable,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
            'context_help': BreadCrumbTrail.leading_to(index),
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
        })


@BreadCrumb("Active jobs", parent=index)
def active_jobs(request):
    data = IndexTableView(request, model=TestJob, table_class=IndexJobTable)
    ptable = IndexJobTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)

    return render(
        request,
        "lava_scheduler_app/active_jobs.html",
        {
            'active_jobs_table': ptable,
            "sort": '-submit_time',
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(active_jobs),
        })


@BreadCrumb("Workers", parent=index)
def workers(request):
    data = WorkerView(request, model=None, table_class=WorkerTable)
    ptable = WorkerTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render(
        request,
        "lava_scheduler_app/allworkers.html",
        {
            'worker_table': ptable,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(workers),
        })


def type_report_data(start_day, end_day, dt, health_check):
    now = timezone.now()
    start_date = now + datetime.timedelta(start_day)
    end_date = now + datetime.timedelta(end_day)

    res = TestJob.objects.filter(actual_device__in=Device.objects.filter(device_type=dt),
                                 health_check=health_check,
                                 start_time__range=(start_date, end_date),
                                 status__in=(TestJob.COMPLETE, TestJob.INCOMPLETE,
                                             TestJob.CANCELED, TestJob.CANCELING),).values('status')
    url = reverse('lava.scheduler.failure_report')
    params = 'start=%s&end=%s&device_type=%s&health_check=%d' % (start_day, end_day, dt, health_check)
    return {
        'pass': res.filter(status=TestJob.COMPLETE).count(),
        'fail': res.exclude(status=TestJob.COMPLETE).count(),
        'date': start_date.strftime('%m-%d'),
        'failure_url': '%s?%s' % (url, params),
    }


def device_report_data(start_day, end_day, device, health_check):
    now = timezone.now()
    start_date = now + datetime.timedelta(start_day)
    end_date = now + datetime.timedelta(end_day)

    res = TestJob.objects.filter(actual_device=device, health_check=health_check,
                                 start_time__range=(start_date, end_date),
                                 status__in=(TestJob.COMPLETE, TestJob.INCOMPLETE,
                                             TestJob.CANCELED, TestJob.CANCELING),).values('status')
    url = reverse('lava.scheduler.failure_report')
    params = 'start=%s&end=%s&device=%s&health_check=%d' % (start_day, end_day, device.pk, health_check)
    return {
        'pass': res.filter(status=TestJob.COMPLETE).count(),
        'fail': res.exclude(status=TestJob.COMPLETE).count(),
        'date': start_date.strftime('%m-%d'),
        'failure_url': '%s?%s' % (url, params),
    }


def job_report(start_day, end_day, health_check):
    now = timezone.now()
    start_date = now + datetime.timedelta(start_day)
    end_date = now + datetime.timedelta(end_day)

    res = TestJob.objects.filter(health_check=health_check,
                                 start_time__range=(start_date, end_date)).values('status')
    url = reverse('lava.scheduler.failure_report')
    params = 'start=%s&end=%s&health_check=%d' % (start_day, end_day, health_check)
    return {
        'pass': res.filter(status=TestJob.COMPLETE).count(),
        'fail': res.filter(status__in=(TestJob.INCOMPLETE, TestJob.CANCELED,
                                       TestJob.CANCELING)).count(),
        'date': start_date.strftime('%m-%d'),
        'failure_url': '%s?%s' % (url, params),
    }


@BreadCrumb("Reports", parent=index)
def reports(request):
    health_day_report = []
    health_week_report = []
    job_day_report = []
    job_week_report = []
    for day in reversed(range(7)):
        health_day_report.append(job_report(day * -1 - 1, day * -1, True))
        job_day_report.append(job_report(day * -1 - 1, day * -1, False))
    for week in reversed(range(10)):
        health_week_report.append(job_report(week * -7 - 7, week * -7, True))
        job_week_report.append(job_report(week * -7 - 7, week * -7, False))
    template = loader.get_template("lava_scheduler_app/reports.html")
    return HttpResponse(template.render(
        {
            'health_week_report': health_week_report,
            'health_day_report': health_day_report,
            'job_week_report': job_week_report,
            'job_day_report': job_day_report,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
        },
        request=request))


@BreadCrumb("Failure Report", parent=reports)
def failure_report(request):

    data = FailureTableView(request)
    ptable = FailedJobTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)

    return render(
        request,
        "lava_scheduler_app/failure_report.html",
        {
            'device_type': request.GET.get('device_type', None),
            'device': request.GET.get('device', None),
            'failed_job_table': ptable,
            "sort": '-submit_time',
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(failure_report),
        })


@BreadCrumb("All Devices", parent=index)
def device_list(request):

    data = DeviceTableView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/alldevices.html")
    return HttpResponse(template.render(
        {
            'devices_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_list),
        },
        request=request))


@BreadCrumb("Active Devices", parent=index)
def active_device_list(request):

    data = ActiveDeviceView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/activedevices.html")
    return HttpResponse(template.render(
        {
            'active_devices_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(active_device_list),
        },
        request=request))


@BreadCrumb("Pipeline Devices", parent=index)
def pipeline_device_list(request):

    data = PipelineDeviceView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(
        ptable)
    template = loader.get_template("lava_scheduler_app/pipelinedevices.html")
    return HttpResponse(template.render(
        {
            'pipeline_devices_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                pipeline_device_list),
        },
        request=request))


class OnlineDeviceView(DeviceTableView):

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        return Device.objects.filter(device_type__in=visible)\
            .exclude(status=Device.RETIRED).order_by("status")


@BreadCrumb("Online Devices", parent=index)
def online_device_list(request):
    data = OnlineDeviceView(request, model=Device, table_class=OnlineDeviceTable)
    ptable = OnlineDeviceTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/onlinedevices.html")
    return HttpResponse(template.render(
        {
            'online_devices_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(online_device_list),
        },
        request=request))


class PassingHealthTableView(JobTableView):

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        return Device.objects.select_related("device_type")\
            .order_by("-health_status", "device_type", "hostname")\
            .filter(temporarydevice=None, device_type__in=visible)\
            .exclude(status=Device.RETIRED)


@BreadCrumb("Passing Health Checks", parent=index)
def passing_health_checks(request):
    data = PassingHealthTableView(request, model=Device,
                                  table_class=PassingHealthTable)
    ptable = PassingHealthTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/passinghealthchecks.html")
    return HttpResponse(template.render(
        {
            'passing_health_checks_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(passing_health_checks),
        },
        request=request))


class MyDeviceView(DeviceTableView):

    def get_queryset(self):
        return Device.objects.owned_by_principal(self.request.user).order_by('hostname')


@BreadCrumb("My Devices", parent=index)
def mydevice_list(request):

    data = MyDeviceView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/mydevices.html")
    return HttpResponse(template.render(
        {
            'my_device_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(mydevice_list)
        },
        request=request))


@BreadCrumb("My Devices Health History", parent=index)
def mydevices_health_history_log(request):
    prefix = "mydeviceshealthhistory_"
    mydeviceshhistory_data = MyDevicesHealthHistoryView(request,
                                                        model=DeviceStateTransition,
                                                        table_class=DeviceTypeTransitionTable)
    mydeviceshhistory_table = DeviceTypeTransitionTable(
        mydeviceshhistory_data.get_table_data(prefix),
        prefix=prefix,
    )
    config = RequestConfig(request,
                           paginate={"per_page": mydeviceshhistory_table.length})
    config.configure(mydeviceshhistory_table)
    template = loader.get_template("lava_scheduler_app/mydevices_health_history_log.html")
    return HttpResponse(template.render(
        {
            'mydeviceshealthhistory_table': mydeviceshhistory_table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(mydevices_health_history_log),
        },
        request=request))


def get_restricted_job(user, pk, request=None):
    """Returns JOB which is a TestJob object after checking for USER
    accessibility to the object.
    """
    try:
        job = TestJob.get_by_job_number(pk)
    except TestJob.DoesNotExist:
        raise Http404("No TestJob matches the given query.")
    if job.can_view(user):
        return job
    else:
        raise PermissionDenied()


def filter_device_types(user):

    """
    Filters the available DeviceType names to exclude DeviceTypes
    which are hidden from this user.
    :param user: User to check
    :return: A list of DeviceType.name which all contain
    at least one device this user can see.
    """
    visible = []
    for device_type in DeviceType.objects.filter(display=True).only('name', 'owners_only'):
        if device_type.num_devices_visible_to(user) > 0:
            visible.append(device_type.name)
    return visible


class ActiveDeviceView(DeviceTableView):

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        return Device.objects.filter(device_type__in=visible)\
            .exclude(status=Device.RETIRED).order_by("hostname")


class PipelineDeviceView(DeviceTableView):

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        return Device.objects.filter(device_type__in=visible,
                                     is_pipeline=True)\
                             .exclude(status=Device.RETIRED)\
                             .order_by("hostname")


class DeviceTypeOverView(JobTableView):

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        return device_type_summary(visible)


class NoDTDeviceView(DeviceTableView):

    def get_queryset(self):
        return Device.objects.filter(
            Q(temporarydevice=None) and ~Q(status__in=[Device.RETIRED])
        ).order_by('hostname')


@BreadCrumb("Device Type {pk}", parent=index, needs=['pk'])
def device_type_detail(request, pk):
    try:
        dt = DeviceType.objects \
            .select_related('architecture', 'bits', 'processor') \
            .get(pk=pk)
    except DeviceType.DoesNotExist:
        raise Http404()
    # Check that at least one device is visible to the current user
    if dt.owners_only:
        if dt.num_devices_visible_to(request.user) == 0:
            raise Http404('No device type matches the given query.')

    # Get some test job statistics
    now = timezone.now().date()
    devices = list(Device.objects.filter(device_type=dt)
                   .values_list('pk', flat=True))
    daily_complete = TestJob.objects.filter(
        actual_device__in=devices,
        health_check=True,
        submit_time__gte=(now - datetime.timedelta(days=1)),
        submit_time__lt=now,
        status=TestJob.COMPLETE).count()
    daily_failed = TestJob.objects.filter(
        actual_device__in=devices,
        health_check=True,
        submit_time__gte=(now - datetime.timedelta(days=1)),
        submit_time__lt=now,
        status=TestJob.INCOMPLETE).count()
    weekly_complete = TestJob.objects.filter(
        actual_device__in=devices,
        health_check=True,
        submit_time__gte=(now - datetime.timedelta(days=7)),
        submit_time__lt=now,
        status=TestJob.COMPLETE).count()
    weekly_failed = TestJob.objects.filter(
        actual_device__in=devices,
        health_check=True,
        submit_time__gte=(now - datetime.timedelta(days=7)),
        submit_time__lt=now,
        status=TestJob.INCOMPLETE).count()
    monthly_complete = TestJob.objects.filter(
        actual_device__in=devices,
        health_check=True,
        submit_time__gte=(now - datetime.timedelta(days=30)),
        submit_time__lt=now,
        status=TestJob.COMPLETE).count()
    monthly_failed = TestJob.objects.filter(
        actual_device__in=devices,
        health_check=True,
        submit_time__gte=(now - datetime.timedelta(days=30)),
        submit_time__lt=now,
        status=TestJob.INCOMPLETE).count()
    health_summary_data = [{
        "Duration": "24hours",
        "Complete": daily_complete,
        "Failed": daily_failed,
    }, {
        "Duration": "Week",
        "Complete": weekly_complete,
        "Failed": weekly_failed,
    }, {"Duration": "Month",
        "Complete": monthly_complete,
        "Failed": monthly_failed, }]

    prefix = 'no_dt_'
    no_dt_data = NoDTDeviceView(request, model=Device, table_class=NoDTDeviceTable)
    no_dt_ptable = NoDTDeviceTable(
        no_dt_data.get_table_data(prefix).
        filter(device_type=dt),
        prefix=prefix,
    )
    config = RequestConfig(request, paginate={"per_page": no_dt_ptable.length})
    config.configure(no_dt_ptable)

    prefix = "dt_"
    dt_jobs_data = AllJobsView(request, model=TestJob, table_class=OverviewJobsTable)
    dt_jobs_ptable = OverviewJobsTable(
        dt_jobs_data.get_table_data(prefix)
        .filter(actual_device__in=devices),
        prefix=prefix,
    )
    config = RequestConfig(request, paginate={"per_page": dt_jobs_ptable.length})
    config.configure(dt_jobs_ptable)

    prefix = 'health_'
    health_table = HealthJobSummaryTable(
        health_summary_data,
        prefix=prefix,
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
            ','.join([core.name for core in dt.cores.all().order_by('name')]))
    else:
        core_string = ''

    processor_name = dt.processor if dt.processor else ''
    architecture_name = dt.architecture if dt.architecture else ''
    bits_width = dt.bits.width if dt.bits else ''
    cpu_name = dt.cpu_model if dt.cpu_model else ''
    desc = dt.description if dt.description else ''
    aliases = ', '.join([alias.name for alias in dt.aliases.all()])

    if dt.health_check_job == "":
        health_freq_str = ""
    elif not Device.objects.filter(Q(device_type=dt), ~Q(status=Device.RETIRED)).count():
        health_freq_str = ""
    elif dt.health_denominator == DeviceType.HEALTH_PER_JOB:
        health_freq_str = "one every %d jobs" % dt.health_frequency
    else:
        health_freq_str = "one every %d hours" % dt.health_frequency
    template = loader.get_template("lava_scheduler_app/device_type.html")
    return HttpResponse(template.render(
        {
            'device_type': dt,
            'arch_version': architecture_name,
            'processor': processor_name,
            'arch_bits': bits_width,
            'cores': core_string,
            'cpu_model': cpu_name,
            'aliases': aliases,
            'description': desc,
            'search_data': search_data,
            "discrete_data": discrete_data,
            'terms_data': terms_data,
            'times_data': times_data,
            'running_jobs_num': TestJob.objects.filter(
                actual_device__in=Device.objects.filter(device_type=dt),
                status=TestJob.RUNNING).count(),
            # going offline are still active - number for comparison with running jobs.
            'active_num': Device.objects.filter(
                device_type=dt,
                status__in=[Device.RUNNING, Device.RESERVED, Device.OFFLINING]).count(),
            'queued_jobs_num': TestJob.objects.filter(
                Q(status=TestJob.SUBMITTED),
                Q(requested_device_type=dt) |
                Q(requested_device__in=Device.objects.filter(device_type=dt))).count(),
            'idle_num': Device.objects.filter(device_type=dt, status=Device.IDLE).count(),
            'offline_num': Device.objects.filter(device_type=dt, status=Device.OFFLINE).count(),
            'retired_num': Device.objects.filter(device_type=dt, status=Device.RETIRED).count(),
            'is_admin': request.user.has_perm('lava_scheduler_app.change_devicetype'),
            'health_job_summary_table': health_table,
            'device_type_jobs_table': dt_jobs_ptable,
            'devices_table_no_dt': no_dt_ptable,  # NoDTDeviceTable('devices' kwargs=dict(pk=pk)), params=(dt,)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_type_detail, pk=pk),
            'context_help': BreadCrumbTrail.leading_to(device_type_detail, pk='help'),
            'health_freq': health_freq_str,
        },
        request=request))


@BreadCrumb("{pk} device type health history", parent=device_type_detail, needs=['pk'])
def device_type_health_history_log(request, pk):
    device_type = get_object_or_404(DeviceType, pk=pk)
    prefix = "dthealthhistory_"
    dthhistory_data = DTHealthHistoryView(request, device_type,
                                          model=DeviceStateTransition,
                                          table_class=DeviceTypeTransitionTable)
    dthhistory_table = DeviceTypeTransitionTable(
        dthhistory_data.get_table_data(prefix),
        prefix=prefix,
    )
    config = RequestConfig(request,
                           paginate={"per_page": dthhistory_table.length})
    config.configure(dthhistory_table)
    template = loader.get_template("lava_scheduler_app/device_type_health_history_log.html")
    return HttpResponse(template.render(
        {
            'device_type': device_type,
            'dthealthhistory_table': dthhistory_table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_type_health_history_log, pk=pk),
        },
        request=request))


@BreadCrumb("{pk} device type report", parent=device_type_detail, needs=['pk'])
def device_type_reports(request, pk):
    device_type = get_object_or_404(DeviceType, pk=pk)
    health_day_report = []
    health_week_report = []
    job_day_report = []
    job_week_report = []
    for day in reversed(range(7)):
        health_day_report.append(type_report_data(day * -1 - 1, day * -1, device_type, True))
        job_day_report.append(type_report_data(day * -1 - 1, day * -1, device_type, False))
    for week in reversed(range(10)):
        health_week_report.append(type_report_data(week * -7 - 7, week * -7, device_type, True))
        job_week_report.append(type_report_data(week * -7 - 7, week * -7, device_type, False))

    long_running = TestJob.objects.filter(
        actual_device__in=Device.objects.filter(device_type=device_type),
        status__in=[TestJob.RUNNING,
                    TestJob.CANCELING]).order_by('start_time')[:5]
    template = loader.get_template("lava_scheduler_app/devicetype_reports.html")
    return HttpResponse(template.render(
        {
            'device_type': device_type,
            'health_week_report': health_week_report,
            'health_day_report': health_day_report,
            'job_week_report': job_week_report,
            'job_day_report': job_day_report,
            'long_running': long_running,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_type_reports, pk=pk),
        },
        request=request))


@BreadCrumb("All Device Health", parent=index)
def lab_health(request):
    data = DeviceTableView(request, model=Device, table_class=DeviceHealthTable)
    ptable = DeviceHealthTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/labhealth.html")
    return HttpResponse(template.render(
        {
            'device_health_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(lab_health),
        },
        request=request))


@BreadCrumb("All Health Jobs on Device {pk}", parent=index, needs=['pk'])
def health_job_list(request, pk):
    device = get_object_or_404(Device, pk=pk)
    trans_data = TransitionView(request, device)
    trans_table = DeviceTransitionTable(trans_data.get_table_data())
    config = RequestConfig(request, paginate={"per_page": trans_table.length})
    config.configure(trans_table)

    health_data = AllJobsView(request)
    health_table = JobTable(health_data.get_table_data().filter(
        actual_device=device, health_check=True))
    config.configure(health_table)

    terms_data = trans_table.prepare_terms_data(trans_data)
    terms_data.update(health_table.prepare_terms_data(health_data))

    search_data = trans_table.prepare_search_data(trans_data)
    search_data.update(health_table.prepare_search_data(health_data))

    times_data = trans_table.prepare_times_data(trans_data)
    times_data.update(health_table.prepare_times_data(health_data))

    discrete_data = trans_table.prepare_discrete_data(trans_data)
    discrete_data.update(health_table.prepare_discrete_data(health_data))
    template = loader.get_template("lava_scheduler_app/health_jobs.html")
    return HttpResponse(template.render(
        {
            'device': device,
            "terms_data": terms_data,
            "search_data": search_data,
            "discrete_data": discrete_data,
            "times_data": times_data,
            'transition_table': trans_table,
            'health_job_table': health_table,
            'show_forcehealthcheck':
                device.can_admin(request.user) and
                device.status not in [Device.RETIRED] and
                device.device_type.health_check_job != "",
            'can_admin': device.can_admin(request.user),
            'show_maintenance':
                device.can_admin(request.user) and
                device.status in [Device.IDLE, Device.RUNNING, Device.RESERVED],
            'edit_description': device.can_admin(request.user),
            'show_online':
                device.can_admin(request.user) and
                device.status in [Device.OFFLINE, Device.OFFLINING],
            'bread_crumb_trail': BreadCrumbTrail.leading_to(health_job_list, pk=pk),
        },
        request=request))


class MyJobsView(JobTableView):

    def get_queryset(self):
        jobs = TestJob.objects.select_related("actual_device", "requested_device",
                                              "requested_device_type", "group")\
            .extra(select={'device_sort': 'coalesce(actual_device_id, '
                                          'requested_device_id, requested_device_type_id)',
                           'duration_sort': 'end_time - start_time'}).all()\
            .filter(submitter=self.request.user)
        return jobs.order_by('-submit_time')


class LongestJobsView(JobTableView):

    def get_queryset(self):
        jobs = TestJob.objects.select_related("actual_device", "requested_device",
                                              "requested_device_type", "group")\
            .extra(select={'device_sort': 'coalesce(actual_device_id, '
                                          'requested_device_id, requested_device_type_id)',
                           'duration_sort': 'end_time - start_time'}).all()\
            .filter(status__in=[TestJob.RUNNING, TestJob.CANCELING])
        return jobs.order_by('start_time')


class FavoriteJobsView(JobTableView):

    def get_queryset(self):

        user = self.user
        if not user:
            user = self.request.user

        jobs = TestJob.objects.select_related("actual_device", "requested_device",
                                              "requested_device_type", "group")\
            .extra(select={'device_sort': 'coalesce(actual_device_id, '
                                          'requested_device_id, requested_device_type_id)',
                           'duration_sort': 'end_time - start_time'}).all()\
            .filter(testjobuser__user=user,
                    testjobuser__is_favorite=True)
        return jobs.order_by('-submit_time')


class AllJobsView(JobTableView):

    def get_queryset(self):
        return all_jobs_with_custom_sort()


@BreadCrumb("All Jobs", parent=index)
def job_list(request):

    data = AllJobsView(request, model=TestJob, table_class=JobTable)
    ptable = JobTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/alljobs.html")
    return HttpResponse(template.render(
        {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(job_list),
            'alljobs_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
        request=request))


@BreadCrumb("Submit Job", parent=index)
def job_submit(request):

    is_authorized = False
    if request.user and request.user.has_perm(
            'lava_scheduler_app.add_testjob'):
        is_authorized = True

    response_data = {
        'is_authorized': is_authorized,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(job_submit),
    }

    if request.method == "POST" and is_authorized:
        use_wizard = request.POST.get("wizard", None)

        if request.is_ajax():
            try:
                validate_job(request.POST.get("definition-input"))
                return HttpResponse(simplejson.dumps("success"))
            except Exception as e:
                return HttpResponse(simplejson.dumps(str(e)),
                                    content_type="application/json")

        elif use_wizard:
            try:
                if request.POST.get("create_stream"):
                    BundleStream.create_from_pathname(
                        request.POST.get("submit_stream"), request.user)
            except Exception as e:
                response_data["error"] = str(e)

            job_definition = _prepare_template(request)
            response_data["definition_input"] = str(job_definition).replace(
                "'", '"')
            template = loader.get_template("lava_scheduler_app/job_submit.html")
            return HttpResponse(template.render(
                response_data, request=request))

        else:
            try:
                definition_data = request.POST.get("definition-input")
                job = testjob_submission(definition_data, request.user)

                if isinstance(job, type(list())):
                    response_data["job_list"] = [j.sub_id for j in job]
                else:
                    response_data["job_id"] = job.id

                is_favorite = request.POST.get("is_favorite")
                if is_favorite:
                    testjob_user, _ = TestJobUser.objects.get_or_create(
                        user=request.user, test_job=job)
                    testjob_user.is_favorite = True
                    testjob_user.save()
                template = loader.get_template(
                    "lava_scheduler_app/job_submit.html")
                return HttpResponse(template.render(
                    response_data, request=request))

            except Exception as e:
                response_data["error"] = str(e)
                response_data["context_help"] = "lava scheduler submit job",
                response_data["definition_input"] = request.POST.get(
                    "definition-input")
                response_data["is_favorite"] = request.POST.get("is_favorite")
                template = loader.get_template(
                    "lava_scheduler_app/job_submit.html")
                return HttpResponse(template.render(
                    response_data, request=request))

    else:
        template = loader.get_template("lava_scheduler_app/job_submit.html")
        return HttpResponse(template.render(response_data, request=request))


@BreadCrumb("Submit Job", parent=index)
def job_submit_wizard(request):

    is_authorized = False
    if request.user and request.user.has_perm(
            'lava_scheduler_app.add_testjob'):
        is_authorized = True

    response_data = {
        'is_authorized': is_authorized,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(job_submit),
        'device_types': filter_device_types(request.user),
    }
    template = loader.get_template("lava_scheduler_app/job_wizard.html")
    return HttpResponse(template.render(response_data, request=request))


def _prepare_template(request):

    boot_type = request.POST.get("boot_type")

    if boot_type == "android_image":
        action_template = copy.deepcopy(ACTIONS_LINARO_ANDROID_IMAGE)

        action_config = {
            "BOOT_IMAGE_PARAMETER": str(request.POST.get("android_boot")),
            "DATA_IMAGE_PARAMETER": str(request.POST.get("android_data")),
            "SYSTEM_IMAGE_PARAMETER": str(request.POST.get("android_system")),
            "TESTS_PARAMETER": [str(request.POST.get("test_name"))],
            "TEST_NAME_PARAMETER": str(request.POST.get("test_name")),
        }

        if request.POST.get("boot_options") != "":
            android_boot_template = copy.deepcopy(ANDROID_BOOT_WITH_CMDS)
            boot_cmds = request.POST.get("boot_options").replace("\r", "")
            android_boot_config = {
                "ANDROID_BOOT_OPTIONS_PARAMETER":
                [str(x) for x in boot_cmds.split("\n")]
            }
        else:
            android_boot_template = copy.deepcopy(ANDROID_BOOT_NO_CMDS)
            android_boot_config = {}

        expand_template(android_boot_template, android_boot_config)
        action_config["ANDROID_BOOT"] = android_boot_template

    else:
        image_template = None
        image_config = None
        deploy_command = None
        if boot_type == "linaro_image":
            image_template = copy.deepcopy(DEPLOY_IMAGE)
            deploy_command = "deploy_linaro_image"
            image_config = {
                "PREBUILT_IMAGE_PARAMETER": str(request.POST.get("image_url"))
            }
        elif boot_type == "linaro_hwpack":
            image_template = copy.deepcopy(DEPLOY_IMAGE_HWPACK)
            deploy_command = "deploy_linaro_image"
            image_config = {
                "HWPACK_PARAMETER": str(request.POST.get("hwpack_url")),
                "ROOTFS_PARAMETER": str(request.POST.get("rootfs_url"))
            }
        elif boot_type == "linaro_kernel":
            image_template = copy.deepcopy(DEPLOY_IMAGE_KERNEL)
            deploy_command = "deploy_linaro_kernel"
            image_config = {
                "KERNEL_PARAMETER": str(request.POST.get("kernel")),
                "RAMDISK_PARAMETER": str(request.POST.get("ramdisk")),
                "DTB_PARAMETER": str(request.POST.get("dtb")),
                "ROOTFS_PARAMETER": str(request.POST.get("kernel_rootfs"))
            }

        expand_template(image_template, image_config)

        command_test_shell = None
        if request.POST.get("repo") or request.POST.get("testdef_url"):

            if request.POST.get("testdef_type") == "repo":
                test_shell_template = copy.deepcopy(LAVA_TEST_SHELL_REPO)
                test_shell_config = {
                    "REPO_PARAMETER": str(request.POST.get("repo")),
                    "TESTDEF_PARAMETER": str(request.POST.get("testdef"))
                }
            else:
                test_shell_template = copy.deepcopy(LAVA_TEST_SHELL_URL)
                test_shell_config = {
                    "TESTDEF_URLS_PARAMETER": [str(request.POST.get("testdef_url"))]
                }

            expand_template(test_shell_template, test_shell_config)

            command_test_shell = copy.deepcopy(COMMAND_TEST_SHELL)
            command_test_shell_config = {
                "TEST_SHELL_PARAMETER": test_shell_template
            }
            expand_template(command_test_shell, command_test_shell_config)

        if request.POST.get("boot_options") != "":
            action_template = copy.deepcopy(ACTIONS_LINARO_BOOT)
            boot_cmds = request.POST.get("boot_options").replace("\r", "")
            action_config = {
                "DEPLOY_COMMAND_PARAMETER": deploy_command,
                "DEPLOY_PARAMETER": image_template,
                "BOOT_OPTIONS_PARAMETER": [str(x) for x in boot_cmds.split("\n")],
                "COMMAND_TEST_SHELL": command_test_shell
            }

        else:
            action_template = copy.deepcopy(ACTIONS_LINARO)
            action_config = {
                "DEPLOY_COMMAND_PARAMETER": deploy_command,
                "DEPLOY_PARAMETER": image_template,
                "COMMAND_TEST_SHELL": command_test_shell
            }

    command_submit = None
    if request.POST.get("submit_stream"):
        command_submit = copy.deepcopy(COMMAND_SUBMIT_RESULTS)
        command_submit_config = {
            "SUBMIT_SERVER": "http://{0}{1}RPC2".format(
                utils.get_fqdn(),
                reverse('lava.home')),
            "BUNDLE_STREAM": str(request.POST.get("submit_stream"))
        }
        expand_template(command_submit, command_submit_config)

    action_config["COMMAND_SUBMIT_RESULTS"] = command_submit

    expand_template(action_template, action_config)

    notify = None
    if request.POST.get("notify"):
        notify = ["%s" % str(x.strip()) for x in request.POST.get("notify").split(",")]
    device_tags = None
    if request.POST.get("device_tags"):
        device_tags = ["%s" % str(x.strip()) for x in request.POST.get("device_tags").split(",")]

    job_template = copy.deepcopy(DEFAULT_TEMPLATE)
    default_config = {
        "JOBNAME_PARAMETER": str(request.POST.get("job_name")),
        "TIMEOUT_PARAMETER": int(request.POST.get("timeout")),
        "DEVICE_TYPE_PARAMETER": str(request.POST.get("device_type")),
        "NOTIFY_ON_INCOMPLETE_PARAMETER": notify,
        "ACTIONS_PARAMETER": action_template,
        "TAGS_PARAMETER": device_tags,
    }

    expand_template(job_template, default_config)

    return job_template


def remove_broken_string(line):
    # Check that the string is valid unicode.
    # This is not needed for python3.
    try:
        line['msg'].encode('utf-8')
    except AttributeError:
        pass
    except UnicodeDecodeError:
        line['msg'] = '<<lava: broken line>>'


@BreadCrumb("Job", parent=index, needs=['pk'])
def job_detail(request, pk):
    job = get_restricted_job(request.user, pk)

    is_favorite = False
    if request.user.is_authenticated():
        try:
            testjob_user, _ = TestJobUser.objects.get(user=request.user,
                                                      test_job=job)
            is_favorite = testjob_user.is_favorite
        except TestJobUser.DoesNotExist:
            is_favorite = False

    template = "lava_scheduler_app/job.html"
    data = {
        'job': job,
        'show_cancel': job.can_cancel(request.user),
        'show_failure': job.can_annotate(request.user),
        'show_resubmit': job.can_resubmit(request.user),
        'bread_crumb_trail': BreadCrumbTrail.leading_to(job_detail, pk=pk),
        'show_reload_page': job.status <= TestJob.RUNNING,
        'change_priority': job.can_change_priority(request.user),
        'context_help': BreadCrumbTrail.leading_to(job_detail, pk='detail'),
        'is_favorite': is_favorite,
        'condition_choices': simplejson.dumps(
            QueryCondition.get_condition_choices(job)
        ),
        'available_content_types': simplejson.dumps(
            QueryCondition.get_similar_job_content_types()
        ),
    }
    if job.is_pipeline:
        description = description_data(job.id)
        job_data = description.get('job', {})
        action_list = job_data.get('actions', [])
        pipeline = description.get('pipeline', {})

        deploy_list = [item['deploy'] for item in action_list if 'deploy' in item]
        boot_list = [item['boot'] for item in action_list if 'boot' in item]
        test_list = [item['test'] for item in action_list if 'test' in item]
        sections = []
        for action in pipeline:
            if 'section' in action:
                sections.append({action['section']: action['level']})
        default_section = 'boot'  # to come from user profile later.

        # Is it the old log format?
        if os.path.exists(os.path.join(job.output_dir, 'output.txt')):
            if 'section' in request.GET:
                log_data = utils.folded_logs(job, request.GET['section'], sections, summary=True)
            else:
                log_data = utils.folded_logs(job, default_section, sections, summary=True)
                if not log_data:
                    default_section = 'deploy'
                    log_data = utils.folded_logs(job, default_section, sections, summary=True)
        else:
            template = "lava_scheduler_app/job_pipeline.html"
            try:
                with open(os.path.join(job.output_dir, "output.yaml"), "r") as f_in:
                    log_data = yaml.load(f_in, Loader=yaml.CLoader)

                    if sys.version_info < (3, 0):
                        for line in log_data:
                            remove_broken_string(line)

            except IOError:
                log_data = []

        data.update({
            'device_data': description.get('device', {}),
            'job_data': job_data,
            'pipeline_data': pipeline,
            'deploy_list': deploy_list,
            'boot_list': boot_list,
            'test_list': test_list,
            'log_data': log_data,
            'default_section': default_section,
        })

    log_file = job.output_file()
    if log_file:
        with log_file as f:
            f.seek(0, 2)
            job_file_size = f.tell()

        if job_file_size >= job.size_limit:
            data.update({
                'job_file_present': True,
                'job_log_messages': None,
                'levels': None,
                'size_warning': job.size_limit,
                'job_file_size': job_file_size,
            })
            template = loader.get_template("lava_scheduler_app/job.html")
            return HttpResponse(template.render(data, request=request))

        if not job.failure_comment:
            job_errors = getDispatcherErrors(job.output_file())
            if len(job_errors) > 0:
                msg = job_errors[-1]
                if msg != "ErrorMessage: None":
                    job.failure_comment = msg
                    job.save()

        job_log_messages = getDispatcherLogMessages(job.output_file())
        levels = defaultdict(int)
        for kl in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            levels[kl] = 0
        for level, msg, _ in job_log_messages:
            levels[level] += 1
        levels = sorted(levels.items(), key=lambda (k, v): logging._levelNames.get(k))
        data.update({
            'job_file_present': True,
            'job_log_messages': job_log_messages,
            'levels': levels,
            'job_file_size': job_file_size,
        })
    else:
        data.update({
            'job_file_present': False,
        })

    if "repeat_count" in job.definition:
        data.update({
            'expand': True,
        })
    template_obj = loader.get_template(template)
    return HttpResponse(template_obj.render(data, request=request))


@BreadCrumb("Definition", parent=job_detail, needs=['pk'])
def job_definition(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    log_file = job.output_file()
    description = description_data(job.id) if job.is_pipeline else {}
    template = loader.get_template("lava_scheduler_app/job_definition.html")
    return HttpResponse(template.render(
        {
            'job': job,
            'pipeline': description.get('pipeline', []),
            'job_file_present': bool(log_file),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(job_definition, pk=pk),
            'show_resubmit': job.can_resubmit(request.user),
        },
        request=request))


def job_description_yaml(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    if not job.is_pipeline:
        raise Http404()
    filename = description_filename(job.id)
    if not filename:
        raise Http404()
    with open(filename, 'r') as desc:
        data = desc.read()
    response = HttpResponse(data, content_type='text/yaml')
    response['Content-Disposition'] = "attachment; filename=job_description_%d.yaml" % \
        job.id
    return response


def job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    response = HttpResponse(job.display_definition, content_type='text/plain')
    filename = "job_%d.yaml" % job.id if job.is_pipeline else "job_%d.json" % job.id
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    return response


@BreadCrumb("Expanded Definition", parent=job_detail, needs=['pk'])
def expanded_job_definition(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    log_file = job.output_file()
    template = loader.get_template("lava_scheduler_app/expanded_job_definition.html")
    return HttpResponse(template.render(
        {
            'job': job,
            'job_file_present': bool(log_file),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(expanded_job_definition, pk=pk),
            'show_cancel': job.can_cancel(request.user),
            'show_resubmit': job.can_resubmit(request.user),
        },
        request=request))


def expanded_job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    response = HttpResponse(job.definition, content_type='text/plain')
    response['Content-Disposition'] = "attachment; filename=job_%d.json" % \
        job.id
    return response


@BreadCrumb("Multinode definition", parent=job_detail, needs=['pk'])
def multinode_job_definition(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    log_file = job.output_file()
    template = loader.get_template("lava_scheduler_app/multinode_job_definition.html")
    return HttpResponse(template.render(
        {
            'job': job,
            'job_file_present': bool(log_file),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(multinode_job_definition, pk=pk),
            'show_cancel': job.can_cancel(request.user),
            'show_resubmit': job.can_resubmit(request.user),
        },
        request=request))


def multinode_job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk)
    response = HttpResponse(job.multinode_definition, content_type='text/plain')
    filename = "job_%d.yaml" % job.id if job.is_pipeline else "job_%d.json" % job.id
    response['Content-Disposition'] = \
        "attachment; filename=multinode_%s" % filename
    return response


@BreadCrumb("VMGroup definition", parent=job_detail, needs=['pk'])
def vmgroup_job_definition(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    log_file = job.output_file()
    template = loader.get_template("lava_scheduler_app/vmgroup_job_definition.html")
    return HttpResponse(template.render(
        {
            'job': job,
            'job_file_present': bool(log_file),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(vmgroup_job_definition, pk=pk),
            'show_cancel': job.can_cancel(request.user),
            'show_resubmit': job.can_resubmit(request.user),
        },
        request=request))


def vmgroup_job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    response = HttpResponse(job.vmgroup_definition, content_type='text/plain')
    response['Content-Disposition'] = \
        "attachment; filename=vmgroup_job_%d.json" % job.id
    return response


@BreadCrumb("My Jobs", parent=index)
def myjobs(request):
    user = get_object_or_404(User, pk=request.user.id)
    data = MyJobsView(request, model=TestJob, table_class=JobTable)
    ptable = JobTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/myjobs.html")
    return HttpResponse(template.render(
        {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(myjobs),
            'myjobs_table': ptable,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
        request=request))


@BreadCrumb("Longest Running Jobs", parent=reports)
def longest_jobs(request, username=None):

    data = LongestJobsView(request, model=TestJob, table_class=LongestJobTable)
    ptable = LongestJobTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(
        ptable)
    template = loader.get_template("lava_scheduler_app/longestjobs.html")
    return HttpResponse(template.render(
        {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(longest_jobs),
            'longestjobs_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
        request=request))


@BreadCrumb("Favorite Jobs", parent=index)
def favorite_jobs(request, username=None):

    if not username:
        username = request.user.username
    user = get_object_or_404(User, username=username)
    data = FavoriteJobsView(request, model=TestJob,
                            table_class=JobTable, user=user)
    ptable = JobTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/favorite_jobs.html")
    return HttpResponse(template.render(
        {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(favorite_jobs),
            'favoritejobs_table': ptable,
            'username': username,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
        request=request))


@BreadCrumb("Complete log", parent=job_detail, needs=['pk'])
def job_complete_log(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    if not job.is_pipeline:
        raise Http404
    # If this is a new log format, redirect to the job page
    if os.path.exists(os.path.join(job.output_dir, "output.yaml")):
        return HttpResponseRedirect(reverse('lava.scheduler.job.detail', args=[pk]))

    description = description_data(job.id)
    pipeline = description.get('pipeline', {})
    sections = []
    for action in pipeline:
        sections.append({action['section']: action['level']})
    default_section = 'boot'  # to come from user profile later.
    if 'section' in request.GET:
        log_data = utils.folded_logs(job, request.GET['section'], sections, summary=False)
    else:
        log_data = utils.folded_logs(job, default_section, sections, summary=False)
        if not log_data:
            default_section = 'deploy'
            log_data = utils.folded_logs(job, default_section, sections, summary=False)
    template = loader.get_template("lava_scheduler_app/pipeline_complete.html")
    return HttpResponse(template.render(
        {
            'show_cancel': job.can_cancel(request.user),
            'show_resubmit': job.can_resubmit(request.user),
            'show_failure': job.can_annotate(request.user),
            'job': job,
            'sections': sections,
            'default_section': default_section,
            'log_data': log_data,
            'pipeline_data': pipeline,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(job_log_file, pk=pk),
            # 'context_help': BreadCrumbTrail.leading_to(job_detail, pk='detail'),
        },
        request=request))


def job_section_log(request, job, log_name):
    job = get_restricted_job(request.user, job, request=request)
    if not job.is_pipeline:
        raise Http404
    path = os.path.join(job.output_dir, 'pipeline', log_name[0], log_name)
    if not os.path.exists(path):
        raise Http404
    with open(path, 'r') as data:
        log_content = yaml.load(data)
    log_target = []
    for logitem in log_content:
        for key, value in logitem.items():
            if key == 'target':
                log_target.append(value)
    # FIXME: decide if this should be a separate URL
    if not log_target:
        for logitem in log_content:
            for key, value in logitem.items():
                log_target.append(yaml.dump(value))

    response = HttpResponse('\n'.join(log_target), content_type='text/plain; charset=utf-8')
    response['Content-Transfer-Encoding'] = 'quoted-printable'
    response['Content-Disposition'] = "attachment; filename=job-%s_%s" % (job.id, log_name)
    return response


def job_status(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    response_dict = {'job_status': job.get_status_display()}
    if (job.actual_device and job.actual_device.status not in [Device.RESERVED, Device.RUNNING]) or \
            job.status not in [TestJob.COMPLETE, TestJob.INCOMPLETE, TestJob.CANCELED]:
        response_dict['device'] = render_to_string("lava_scheduler_app/_device_refresh.html",
                                                   {'job': job})
    response_dict['timing'] = render_to_string("lava_scheduler_app/_job_timing.html",
                                               {'job': job})
    if job.status == TestJob.SUBMITTED and not job.actual_device:
        response_dict['priority'] = job.priority
    if job.failure_comment:
        response_dict['failure'] = job.failure_comment
    if job.status in [TestJob.COMPLETE, TestJob.INCOMPLETE, TestJob.CANCELED]:
        response_dict['X-JobStatus'] = '1'
    response = HttpResponse(json.dumps(response_dict), content_type='text/json')
    return response


def job_pipeline_sections(request, pk):
    job = get_restricted_job(request.user, pk)
    if not job.is_pipeline:
        raise Http404
    description = description_data(job.id)
    pipeline = description.get('pipeline', {})
    sections = []
    for action in pipeline:
        if 'section' in action:
            sections.append({action['section']: action['level']})
    template = loader.get_template("lava_scheduler_app/_section_logging.html")
    response = HttpResponse(template.render(
        {
            'job': job,
            'pipeline_data': pipeline,
            'sections': sections,
            'default_section': 'any',
        }, request=request))
    if job.status in [TestJob.COMPLETE, TestJob.INCOMPLETE, TestJob.CANCELED]:
        response['X-Sections'] = '1'
    return response


def job_pipeline_timing(request, pk):
    job = get_restricted_job(request.user, pk)
    try:
        logs = yaml.load(open(os.path.join(job.output_dir, "output.yaml")))
    except IOError:
        raise Http404

    # start and end patterns
    pattern_start = re.compile("^start: (?P<level>[\\d.]+) (?P<action>[\\w_-]+) \\(timeout (?P<timeout>\\d+:\\d+:\\d+)\\)$")
    pattern_end = re.compile('^end: (?P<level>[\\d.]+) (?P<action>[\\w_-]+) \\(duration (?P<duration>\\d+:\\d+:\\d+)\\)$')

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
            timings[d["level"]] = {"name": d["action"],
                                   "timeout": float(timeout)}
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
            timings[level]["duration"] = duration

            max_duration = max(max_duration, duration)
            if '.' not in level:
                total_duration += duration
                summary.append([d["action"], duration, 0])

    levels = timings.keys()
    levels.sort()

    # Construct the report
    pipeline = []
    for lvl in levels:
        duration = timings[lvl].get("duration", 0.0)
        timeout = timings[lvl]["timeout"]
        pipeline.append((lvl, timings[lvl]["name"], duration, timeout,
                         bool(duration >= (timeout * 0.85))))

    # Compute the percentage
    for index, action in enumerate(summary):
        summary[index][2] = action[1] / total_duration * 100

    if len(pipeline) == 0:
        response_dict = {'timing': '',
                         'graph': []}
    else:
        timing = render_to_string('lava_scheduler_app/job_pipeline_timing.html',
                                  {'job': job, 'pipeline': pipeline, 'summary': summary,
                                   'total_duration': total_duration,
                                   'mean_duration': total_duration / len(pipeline),
                                   'max_duration': max_duration})

        response_dict = {'timing': timing,
                         'graph': pipeline}

    return HttpResponse(json.dumps(response_dict), content_type='text/json')


def job_pipeline_incremental(request, pk):
    # FIXME: LAVA-375 - monitor the logfile and possibly the count to send less data per poll.
    job = get_restricted_job(request.user, pk)
    summary = int(request.GET.get('summary', 0)) == 1
    description = description_data(job.id)
    pipeline = description.get('pipeline', {})
    sections = []
    for action in pipeline:
        if 'section' in action:
            sections.append({action['section']: action['level']})
    default_section = str(request.GET.get('section', 'deploy'))
    if 'section' in request.GET:
        log_data = utils.folded_logs(job, request.GET['section'], sections, summary=summary)
    else:
        log_data = utils.folded_logs(job, default_section, sections, summary=summary, increment=True)
        if not log_data:
            default_section = 'deploy'
            log_data = utils.folded_logs(job, default_section, sections, summary=summary)
    template = loader.get_template("lava_scheduler_app/_structured_logdata.html")
    response = HttpResponse(template.render(
        {
            'job': TestJob.objects.get(pk=pk),
            'sections': sections,
            'default_section': 'any',
            'log_data': log_data,
        },
        request=request))
    if job.status in [TestJob.COMPLETE, TestJob.INCOMPLETE, TestJob.CANCELED]:
        response['X-Is-Finished'] = '1'
    return response


@BreadCrumb("Complete log", parent=job_detail, needs=['pk'])
def job_log_file(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    if job.is_pipeline:
        return redirect(job_complete_log, pk=pk)
    log_file = job.output_file()
    if not log_file:
        raise Http404

    with log_file as f:
        f.seek(0, 2)
        job_file_size = f.tell()

    size_warning = 0
    if job_file_size >= job.size_limit:
        size_warning = job.size_limit
        content = None
    else:
        content = formatLogFile(job.output_file())
    template = loader.get_template("lava_scheduler_app/job_log_file.html")
    return HttpResponse(template.render(
        {
            'show_cancel': job.can_cancel(request.user),
            'show_resubmit': job.can_resubmit(request.user),
            'job': job,
            'job_file_present': bool(log_file),
            'sections': content,
            'size_warning': size_warning,
            'job_file_size': job_file_size,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(job_log_file, pk=pk),
            'show_failure': job.can_annotate(request.user),
            'context_help': BreadCrumbTrail.leading_to(job_detail, pk='detail'),
        },
        request=request))


def job_log_file_plain(request, pk):
    job = get_restricted_job(request.user, pk, request=request)
    # Old style jobs
    log_file = job.output_file()
    if log_file:
        response = HttpResponse(log_file, content_type='text/plain; charset=utf-8')
        response['Content-Transfer-Encoding'] = 'quoted-printable'
        response['Content-Disposition'] = "attachment; filename=job_%d.log" % job.id
        return response

    # New pipeline jobs
    try:
        with open(os.path.join(job.output_dir, "output.yaml"), "r") as log_file:
            response = HttpResponse(log_file, content_type='application/yaml')
            response['Content-Disposition'] = "attachment; filename=job_%d.log" % job.id
            return response
    except IOError:
        raise Http404


def job_log_incremental(request, pk):
    start = int(request.GET.get('start', 0))
    job = get_restricted_job(request.user, pk)
    log_file = job.output_file()
    log_file.seek(start)
    new_content = log_file.read()
    m = getDispatcherLogMessages(StringIO.StringIO(new_content))
    response = HttpResponse(
        simplejson.dumps(m), content_type='application/json')
    response['X-Current-Size'] = str(start + len(new_content))
    if job.status not in [TestJob.RUNNING, TestJob.CANCELING]:
        response['X-Is-Finished'] = '1'
    return response


def job_log_pipeline_incremental(request, pk):
    job = get_restricted_job(request.user, pk)
    # Start from this line
    try:
        first_line = int(request.GET.get("line", 0))
    except ValueError:
        first_line = 0

    try:
        with open(os.path.join(job.output_dir, "output.yaml"), "r") as f_in:
            # Manually skip the first lines
            # This is working because:
            # 1/ output.yaml is a list of dictionnaries
            # 2/ each item in this list is represented as one line in output.yaml
            count = 0
            for _ in range(first_line):
                count += len(f_in.next())
            # Seeking is needed to switch from reading lines to reading bytes.
            f_in.seek(count)
            # Load the remaining as yaml
            data = yaml.load(f_in, Loader=yaml.CLoader)
            # When reaching EOF, yaml.load does return None instead of []
            if not data:
                data = []
            if sys.version_info < (3, 0):
                for line in data:
                    remove_broken_string(line)

    except (IOError, StopIteration):
        data = []

    response = HttpResponse(
        simplejson.dumps(data), content_type='application/json')

    if job.status not in [TestJob.SUBMITTED, TestJob.RUNNING, TestJob.CANCELING]:
        response['X-Is-Finished'] = '1'

    return response


def job_full_log_incremental(request, pk):
    start = int(request.GET.get('start', 0))
    job = get_restricted_job(request.user, pk)
    log_file = job.output_file()
    log_file.seek(start)
    new_content = log_file.read()
    nl_index = new_content.rfind('\n', -NEWLINE_SCAN_SIZE)
    if nl_index >= 0:
        new_content = new_content[:nl_index + 1]
    m = formatLogFile(StringIO.StringIO(new_content))
    response = HttpResponse(
        simplejson.dumps(m), content_type='application/json')
    response['X-Current-Size'] = str(start + len(new_content))
    if job.status not in [TestJob.RUNNING, TestJob.CANCELING]:
        response['X-Is-Finished'] = '1'
    return response


LOG_CHUNK_SIZE = 512 * 1024
NEWLINE_SCAN_SIZE = 80


def job_output(request, pk):
    start = request.GET.get('start', 0)
    try:
        start = int(start)
    except ValueError:
        return HttpResponseBadRequest("invalid start")
    count_present = 'count' in request.GET
    job = get_restricted_job(request.user, pk)
    log_file = job.output_file()
    log_file.seek(0, os.SEEK_END)
    size = int(request.GET.get('count', log_file.tell()))
    if size - start > LOG_CHUNK_SIZE and not count_present:
        log_file.seek(-LOG_CHUNK_SIZE, os.SEEK_END)
        content = log_file.read(LOG_CHUNK_SIZE)
        nl_index = content.find('\n', 0, NEWLINE_SCAN_SIZE)
        if nl_index > 0 and not count_present:
            content = content[nl_index + 1:]
        skipped = size - start - len(content)
    else:
        skipped = 0
        log_file.seek(start, os.SEEK_SET)
        content = log_file.read(size - start)
    nl_index = content.rfind('\n', -NEWLINE_SCAN_SIZE)
    if nl_index >= 0 and not count_present:
        content = content[:nl_index + 1]
    response = HttpResponse(content)
    if skipped:
        response['X-Skipped-Bytes'] = str(skipped)
    response['X-Current-Size'] = str(start + len(content))
    if job.status not in [TestJob.RUNNING, TestJob.CANCELING]:
        response['X-Is-Finished'] = '1'
    return response


def job_cancel(request, pk):
    job = get_restricted_job(request.user, pk)
    if job.can_cancel(request.user):
        if job.is_multinode:
            multinode_jobs = TestJob.objects.filter(
                target_group=job.target_group)
            for multinode_job in multinode_jobs:
                multinode_job.cancel(request.user)
        elif job.is_vmgroup:
            vmgroup_jobs = TestJob.objects.filter(
                vm_group=job.vm_group)
            for vmgroup_job in vmgroup_jobs:
                vmgroup_job.cancel(request.user)
        else:
            job.cancel(request.user)
        return redirect(job)
    else:
        return HttpResponseForbidden(
            "you cannot cancel this job", content_type="text/plain")


def job_resubmit(request, pk):

    is_resubmit = request.POST.get("is_resubmit", False)

    response_data = {
        'is_authorized': False,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(job_list),
    }

    job = get_restricted_job(request.user, pk)
    if job.can_resubmit(request.user):
        response_data["is_authorized"] = True

        if is_resubmit:
            try:
                job = testjob_submission(request.POST.get("definition-input"),
                                         request.user)

                if isinstance(job, type(list())):
                    response_data["job_list"] = [j.sub_id for j in job]
                else:
                    response_data["job_id"] = job.id
                template = loader.get_template("lava_scheduler_app/job_submit.html")
                return HttpResponse(template.render(response_data, request=request))

            except Exception as e:
                response_data["error"] = str(e)
                response_data["definition_input"] = request.POST.get(
                    "definition-input")
                template = loader.get_template(
                    "lava_scheduler_app/job_submit.html")
                return HttpResponse(
                    template.render(response_data, request=request))
        else:
            if request.is_ajax():
                try:
                    validate_job(request.POST.get("definition-input"))
                    return HttpResponse(simplejson.dumps("success"))
                except Exception as e:
                    return HttpResponse(simplejson.dumps(str(e)),
                                        content_type="application/json")
            if job.is_multinode:
                definition = job.multinode_definition
            elif job.is_vmgroup:
                definition = job.vmgroup_definition
            else:
                definition = job.display_definition

            if request.user != job.owner and not request.user.is_superuser \
               and not utils.is_member(request.user, job.owner):
                obj = simplejson.loads(definition)

                # Iterate through the objects in the JSON and pop (remove)
                # the bundle stream path in submit_results action once we find it.
                for key in obj:
                    if key == "actions":
                        for i in xrange(len(obj[key])):
                            if obj[key][i]["command"] == \
                                    "submit_results_on_host" or \
                                    obj[key][i]["command"] == "submit_results":
                                for key1 in obj[key][i]:
                                    if key1 == "parameters":
                                        for key2 in obj[key][i][key1]:
                                            if key2 == "stream":
                                                obj[key][i][key1][key2] = ""
                                                break
                definition = simplejson.dumps(obj, sort_keys=True, indent=4, separators=(',', ': '))
                response_data["resubmit_warning"] = \
                    "The bundle stream was removed because you are neither the submitter "\
                    "nor in the same group as the submitter. Please provide a bundle stream."

            try:
                response_data["definition_input"] = definition
                template = loader.get_template(
                    "lava_scheduler_app/job_submit.html")
                return HttpResponse(
                    template.render(response_data, request=request))
            except (JSONDataError, ValueError, DevicesUnavailableException) \
                    as e:
                response_data["error"] = str(e)
                response_data["definition_input"] = definition
                template = loader.get_template("lava_scheduler_app/job_submit.html")
                return HttpResponse(template.render(response_data, request=request))

    else:
        return HttpResponseForbidden(
            "you cannot re-submit this job", content_type="text/plain")


class FailureForm(forms.ModelForm):

    class Meta:
        model = TestJob
        fields = ('failure_tags', 'failure_comment')


@post_only
def job_change_priority(request, pk):
    job = get_restricted_job(request.user, pk)
    if not job.can_change_priority(request.user):
        raise PermissionDenied()
    requested_priority = request.POST['priority']
    if job.priority != requested_priority:
        job.priority = requested_priority
        job.save()
    return redirect(job)


def job_toggle_favorite(request, pk):

    if not request.user.is_authenticated():
        raise PermissionDenied()

    job = TestJob.objects.get(pk=pk)
    testjob_user, _ = TestJobUser.objects.get_or_create(user=request.user,
                                                        test_job=job)

    testjob_user.is_favorite = not testjob_user.is_favorite
    testjob_user.save()
    return redirect(job)


def job_annotate_failure(request, pk):
    job = get_restricted_job(request.user, pk)
    if not job.can_annotate(request.user):
        raise PermissionDenied()

    if request.method == 'POST':
        form = FailureForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            return redirect(job)
    else:
        form = FailureForm(instance=job)
    template = loader.get_template("lava_scheduler_app/job_annotate_failure.html")
    return HttpResponse(template.render(
        {
            'form': form,
            'job': job,
        },
        request=request))


def job_json(request, pk):
    job = get_restricted_job(request.user, pk)
    json_text = simplejson.dumps({
        'status': job.get_status_display(),
        'results_link': request.build_absolute_uri(job.results_link),
    })
    content_type = 'application/json'
    if 'callback' in request.GET:
        json_text = '%s(%s)' % (request.GET['callback'], json_text)
        content_type = 'text/javascript'
    return HttpResponse(json_text, content_type=content_type)


@post_only
def get_remote_definition(request):
    """Fetches remote job definition file."""
    url = request.POST.get("url")

    try:
        data = urllib2.urlopen(url).read()
        # Validate that the data at the location is really JSON or YAML.
        # This is security based check so noone can misuse this url.
        yaml.load(data)
    except Exception as e:
        return HttpResponse(simplejson.dumps(str(e)),
                            content_type="application/json")

    return HttpResponse(data)


@post_only
def edit_transition(request):
    """Edit device state transition, based on user permission."""
    trans_id = request.POST.get("id")
    value = request.POST.get("value")

    transition_obj = get_object_or_404(DeviceStateTransition, pk=trans_id)
    if transition_obj.device.can_admin(request.user):
        transition_obj.update_message(value)
        return HttpResponse(transition_obj.message)
    else:
        return HttpResponseForbidden("Permission denied.",
                                     content_type="text/plain")


@BreadCrumb("Transition {pk}", parent=index, needs=['pk'])
def transition_detail(request, pk):
    transition = get_object_or_404(DeviceStateTransition, id=pk)
    device_type = transition.device.device_type
    if device_type.num_devices_visible_to(request.user) == 0:
        raise Http404()
    trans_data = TransitionView(request, transition.device, model=DeviceStateTransition, table_class=DeviceTransitionTable)
    trans_table = DeviceTransitionTable(trans_data.get_table_data())
    config = RequestConfig(request, paginate={"per_page": trans_table.length})
    config.configure(trans_table)
    template = loader.get_template("lava_scheduler_app/transition.html")
    return HttpResponse(template.render(
        {
            'device': transition.device,
            'transition': transition,
            "length": trans_table.length,
            "terms_data": trans_table.prepare_terms_data(trans_data),
            "search_data": trans_table.prepare_search_data(trans_data),
            "discrete_data": trans_table.prepare_discrete_data(trans_data),
            'transition_table': trans_table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(transition_detail, pk=pk),
            'old_state': transition.get_old_state_display(),
            'new_state': transition.get_new_state_display(),
        },
        request=request))


class RecentJobsView(JobTableView):

    def __init__(self, request, device, **kwargs):
        super(RecentJobsView, self).__init__(request, **kwargs)
        self.device = device

    def get_queryset(self):
        return TestJob.objects.select_related(
            "actual_device",
            "requested_device",
            "requested_device_type",
            "submitter",
            "user",
            "group",
        ).extra(
            select={'duration_sort': 'end_time - start_time'}
        ).filter(
            actual_device=self.device
        ).order_by(
            '-submit_time'
        )


class TransitionView(JobTableView):

    def __init__(self, request, device, **kwargs):
        super(TransitionView, self).__init__(request, **kwargs)
        self.device = device

    def get_queryset(self):
        return DeviceStateTransition.objects.select_related(
            'created_by'
        ).filter(
            device=self.device,
        ).order_by(
            '-id'
        )


class DeviceHealthHistoryView(JobTableView):

    def __init__(self, request, device, **kwargs):
        super(DeviceHealthHistoryView, self).__init__(request, **kwargs)
        self.device = device

    def get_queryset(self):
        states = [Device.OFFLINE, Device.OFFLINING, Device.RETIRED]

        return DeviceStateTransition.objects.select_related(
            'created_by'
        ).filter(
            (Q(old_state__in=states) | Q(new_state__in=states)),
            device=self.device
        ).order_by(
            '-created_on'
        )


class DTHealthHistoryView(JobTableView):

    def __init__(self, request, device_type, **kwargs):
        super(DTHealthHistoryView, self).__init__(request, **kwargs)
        self.device_type = device_type

    def get_queryset(self):
        states = [Device.OFFLINE, Device.OFFLINING, Device.RETIRED]

        return DeviceStateTransition.objects.select_related(
            'device__hostname', 'created_by'
        ).filter(
            (Q(old_state__in=states) | Q(new_state__in=states)),
            device__device_type=self.device_type
        ).order_by(
            'device__hostname',
            '-created_on'
        )


class MyDevicesHealthHistoryView(JobTableView):

    def __init__(self, request, **kwargs):
        super(MyDevicesHealthHistoryView, self).__init__(request, **kwargs)

    def get_queryset(self):
        states = [Device.OFFLINE, Device.OFFLINING, Device.RETIRED]

        return DeviceStateTransition.objects.select_related(
            'device', 'created_by'
        ).filter(
            (Q(old_state__in=states) | Q(new_state__in=states)),
            created_by=self.request.user
        ).order_by(
            'device__device_type',
            'device__hostname',
            '-created_on'
        )


@BreadCrumb("Device {pk}", parent=index, needs=['pk'])
def device_detail(request, pk):
    # Find the device and raise 404 if we are not allowed to see it
    try:
        device = Device.objects.select_related('device_type', 'user').get(pk=pk)
    except Device.DoesNotExist:
        raise Http404()

    # Any user that can access to a device_type can
    # see all the devices even if they are for owners_only
    if device.device_type.owners_only:
        if device.device_type.num_devices_visible_to(request.user) == 0:
            raise Http404('No device matches the given query.')

    # Find previous and next device
    devices = Device.objects \
        .filter(device_type_id=device.device_type_id) \
        .only('hostname').order_by('hostname')
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

    if device.status in [Device.OFFLINE, Device.OFFLINING]:
        try:
            transition = device.transitions.filter(message__isnull=False).latest('created_on').message
        except DeviceStateTransition.DoesNotExist:
            transition = None
    else:
        transition = None
    recent_data = RecentJobsView(request, device, model=TestJob, table_class=RecentJobsTable)
    prefix = "recent_"
    recent_ptable = RecentJobsTable(
        recent_data.get_table_data(prefix),
        prefix=prefix,
    )

    config = RequestConfig(request, paginate={"per_page": recent_ptable.length})
    config.configure(recent_ptable)

    prefix = "transition_"
    trans_data = TransitionView(request, device, model=DeviceStateTransition, table_class=DeviceTransitionTable)
    trans_table = DeviceTransitionTable(
        trans_data.get_table_data(prefix),
        prefix=prefix,
    )
    config = RequestConfig(request, paginate={"per_page": trans_table.length})
    config.configure(trans_table)

    search_data = recent_ptable.prepare_search_data(recent_data)
    search_data.update(trans_table.prepare_search_data(trans_data))

    discrete_data = recent_ptable.prepare_discrete_data(recent_data)
    discrete_data.update(trans_table.prepare_discrete_data(trans_data))

    terms_data = recent_ptable.prepare_terms_data(recent_data)
    terms_data.update(trans_table.prepare_terms_data(trans_data))

    times_data = recent_ptable.prepare_times_data(recent_data)
    times_data.update(trans_table.prepare_times_data(trans_data))

    mismatch = False

    overrides = None
    if device.is_pipeline:
        overrides = []
        path = utils.jinja_template_path(system=True)
        device_dict = DeviceDictionary.get(device.hostname)
        if device_dict:
            extends = device_dict.to_dict()['parameters']['extends']
            devicetype_file = os.path.join(path, 'device-types', '%s' % extends)
            mismatch = not os.path.exists(devicetype_file)

    template = loader.get_template("lava_scheduler_app/device.html")
    return HttpResponse(template.render(
        {
            'device': device,
            "times_data": times_data,
            "terms_data": terms_data,
            "search_data": search_data,
            "discrete_data": discrete_data,
            'transition': transition,
            'transition_table': trans_table,
            'recent_job_table': recent_ptable,
            'show_forcehealthcheck':
                device.can_admin(request.user) and
                device.status not in [Device.RETIRED] and
                device.device_type.health_check_job != "",
            'can_admin': device.can_admin(request.user),
            'exclusive': device.is_exclusive,
            'pipeline': device.is_pipeline,
            'show_maintenance':
                device.can_admin(request.user) and
                device.status in [Device.IDLE, Device.RUNNING, Device.RESERVED],
            'edit_description': device.can_admin(request.user),
            'show_online': (device.can_admin(request.user) and
                            device.status in [Device.OFFLINE, Device.OFFLINING]),
            'show_restrict': (device.is_public and device.can_admin(request.user) and
                              device.status not in [Device.RETIRED]),
            'show_pool': (not device.is_public and device.can_admin(request.user) and
                          device.status not in [Device.RETIRED] and not
                          device.device_type.owners_only),
            'cancel_looping': device.health_status == Device.HEALTH_LOOPING,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_detail, pk=pk),
            'context_help': BreadCrumbTrail.show_help(device_detail, pk="help"),
            'next_device': next_device,
            'previous_device': previous_device,
            'overrides': overrides,
            'template_mismatch': mismatch,
        },
        request=request))


@BreadCrumb("{pk} device dictionary", parent=device_detail, needs=['pk'])
def device_dictionary(request, pk):
    # Find the device and raise 404 if we are not allowed to see it
    try:
        device = Device.objects.select_related('device_type', 'user').get(pk=pk)
    except Device.DoesNotExist:
        raise Http404()

    # Any user that can access to a device_type can
    # see all the devices even if they are for owners_only
    if device.device_type.owners_only:
        if device.device_type.num_devices_visible_to(request.user) == 0:
            raise Http404('No device matches the given query.')

    if not device.is_pipeline:
        raise Http404

    device_dict = DeviceDictionary.get(device.hostname)
    if not device_dict:
        raise Http404

    device_dict = device_dict.to_dict()
    dictionary = OrderedDict()
    vland = OrderedDict()
    extra = {}
    sequence = utils.device_dictionary_sequence()
    for item in sequence:
        if item in device_dict['parameters'].keys():
            dictionary[item] = device_dict['parameters'][item]
    vlan_sequence = utils.device_dictionary_vlan()
    for item in vlan_sequence:
        if item in device_dict['parameters'].keys():
            vland[item] = yaml.dump(device_dict['parameters'][item], default_flow_style=False)
    for item in set(device_dict['parameters'].keys()) - set(sequence) - set(vlan_sequence):
        extra[item] = device_dict['parameters'][item]
    template = loader.get_template("lava_scheduler_app/devicedictionary.html")
    return HttpResponse(template.render(
        {
            'device': device,
            'dictionary': dictionary,
            'vland': vland,
            'extra': extra,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_dictionary, pk=pk),
            'context_help': ['lava-scheduler-device-dictionary'],
        },
        request=request))


@BreadCrumb("{pk} device report", parent=device_detail, needs=['pk'])
def device_reports(request, pk):
    device = get_object_or_404(Device, pk=pk)
    health_day_report = []
    health_week_report = []
    job_day_report = []
    job_week_report = []
    for day in reversed(range(7)):
        health_day_report.append(device_report_data(day * -1 - 1, day * -1, device, True))
        job_day_report.append(device_report_data(day * -1 - 1, day * -1, device, False))
    for week in reversed(range(10)):
        health_week_report.append(device_report_data(week * -7 - 7, week * -7, device, True))
        job_week_report.append(device_report_data(week * -7 - 7, week * -7, device, False))

    long_running = TestJob.objects.filter(
        actual_device=device,
        status__in=[TestJob.RUNNING,
                    TestJob.CANCELING]).order_by('start_time')[:5]
    template = loader.get_template("lava_scheduler_app/device_reports.html")
    return HttpResponse(template.render(
        {
            'device': device,
            'health_week_report': health_week_report,
            'health_day_report': health_day_report,
            'job_week_report': job_week_report,
            'job_day_report': job_day_report,
            'long_running': long_running,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_reports, pk=pk),
        },
        request=request))


@post_only
def device_maintenance_mode(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        device.put_into_maintenance_mode(request.user, request.POST.get('reason'),
                                         request.POST.get('notify'))
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot administer this device", content_type="text/plain")


@post_only
def device_online(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        device.put_into_online_mode(request.user, request.POST.get('reason'),
                                    request.POST.get('skiphealthcheck'))
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot administer this device", content_type="text/plain")


@post_only
def device_looping_mode(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        device.put_into_looping_mode(request.user, request.POST.get('reason'))
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot administer this device", content_type="text/plain")


@post_only
def device_force_health_check(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.can_admin(request.user):
        job = initiate_health_check_job(device)
        if not job:
            raise Http404
        device.log_admin_entry(request.user, "forced a health check")
        return redirect(job)
    else:
        return HttpResponseForbidden(
            "you cannot administer this device", content_type="text/plain")


def device_edit_description(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        device.description = request.POST.get('desc')
        device.save()
        device.log_admin_entry(request.user, "changed description")
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot edit the description of this device", content_type="text/plain")


@post_only
def device_restrict_device(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        message = "added a restriction: %s" % request.POST.get('reason')
        device.is_public = False
        device.save(update_fields=['is_public'])
        device.log_admin_entry(request.user, message)
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot restrict submissions to this device", content_type="text/plain")


@post_only
def device_derestrict_device(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        message = "removed restriction: %s" % request.POST.get('reason')
        device.is_public = True
        device.save(update_fields=['is_public'])
        device.log_admin_entry(request.user, message)
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot derestrict submissions to this device", content_type="text/plain")


@BreadCrumb("{pk} device health history", parent=device_detail, needs=['pk'])
def device_health_history_log(request, pk):
    device = get_object_or_404(Device, pk=pk)
    prefix = "healthhistory_"
    hhistory_data = DeviceHealthHistoryView(request, device,
                                            model=DeviceStateTransition,
                                            table_class=DeviceTransitionTable)
    hhistory_table = DeviceTransitionTable(
        hhistory_data.get_table_data(prefix),
        prefix=prefix,
    )
    config = RequestConfig(request,
                           paginate={"per_page": hhistory_table.length})
    config.configure(hhistory_table)
    template = loader.get_template("lava_scheduler_app/device_health_history_log.html")
    return HttpResponse(template.render(
        {
            'device': device,
            'healthhistory_table': hhistory_table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_health_history_log, pk=pk),
        },
        request=request))


@BreadCrumb("Worker: {pk}", parent=index, needs=['pk'])
def worker_detail(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    data = DeviceTableView(request)
    ptable = NoWorkerDeviceTable(data.get_table_data().filter(worker_host=worker).order_by('hostname'))
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    template = loader.get_template("lava_scheduler_app/worker.html")
    return HttpResponse(template.render(
        {
            'worker': worker,
            'worker_device_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'can_admin': worker.can_admin(request.user),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(worker_detail,
                                                            pk=pk),
        },
        request=request))


@post_only
def edit_worker_desc(request):
    """Edit worker description, based on user permission."""

    pk = request.POST.get("id")
    value = request.POST.get("value")
    worker_obj = get_object_or_404(Worker, pk=pk)

    if worker_obj.can_admin(request.user):
        worker_obj.update_description(value)
        return HttpResponse(worker_obj.get_description())
    else:
        return HttpResponseForbidden("Permission denied.",
                                     content_type="text/plain")


def username_list_json(request):

    term = request.GET['term']
    users = []
    for user in User.objects.filter(Q(username__istartswith=term)):
        users.append(
            {"id": user.id,
             "name": user.username,
             "label": user.username})
    return HttpResponse(simplejson.dumps(users), content_type='application/json')


class HealthCheckJobsView(JobTableView):

    def get_queryset(self):
        return all_jobs_with_custom_sort().filter(health_check=True)


@BreadCrumb("Healthcheck", parent=index)
def healthcheck(request):
    health_check_data = HealthCheckJobsView(request, model=TestJob,
                                            table_class=JobTable)
    health_check_ptable = JobTable(health_check_data.get_table_data(),)
    config = RequestConfig(request,
                           paginate={"per_page": health_check_ptable.length})
    config.configure(health_check_ptable)
    template = loader.get_template("lava_scheduler_app/health_check_jobs.html")
    return HttpResponse(template.render(
        {
            "times_data": health_check_ptable.prepare_times_data(health_check_data),
            "terms_data": health_check_ptable.prepare_terms_data(health_check_data),
            "search_data": health_check_ptable.prepare_search_data(health_check_data),
            "discrete_data": health_check_ptable.prepare_discrete_data(health_check_data),
            'health_check_table': health_check_ptable,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(healthcheck),
        },
        request=request))


class PipelineJobsView(JobTableView):

    def get_queryset(self):
        return all_jobs_with_custom_sort().filter(is_pipeline=True)


@BreadCrumb("Pipeline", parent=index)
def pipeline(request):
    pipeline_data = PipelineJobsView(request, model=TestJob,
                                     table_class=JobTable)
    pipeline_ptable = JobTable(pipeline_data.get_table_data(),)
    config = RequestConfig(request,
                           paginate={"per_page": pipeline_ptable.length})
    config.configure(pipeline_ptable)
    template = loader.get_template("lava_scheduler_app/pipelinejobs.html")
    return HttpResponse(template.render(
        {
            "times_data": pipeline_ptable.prepare_times_data(pipeline_data),
            "terms_data": pipeline_ptable.prepare_terms_data(pipeline_data),
            "search_data": pipeline_ptable.prepare_search_data(pipeline_data),
            "discrete_data": pipeline_ptable.prepare_discrete_data(pipeline_data),
            'pipeline_table': pipeline_ptable,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(pipeline),
        },
        request=request))


class QueueJobsView(JobTableView):

    def get_queryset(self):
        return all_jobs_with_custom_sort().filter(status=TestJob.SUBMITTED)


@BreadCrumb("Queue", parent=index)
def queue(request):
    queue_data = QueueJobsView(request, model=TestJob, table_class=QueueJobsTable)
    queue_ptable = QueueJobsTable(
        queue_data.get_table_data(),
    )
    config = RequestConfig(request, paginate={"per_page": queue_ptable.length})
    config.configure(queue_ptable)
    template = loader.get_template("lava_scheduler_app/queue.html")
    return HttpResponse(template.render(
        {
            "times_data": queue_ptable.prepare_times_data(queue_data),
            "terms_data": queue_ptable.prepare_terms_data(queue_data),
            "search_data": queue_ptable.prepare_search_data(queue_data),
            "discrete_data": queue_ptable.prepare_discrete_data(queue_data),
            'queue_table': queue_ptable,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(queue),
        },
        request=request))


class RunningView(LavaView):

    def get_queryset(self):
        return DeviceType.objects.filter(display=True).order_by('name')


@BreadCrumb("Running", parent=index)
def running(request):
    running_data = RunningView(request, model=DeviceType, table_class=RunningTable)
    running_ptable = RunningTable(running_data.get_table_data())
    config = RequestConfig(request, paginate={"per_page": running_ptable.length})
    config.configure(running_ptable)

    retirements = []
    for dt in running_data.get_queryset():
        if not Device.objects.filter(~Q(status=Device.RETIRED) & Q(device_type=dt)):
            retirements.append(dt.name)

    template = loader.get_template("lava_scheduler_app/running.html")
    return HttpResponse(template.render(
        {
            'running_table': running_ptable,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(running),
            'is_admin': request.user.has_perm('lava_scheduler_app.change_devicetype'),
            'retirements': retirements,
        },
        request=request))


def download_device_type_template(request, pk):
    device_type = DeviceType.objects.filter(name=pk)
    if not device_type:
        raise Http404
    device_type = device_type[0]
    data = utils.load_devicetype_template(device_type.name)
    if not data:
        raise Http404
    response = HttpResponse(yaml.dump(data), content_type='text/plain; charset=utf-8')
    response['Content-Transfer-Encoding'] = 'quoted-printable'
    response['Content-Disposition'] = "attachment; filename=%s_template.yaml" % device_type.name
    return response


@post_only
def similar_jobs(request, pk):
    from lava_results_app.models import TestData

    logger = logging.getLogger('lava_scheduler_app')
    job = get_restricted_job(request.user, pk)
    if not job.can_change_priority(request.user):
        raise PermissionDenied()

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
                logger.info(
                    "Test job does not contain field '%s'." % fields[key])
                continue

            # Handle Foreign key values and dates
            if job_field_value.__class__ == User:
                job_field_value = job_field_value.username
            elif job_field_value.__class__ == Device:
                job_field_value = job_field_value.hostname

            # For dates, use date of the job, not the exact moment in time.
            try:
                job_field_value = job_field_value.date()
                operator = QueryCondition.ICONTAINS
            except AttributeError:  # it's not a date.
                pass

        else:  # NamedTestAttribute
            try:

                testdata = TestData.objects.filter(testjob=job).first()
                job_field_value = NamedTestAttribute.objects.get(
                    object_id=testdata.id,
                    content_type=ContentType.objects.get_for_model(TestData),
                    name=fields[key]
                ).value
            except NamedTestAttribute.DoesNotExist:
                # Ignore this condition.
                logger.info("Named attribute %s does not exist for similar jobs search." % fields[key])
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
        "%s?entity=%s&conditions=%s" % (
            reverse('lava.results.query_custom'),
            entity, conditions))
