from collections import defaultdict
import logging
import os
import simplejson
import StringIO
import datetime
import urllib2
from dateutil.relativedelta import relativedelta

from django import forms

from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.http import (
    HttpResponse,
    Http404,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render_to_response,
    render,
)
from django.template import RequestContext
from django.template import defaultfilters as filters
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.db import models
from django.db.models import Q

from django_tables2 import (
    Column,
    TemplateColumn,
    RequestConfig,
)

from lava_server.views import index as lava_index
from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from lava_scheduler_app.logfile_helper import (
    formatLogFile,
    getDispatcherErrors,
    getDispatcherLogMessages
)
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    DeviceStateTransition,
    TestJob,
    JSONDataError,
    validate_job_json,
    DevicesUnavailableException,
    Worker,
)
from lava.utils.lavatable import LavaTable, LavaView
from django.contrib.auth.models import User, Group
from lava_scheduler_app.tables import (
    JobTable,
    DateColumn,
    IDLinkColumn,
    RestrictedIDLinkColumn,
    pklink,
    all_jobs_with_custom_sort,
    IndexJobTable,
    FailedJobTable,
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
)

# The only functions which need to go in this file are those directly
# referenced in urls.py - other support functions can go in tables.py or similar.


def post_only(func):
    def decorated(request, *args, **kwargs):
        if request.method != 'POST':
            return HttpResponseNotAllowed('Only POST here')
        return func(request, *args, **kwargs)
    return decorated


def _str_to_bool(string):
    return string.lower() in ['1', 'true', 'yes']


class JobTableView(LavaView):

    def __init__(self, request, **kwargs):
        super(JobTableView, self).__init__(request, **kwargs)

    def device_query(self, term):
        visible = filter_device_types(self.request.user)
        device = list(Device.objects.filter(hostname__contains=term, device_type__in=visible))
        return Q(actual_device__in=device)

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
            now = datetime.datetime.now()
            start = now + datetime.timedelta(int(start))

            end = self.request.GET.get('end', None)
            if end:
                end = now + datetime.timedelta(int(end))
                jobs = jobs.filter(start_time__range=(start, end))
        return jobs


class WorkerView(JobTableView):

    def get_queryset(self):
        return Worker.objects.all().order_by('hostname')


def health_jobs_in_hr(hr=-24):
    return TestJob.objects.filter(health_check=True,
                                  start_time__gte=(datetime.datetime.now() +
                                                   relativedelta(hours=hr)))\
        .exclude(status__in=[TestJob.SUBMITTED, TestJob.RUNNING])


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
        return all_jobs_with_custom_sort().filter(status__in=[TestJob.SUBMITTED, TestJob.RUNNING])


class DeviceTableView(JobTableView):

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        return Device.objects.select_related("device_type").order_by(
            "hostname").filter(temporarydevice=None,
                               device_type__in=visible)


@BreadCrumb("Scheduler", parent=lava_index)
def index(request):

    index_data = IndexTableView(request, model=TestJob, table_class=IndexJobTable)
    prefix = 'index_'
    index_table = IndexJobTable(
        index_data.get_table_data(prefix),
        prefix=prefix,
    )
    config = RequestConfig(request, paginate={"per_page": index_table.length})
    config.configure(index_table)

    prefix = 'device_'
    dt_overview_data = DeviceTypeOverView(request, model=DeviceType, table_class=DeviceTypeTable)
    dt_overview_table = DeviceTypeTable(
        dt_overview_data.get_table_data(prefix),
        prefix=prefix,
    )
    config = RequestConfig(request, paginate={"per_page": dt_overview_table.length})
    config.configure(dt_overview_table)

    prefix = 'worker_'
    worker_data = WorkerView(request, model=None, table_class=WorkerTable)
    worker_table = WorkerTable(
        worker_data.get_table_data(prefix),
        prefix=prefix,
    )
    config = RequestConfig(request, paginate={"per_page": worker_table.length})
    config.configure(worker_table)

    search_data = index_table.prepare_search_data(index_data)
    search_data.update(dt_overview_table.prepare_search_data(dt_overview_data))

    terms_data = index_table.prepare_terms_data(index_data)
    terms_data.update(dt_overview_table.prepare_terms_data(dt_overview_data))

    times_data = index_table.prepare_times_data(index_data)

    discrete_data = index_table.prepare_discrete_data(index_data)
    discrete_data.update(dt_overview_table.prepare_discrete_data(dt_overview_data))

    return render(
        request,
        "lava_scheduler_app/index.html",
        {
            'device_status': "%d/%d" % _online_total(),
            'health_check_status': "%s/%s" % (
                health_jobs_in_hr().filter(status=TestJob.COMPLETE).count(),
                health_jobs_in_hr().count()),
            'device_type_table': dt_overview_table,
            'worker_table': worker_table,
            'active_jobs_table': index_table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
            'context_help': BreadCrumbTrail.leading_to(index),
            "terms_data": terms_data,
            "search_data": search_data,
            "discrete_data": discrete_data,
            "times_data": times_data,
        })


def type_report_data(start_day, end_day, dt, health_check):
    now = datetime.datetime.now()
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
    now = datetime.datetime.now()
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
    now = datetime.datetime.now()
    start_date = now + datetime.timedelta(start_day)
    end_date = now + datetime.timedelta(end_day)

    res = TestJob.objects.filter(health_check=health_check,
                                 start_time__range=(start_date, end_date),
                                 status__in=(TestJob.COMPLETE, TestJob.INCOMPLETE,
                                             TestJob.CANCELED, TestJob.CANCELING),).values('status')
    url = reverse('lava.scheduler.failure_report')
    params = 'start=%s&end=%s&health_check=%d' % (start_day, end_day, health_check)
    return {
        'pass': res.filter(status=TestJob.COMPLETE).count(),
        'fail': res.exclude(status=TestJob.COMPLETE).count(),
        'date': start_date.strftime('%m-%d'),
        'failure_url': '%s?%s' % (url, params),
    }


@BreadCrumb("Reports", parent=lava_index)
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

    long_running = TestJob.objects.filter(status__in=[TestJob.RUNNING,
                                                      TestJob.CANCELING]).order_by('start_time')[:5]

    return render_to_response(
        "lava_scheduler_app/reports.html",
        {
            'health_week_report': health_week_report,
            'health_day_report': health_day_report,
            'job_week_report': job_week_report,
            'job_day_report': job_day_report,
            'long_running': long_running,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
        },
        RequestContext(request))


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
    return render_to_response(
        "lava_scheduler_app/alldevices.html",
        {
            'devices_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_list),
        },
        RequestContext(request))


@BreadCrumb("Active Devices", parent=index)
def active_device_list(request):

    data = ActiveDeviceView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render_to_response(
        "lava_scheduler_app/activedevices.html",
        {
            'active_devices_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(active_device_list),
        },
        RequestContext(request))


class MyDeviceView(DeviceTableView):

    def get_queryset(self):
        return Device.objects.owned_by_principal(self.request.user)


@BreadCrumb("My Devices", parent=index)
def mydevice_list(request):

    data = MyDeviceView(request, model=Device, table_class=DeviceTable)
    ptable = DeviceTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render_to_response(
        "lava_scheduler_app/mydevices.html",
        {
            'my_device_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(mydevice_list)
        },
        RequestContext(request))


def get_restricted_job(user, pk):
    """Returns JOB which is a TestJob object after checking for USER
    accessibility to the object.
    """
    job = TestJob.get_by_job_number(pk)
    if job.actual_device:
        device_type = job.actual_device.device_type
    elif job.requested_device:
        device_type = job.requested_device.device_type
    else:
        device_type = job.requested_device_type
    if len(device_type.devices_visible_to(user)) == 0:
            raise Http404()
    if not job.is_accessible_by(user) and not user.is_superuser:
        raise PermissionDenied()
    return job


def filter_device_types(user):

    """
    Filters the available DeviceType names to exclude DeviceTypes
    which are hidden from this user.
    :param user: User to check
    :return: A list of DeviceType.name which all contain
    at least one device this user can see.
    """
    visible = []
    for device_type in DeviceType.objects.filter(display=True):
        if len(device_type.devices_visible_to(user)) > 0:
            visible.append(device_type.name)
    return visible


class SumIfSQL(models.sql.aggregates.Aggregate):
    is_ordinal = True
    sql_function = 'SUM'
    sql_template = 'SUM((%(condition)s)::int)'


class SumIf(models.Aggregate):
    name = 'SumIf'

    def add_to_query(self, query, alias, col, source, is_summary):
        aggregate = SumIfSQL(col,
                             source=source, is_summary=is_summary, **self.extra)
        query.aggregates[alias] = aggregate


class ActiveDeviceView(DeviceTableView):

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        return Device.objects.filter(device_type__in=visible)\
            .exclude(status=Device.RETIRED).order_by("hostname")


class DeviceTypeOverView(JobTableView):

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        devices = DeviceType.objects.filter(name__in=visible)\
            .annotate(idle=SumIf('device', condition='status=%s' % Device.IDLE),
                      offline=SumIf('device', condition='status in (%s,%s)' %
                                                        (Device.OFFLINE, Device.OFFLINING)),
                      busy=SumIf('device', condition='status in (%s,%s)' %
                                                     (Device.RUNNING, Device.RESERVED)),
                      restricted=SumIf('device', condition='is_public is False and status not in (%s)' %
                                                           Device.RETIRED),
                      ).order_by('name')
        return devices


class NoDTDeviceView(DeviceTableView):

    def get_queryset(self):
        return Device.objects.filter(Q(temporarydevice=None) and
                                     ~Q(status__in=[Device.RETIRED])
                                     ).order_by('hostname')


def populate_capabilities(dt):
    """
    device capabilities data retrieved from health checks
    param dt: a device type to check for capabilities.
    return: dict of capabilities based on the most recent health check.
    the returned dict contains a full set of empty values if no
    capabilities could be determined.
    """
    capability = {
        'capabilities_date': None,
        'processor': None,
        'models': None,
        'cores': 0,
        'emulated': False,
        'flags': [],
    }
    hardware_flags = []
    hardware_cpu_models = []
    use_health_job = dt.health_check_job != ""
    try:
        health_job = TestJob.objects.filter(
            actual_device__in=Device.objects.filter(device_type=dt),
            health_check=use_health_job,
            status=TestJob.COMPLETE).order_by('submit_time').reverse()[0]
    except IndexError:
        return capability
    if not health_job:
        return capability
    job = TestJob.objects.filter(id=health_job.id)[0]
    if not job:
        return capability
    bundle = job._results_bundle
    if not bundle:
        return capability
    bundle_json = bundle.get_sanitized_bundle().get_human_readable_json()
    if not bundle_json:
        return capability
    bundle_data = simplejson.loads(bundle_json)
    if 'hardware_context' not in bundle_data['test_runs'][0]:
        return capability
    # ok, we finally have a hardware_context for this device type, populate.
    devices = bundle_data['test_runs'][0]['hardware_context']['devices']
    capability['capabilities_date'] = job.end_time
    for device in devices:
        # multiple core cpus have multiple device.cpu entries, each with attributes.
        if device['device_type'] == 'device.cpu':
            if device['attributes']['cpu_type'] == '?':
                model = device['attributes']['model name']
            else:
                model = device['attributes']['cpu_type']
            if 'cpu_part' in device['attributes']:
                cpu_part = int(device['attributes']['cpu_part'], 16)
            elif 'CPU part' in device['attributes']:
                cpu_part = int(device['attributes']['CPU part'], 16)
            else:
                cpu_part = None
            if model.startswith("ARMv7") and cpu_part:
                if hex(cpu_part) == hex(0xc05):
                    model = "%s - %s" % (model, "Cortex A5")
                if hex(cpu_part) == hex(0xc07):
                    model = "%s - %s" % (model, "Cortex A7")
                if hex(cpu_part) == hex(0xc08):
                    model = "%s - %s" % (model, "Cortex A8")
                if hex(cpu_part) == hex(0xc09):
                    model = "%s - %s" % (model, "Cortex A9")
                if hex(cpu_part) == hex(0xc0f):
                    model = "%s - %s" % (model, "Cortex A15")
            hardware_cpu_models.append(model)
            if 'Features' in device['attributes']:
                hardware_flags.append(device['attributes']['Features'])
            elif 'flags' in device['attributes']:
                hardware_flags.append(device['attributes']['flags'])
            if device['attributes']['cpu_type'].startswith("QEMU"):
                capability['emulated'] = True
            capability['cores'] += 1
        if device['device_type'] == 'device.board':
            capability['processor'] = device['description']
    if len(hardware_flags) == 0:
        hardware_flags.append("None")
    if len(hardware_cpu_models) == 0:
        hardware_cpu_models.append("None")
    capability['models'] = ", ".join(hardware_cpu_models)
    capability['flags'] = ", ".join(hardware_flags)
    return capability


@BreadCrumb("Device Type {pk}", parent=index, needs=['pk'])
def device_type_detail(request, pk):
    dt = get_object_or_404(DeviceType, pk=pk)
    if dt.owners_only:
        visible = filter_device_types(request.user)
        if not dt.name in visible:
            raise Http404('No device type matches the given query.')
    daily_complete = TestJob.objects.filter(
        actual_device__in=Device.objects.filter(device_type=dt),
        health_check=True,
        submit_time__gte=(datetime.datetime.now().date() - datetime.timedelta(days=1)),
        submit_time__lt=datetime.datetime.now().date(),
        status=TestJob.COMPLETE).count()
    daily_failed = TestJob.objects.filter(
        actual_device__in=Device.objects.filter(device_type=dt),
        health_check=True,
        submit_time__gte=(datetime.datetime.now().date() - datetime.timedelta(days=1)),
        submit_time__lt=datetime.datetime.now().date(),
        status=TestJob.INCOMPLETE).count()
    weekly_complete = TestJob.objects.filter(
        actual_device__in=Device.objects.filter(device_type=dt),
        health_check=True,
        submit_time__gte=(datetime.datetime.now().date() - datetime.timedelta(days=7)),
        submit_time__lt=datetime.datetime.now().date(),
        status=TestJob.COMPLETE).count()
    weekly_failed = TestJob.objects.filter(
        actual_device__in=Device.objects.filter(device_type=dt),
        health_check=True,
        submit_time__gte=(datetime.datetime.now().date() - datetime.timedelta(days=7)),
        submit_time__lt=datetime.datetime.now().date(),
        status=TestJob.INCOMPLETE).count()
    monthly_complete = TestJob.objects.filter(
        actual_device__in=Device.objects.filter(device_type=dt),
        health_check=True,
        submit_time__gte=(datetime.datetime.now().date() - datetime.timedelta(days=30)),
        submit_time__lt=datetime.datetime.now().date(),
        status=TestJob.COMPLETE).count()
    monthly_failed = TestJob.objects.filter(
        actual_device__in=Device.objects.filter(device_type=dt),
        health_check=True,
        submit_time__gte=(datetime.datetime.now().date() - datetime.timedelta(days=30)),
        submit_time__lt=datetime.datetime.now().date(),
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
        "Failed": monthly_failed,
        }
    ]
    #  device capabilities data retrieved from health checks
    capabilities = populate_capabilities(dt)

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
    dt = get_object_or_404(DeviceType, pk=dt)
    dt_jobs_ptable = OverviewJobsTable(
        dt_jobs_data.get_table_data(prefix)
        .filter(actual_device__in=Device.objects.filter(device_type=dt)),
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

    return render_to_response(
        "lava_scheduler_app/device_type.html",
        {
            'device_type': dt,
            'search_data': search_data,
            "discrete_data": discrete_data,
            'terms_data': terms_data,
            'times_data': times_data,
            'capabilities_date': capabilities['capabilities_date'],
            'processor': capabilities['processor'],
            'models': capabilities['models'],
            'cores': capabilities['cores'],
            'emulated': capabilities['emulated'],
            'flags': capabilities['flags'],
            'running_jobs_num': TestJob.objects.filter(
                actual_device__in=Device.objects.filter(device_type=dt),
                status=TestJob.RUNNING).count(),
            'queued_jobs_num': TestJob.objects.filter(
                Q(status=TestJob.SUBMITTED), Q(requested_device_type=dt)
                | Q(requested_device__in=Device.objects.filter(device_type=dt))).count(),
            'health_job_summary_table': health_table,
            'device_type_jobs_table': dt_jobs_ptable,
            'devices_table_no_dt': no_dt_ptable,  # NoDTDeviceTable('devices' kwargs=dict(pk=pk)), params=(dt,)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_type_detail, pk=pk),
            'context_help': BreadCrumbTrail.leading_to(device_type_detail, pk='help'),
        },
        RequestContext(request))


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

    return render_to_response(
        "lava_scheduler_app/devicetype_reports.html",
        {
            'device_type': device_type,
            'health_week_report': health_week_report,
            'health_day_report': health_day_report,
            'job_week_report': job_week_report,
            'job_day_report': job_day_report,
            'long_running': long_running,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_type_reports, pk=pk),
        },
        RequestContext(request))


@BreadCrumb("All Device Health", parent=index)
def lab_health(request):
    data = DeviceTableView(request, model=Device, table_class=DeviceHealthTable)
    ptable = DeviceHealthTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render_to_response(
        "lava_scheduler_app/labhealth.html",
        {
            'device_health_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(lab_health),
        },
        RequestContext(request))


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

    return render_to_response(
        "lava_scheduler_app/health_jobs.html",
        {
            'device': device,
            "terms_data": terms_data,
            "search_data": search_data,
            "discrete_data": discrete_data,
            "times_data": times_data,
            'transition_table': trans_table,
            'health_job_table': health_table,
            'show_forcehealthcheck': device.can_admin(request.user) and
            device.status not in [Device.RETIRED] and device.device_type.health_check_job != "",
            'can_admin': device.can_admin(request.user),
            'show_maintenance': device.can_admin(request.user) and
            device.status in [Device.IDLE, Device.RUNNING, Device.RESERVED],
            'edit_description': device.can_admin(request.user),
            'show_online': device.can_admin(request.user) and
            device.status in [Device.OFFLINE, Device.OFFLINING],
            'bread_crumb_trail': BreadCrumbTrail.leading_to(health_job_list, pk=pk),
        },
        RequestContext(request))


class MyJobsView(JobTableView):

    def get_queryset(self):
        jobs = TestJob.objects.select_related("actual_device", "requested_device",
                                              "requested_device_type", "group")\
            .extra(select={'device_sort': 'coalesce(actual_device_id, '
                                          'requested_device_id, requested_device_type_id)',
                           'duration_sort': 'end_time - start_time'}).all()\
            .filter(submitter=self.request.user)
        return jobs.order_by('-submit_time')


class AllJobsView(JobTableView):

    def get_queryset(self):
        return all_jobs_with_custom_sort()


@BreadCrumb("All Jobs", parent=index)
def job_list(request):

    data = AllJobsView(request, model=TestJob, table_class=JobTable)
    ptable = JobTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)

    return render_to_response(
        "lava_scheduler_app/alljobs.html",
        {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(job_list),
            'alljobs_table': ptable,
            "length": ptable.length,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
        RequestContext(request))


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
        if request.is_ajax():
            try:
                validate_job_json(request.POST.get("json-input"))
                return HttpResponse(simplejson.dumps("success"))
            except Exception as e:
                return HttpResponse(simplejson.dumps(str(e)),
                                    mimetype="application/json")

        else:
            try:
                json_data = request.POST.get("json-input")
                job = TestJob.from_json_and_user(json_data, request.user)

                if isinstance(job, type(list())):
                    response_data["job_list"] = [j.sub_id for j in job]
                else:
                    response_data["job_id"] = job.id
                return render_to_response(
                    "lava_scheduler_app/job_submit.html",
                    response_data, RequestContext(request))

            except (JSONDataError, ValueError, DevicesUnavailableException) \
                    as e:
                response_data["error"] = str(e)
                response_data["context_help"] = "lava scheduler submit job",
                response_data["json_input"] = request.POST.get("json-input")
                return render_to_response(
                    "lava_scheduler_app/job_submit.html",
                    response_data, RequestContext(request))

    else:
        return render_to_response(
            "lava_scheduler_app/job_submit.html",
            response_data, RequestContext(request))


@BreadCrumb("Job", parent=index, needs=['pk'])
def job_detail(request, pk):
    job = get_restricted_job(request.user, pk)

    data = {
        'job': job,
        'show_cancel': job.can_cancel(request.user),
        'show_failure': job.can_annotate(request.user),
        'show_resubmit': job.can_resubmit(request.user),
        'bread_crumb_trail': BreadCrumbTrail.leading_to(job_detail, pk=pk),
        'show_reload_page': job.status <= TestJob.RUNNING,
        'change_priority': job.can_change_priority(request.user),
        'context_help': BreadCrumbTrail.leading_to(job_detail, pk='detail'),
    }

    log_file = job.output_file()

    if log_file:
        if not job.failure_comment:
            job_errors = getDispatcherErrors(job.output_file())
            if len(job_errors) > 0:
                msg = "".join(job_errors).strip()
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
        with job.output_file() as f:
            f.seek(0, 2)
            job_file_size = f.tell()
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

    return render_to_response(
        "lava_scheduler_app/job.html", data, RequestContext(request))


def job_definition(request, pk):
    job = get_restricted_job(request.user, pk)
    log_file = job.output_file()
    return render_to_response(
        "lava_scheduler_app/job_definition.html",
        {
            'job': job,
            'job_file_present': bool(log_file),
            'show_cancel': job.can_cancel(request.user),
            'show_resubmit': job.can_resubmit(request.user),
        },
        RequestContext(request))


def job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk)
    response = HttpResponse(job.display_definition, mimetype='text/plain')
    response['Content-Disposition'] = "attachment; filename=job_%d.json" % \
        job.id
    return response


def multinode_job_definition(request, pk):
    job = get_restricted_job(request.user, pk)
    log_file = job.output_file()
    return render_to_response(
        "lava_scheduler_app/multinode_job_definition.html",
        {
            'job': job,
            'job_file_present': bool(log_file),
            'show_cancel': job.can_cancel(request.user),
            'show_resubmit': job.can_resubmit(request.user),
        },
        RequestContext(request))


def multinode_job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk)
    response = HttpResponse(job.multinode_definition, mimetype='text/plain')
    response['Content-Disposition'] = \
        "attachment; filename=multinode_job_%d.json" % job.id
    return response


def vmgroup_job_definition(request, pk):
    job = get_restricted_job(request.user, pk)
    log_file = job.output_file()
    return render_to_response(
        "lava_scheduler_app/vmgroup_job_definition.html",
        {
            'job': job,
            'job_file_present': bool(log_file),
        },
        RequestContext(request))


def vmgroup_job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk)
    response = HttpResponse(job.vmgroup_definition, mimetype='text/plain')
    response['Content-Disposition'] = \
        "attachment; filename=vmgroup_job_%d.json" % job.id
    return response


@BreadCrumb("My Jobs", parent=index)
def myjobs(request):
    data = MyJobsView(request, model=TestJob, table_class=JobTable)
    ptable = JobTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render_to_response(
        "lava_scheduler_app/myjobs.html",
        {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(myjobs),
            'myjobs_table': ptable,
            "terms_data": ptable.prepare_terms_data(data),
            "search_data": ptable.prepare_search_data(data),
            "discrete_data": ptable.prepare_discrete_data(data),
            "times_data": ptable.prepare_times_data(data),
        },
        RequestContext(request))


@BreadCrumb("Complete log", parent=job_detail, needs=['pk'])
def job_log_file(request, pk):
    job = get_restricted_job(request.user, pk)
    content = formatLogFile(job.output_file())
    with job.output_file() as f:
        f.seek(0, 2)
        job_file_size = f.tell()
    return render_to_response(
        "lava_scheduler_app/job_log_file.html",
        {
            'show_cancel': job.can_cancel(request.user),
            'show_resubmit': job.can_resubmit(request.user),
            'job': TestJob.objects.get(pk=pk),
            'job_file_present': bool(job.output_file()),
            'sections': content,
            'job_file_size': job_file_size,
        },
        RequestContext(request))


def job_log_file_plain(request, pk):
    job = get_restricted_job(request.user, pk)
    response = HttpResponse(job.output_file(), mimetype='text/plain')
    response['Content-Disposition'] = "attachment; filename=job_%d.log" % job.id
    return response


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


@post_only
def job_cancel(request, pk):
    job = get_restricted_job(request.user, pk)
    if job.can_cancel(request.user):
        if job.is_multinode:
            multinode_jobs = TestJob.objects.all().filter(
                target_group=job.target_group)
            for multinode_job in multinode_jobs:
                multinode_job.cancel(request.user)
        elif job.is_vmgroup:
            vmgroup_jobs = TestJob.objects.all().filter(
                vm_group=job.vm_group)
            for vmgroup_job in vmgroup_jobs:
                vmgroup_job.cancel(request.user)
        else:
            job.cancel(request.user)
        return redirect(job)
    else:
        return HttpResponseForbidden(
            "you cannot cancel this job", content_type="text/plain")


@post_only
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
                job = TestJob.from_json_and_user(
                    request.POST.get("json-input"), request.user)

                if isinstance(job, type(list())):
                    response_data["job_list"] = [j.sub_id for j in job]
                else:
                    response_data["job_id"] = job.id
                return render_to_response(
                    "lava_scheduler_app/job_submit.html",
                    response_data, RequestContext(request))

            except (JSONDataError, ValueError, DevicesUnavailableException) \
                    as e:
                response_data["error"] = str(e)
                response_data["json_input"] = request.POST.get("json-input")
                return render_to_response(
                    "lava_scheduler_app/job_submit.html",
                    response_data, RequestContext(request))
        else:
            if request.is_ajax():
                try:
                    validate_job_json(request.POST.get("json-input"))
                    return HttpResponse(simplejson.dumps("success"))
                except Exception as e:
                    return HttpResponse(simplejson.dumps(str(e)),
                                        mimetype="application/json")
            if job.is_multinode:
                definition = job.multinode_definition
            elif job.is_vmgroup:
                definition = job.vmgroup_definition
            else:
                definition = job.display_definition

            if request.user != job.owner and not request.user.is_superuser:
                obj = simplejson.loads(definition)

                # Iterate through the objects in the JSON and pop (remove)
                # the submit_results action once we find it.
                for key in obj:
                    if key == "actions":
                        for i in xrange(len(obj[key])):
                            if obj[key][i]["command"] == \
                                    "submit_results_on_host" or \
                                    obj[key][i]["command"] == "submit_results":
                                obj[key].pop(i)
                                break
                definition = simplejson.dumps(obj, sort_keys=True, indent=4, separators=(',', ': '))

            try:
                response_data["json_input"] = definition
                return render_to_response(
                    "lava_scheduler_app/job_submit.html",
                    response_data, RequestContext(request))
            except (JSONDataError, ValueError, DevicesUnavailableException) \
                    as e:
                response_data["error"] = str(e)
                response_data["json_input"] = definition
                return render_to_response(
                    "lava_scheduler_app/job_submit.html",
                    response_data, RequestContext(request))

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

    return render_to_response(
        "lava_scheduler_app/job_annotate_failure.html",
        {
            'form': form,
            'job': job,
        },
        RequestContext(request))


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
def get_remote_json(request):
    """Fetches remote json file."""
    url = request.POST.get("url")

    try:
        data = urllib2.urlopen(url).read()
        # Validate that the data at the location is really JSON.
        # This is security based check so noone can misuse this url.
        simplejson.loads(data)
    except Exception as e:
        return HttpResponse(simplejson.dumps(str(e)),
                            mimetype="application/json")

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
    if len(device_type.devices_visible_to(request.user)) == 0:
        raise Http404()
    trans_data = TransitionView(request, transition.device, model=DeviceStateTransition, table_class=DeviceTransitionTable)
    trans_table = DeviceTransitionTable(trans_data.get_table_data())
    config = RequestConfig(request, paginate={"per_page": trans_table.length})
    config.configure(trans_table)

    return render_to_response(
        "lava_scheduler_app/transition.html",
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
        RequestContext(request))


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
            '-created_on'
        )


@BreadCrumb("Device {pk}", parent=index, needs=['pk'])
def device_detail(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.device_type.owners_only:
        visible = filter_device_types(request.user)
        if not device.device_type.name in visible:
            raise Http404('No device matches the given query.')

    devices = Device.objects.filter(device_type_id=device.device_type_id).order_by('hostname')
    devices_list = [dev[0] for dev in devices.values_list('hostname')]
    try:
        next_device = devices_list[devices_list.index(device.hostname) + 1]
    except IndexError:
        next_device = None
    try:
        previous_device = devices_list[:devices_list.index(device.hostname)].pop()
    except IndexError:
        previous_device = None

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

    visible = filter_device_types(request.user)

    return render_to_response(
        "lava_scheduler_app/device.html",
        {
            'device': device,
            "times_data": times_data,
            "terms_data": terms_data,
            "search_data": search_data,
            "discrete_data": discrete_data,
            'transition': transition,
            'transition_table': trans_table,
            'recent_job_table': recent_ptable,
            'show_forcehealthcheck': device.can_admin(request.user) and
            device.status not in [Device.RETIRED] and device.device_type.health_check_job != "",
            'can_admin': device.can_admin(request.user),
            'show_maintenance': device.can_admin(request.user) and
            device.status in [Device.IDLE, Device.RUNNING, Device.RESERVED],
            'edit_description': device.can_admin(request.user),
            'show_online': (device.can_admin(request.user) and
                            device.status in [Device.OFFLINE, Device.OFFLINING]),
            'show_restrict': (device.is_public and device.can_admin(request.user)
                              and device.status not in [Device.RETIRED]),
            'show_pool': (not device.is_public and device.can_admin(request.user)
                          and device.status not in [Device.RETIRED]
                          and not device.device_type.owners_only),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_detail, pk=pk),
            'context_help': BreadCrumbTrail.show_help(device_detail, pk="help"),
            'next_device': next_device,
            'previous_device': previous_device,
        },
        RequestContext(request))


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

    return render_to_response(
        "lava_scheduler_app/device_reports.html",
        {
            'device': device,
            'health_week_report': health_week_report,
            'health_day_report': health_day_report,
            'job_week_report': job_week_report,
            'job_day_report': job_day_report,
            'long_running': long_running,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_reports, pk=pk),
        },
        RequestContext(request))


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
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        job = device.initiate_health_check_job()
        return redirect(job)
    else:
        return HttpResponseForbidden(
            "you cannot administer this device", content_type="text/plain")


def device_edit_description(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        device.description = request.POST.get('desc')
        device.save()
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot edit the description of this device", content_type="text/plain")


@post_only
def device_restrict_device(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        message = "Restriction added: %s" % request.POST.get('reason')
        device.is_public = False
        DeviceStateTransition.objects.create(
            created_by=request.user, device=device, old_state=device.status,
            new_state=device.status, message=message, job=None).save()
        device.save()
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot restrict submissions to this device", content_type="text/plain")


@post_only
def device_derestrict_device(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        message = "Restriction removed: %s" % request.POST.get('reason')
        device.is_public = True
        DeviceStateTransition.objects.create(
            created_by=request.user, device=device, old_state=device.status,
            new_state=device.status, message=message, job=None).save()
        device.save()
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot derestrict submissions to this device", content_type="text/plain")


@BreadCrumb("Worker: {pk}", parent=index, needs=['pk'])
def worker_detail(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    data = DeviceTableView(request)
    ptable = NoWorkerDeviceTable(data.get_table_data().filter(worker_host=worker).order_by('hostname'))
    RequestConfig(request, paginate={"per_page": ptable.length}).configure(ptable)
    return render_to_response(
        "lava_scheduler_app/worker.html",
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
        RequestContext(request))


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

    return render_to_response(
        "lava_scheduler_app/queue.html",
        {
            "times_data": queue_ptable.prepare_times_data(queue_data),
            "terms_data": queue_ptable.prepare_terms_data(queue_data),
            "search_data": queue_ptable.prepare_search_data(queue_data),
            "discrete_data": queue_ptable.prepare_discrete_data(queue_data),
            'queue_table': queue_ptable,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(queue),
        },
        RequestContext(request))
