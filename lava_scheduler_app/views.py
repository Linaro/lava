from collections import defaultdict
import logging
import os
import simplejson
import StringIO
import datetime
import urllib2
from dateutil.relativedelta import relativedelta

from django import forms

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render_to_response,
)
from django.template import RequestContext
from django.template import defaultfilters as filters
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.db import models
from django.db.models import Q

from django_tables2 import Attrs, Column, TemplateColumn

from lava.utils.data_tables.tables import DataTablesTable

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
    User,
)


def post_only(func):
    def decorated(request, *args, **kwargs):
        if request.method != 'POST':
            return HttpResponseNotAllowed('Only POST here')
        return func(request, *args, **kwargs)
    return decorated


class DateColumn(Column):

    def __init__(self, **kw):
        self._format = kw.get('date_format', settings.DATETIME_FORMAT)
        super(DateColumn, self).__init__(**kw)

    def render(self, value):
        return filters.date(value, self._format)


def pklink(record):
    job_id = record.pk
    try:
        if record.sub_id:
            job_id = record.sub_id
    except:
        pass
    return mark_safe(
        '<a href="%s">%s</a>' % (
            record.get_absolute_url(),
            escape(job_id)))


class IDLinkColumn(Column):

    def __init__(self, verbose_name="ID", **kw):
        kw['verbose_name'] = verbose_name
        super(IDLinkColumn, self).__init__(**kw)

    def render(self, record):
        return pklink(record)


class RestrictedIDLinkColumn(IDLinkColumn):

    def render(self, record, table):
        if record.is_accessible_by(table.context.get('request').user):
            return pklink(record)
        else:
            return record.pk


def all_jobs_with_device_sort():
    jobs = TestJob.objects.select_related("actual_device", "requested_device",
                                          "requested_device_type", "submitter", "user", "group")\
        .extra(select={'device_sort': 'coalesce(actual_device_id, '
                                      'requested_device_id, requested_device_type_id)'}).all()
    return jobs.order_by('submit_time')


def my_jobs_with_device_sort(user):
    jobs = TestJob.objects.select_related("actual_device", "requested_device",
                                          "requested_device_type", "group")\
        .extra(select={'device_sort': 'coalesce(actual_device_id, '
                                      'requested_device_id, requested_device_type_id)'}).all()\
        .filter(submitter=user)
    return jobs.order_by('submit_time')


class JobTable(DataTablesTable):

    def render_device(self, record):
        if record.actual_device:
            return pklink(record.actual_device)
        elif record.requested_device:
            return pklink(record.requested_device)
        else:
            return mark_safe(
                '<i>' + escape(record.requested_device_type.pk) + '</i>')

    def render_description(self, value):
        if value:
            return value
        else:
            return ''

    sub_id = RestrictedIDLinkColumn(accessor='id')
    status = Column()
    priority = Column()
    device = Column(accessor='device_sort')
    description = Column(attrs=Attrs(width="30%"))
    submitter = Column()
    submit_time = DateColumn()
    end_time = DateColumn()
    duration = Column()

    datatable_opts = {
        'aaSorting': [[6, 'desc']],
    }
    searchable_columns = ['description']


class IndexJobTable(JobTable):
    def get_queryset(self):
        return all_jobs_with_device_sort()\
            .filter(status__in=[TestJob.SUBMITTED, TestJob.RUNNING])

    class Meta:
        exclude = ('end_time',)

    datatable_opts = JobTable.datatable_opts.copy()

    datatable_opts.update({
        'iDisplayLength': 25,
    })


def index_active_jobs_json(request):
    return IndexJobTable.json(request)


class ExpandedStatusColumn(Column):

    def __init__(self, verbose_name="Expanded Status", **kw):
        kw['verbose_name'] = verbose_name
        super(ExpandedStatusColumn, self).__init__(**kw)

    def render(self, record):
        if record.status == Device.RUNNING:
            return mark_safe("Running job #%s - %s submitted by %s" % (
                             pklink(record.current_job),
                             record.current_job.description,
                             record.current_job.submitter))
        else:
            return Device.STATUS_CHOICES[record.status][1]


class DeviceTable(DataTablesTable):

    def get_queryset(self):
        return Device.objects.select_related("device_type")

    hostname = TemplateColumn('''
    {% if record.status == record.UNREACHABLE %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-offline-icon.png"
          alt="{{ record.last_heartbeat }}" />
    {% elif record.status == record.RETIRED or record.status == record.OFFLINE        or record.status == record.OFFLINING %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-offline-icon.png"
          alt="NA" />
    {% else %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-available-icon.png"
          alt="{{ record.last_heartbeat }}" />
    {% endif %}&nbsp;&nbsp;
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
        ''')
    worker_hostname = Column()
    device_type = Column()
    status = ExpandedStatusColumn("status")
    health_status = Column()

    searchable_columns = ['hostname']


def index_devices_json(request):
    return DeviceTable.json(request)


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


@BreadCrumb("Scheduler", parent=lava_index)
def index(request):
    return render_to_response(
        "lava_scheduler_app/index.html",
        {
            'device_status': "%d/%d" % _online_total(),
            'health_check_status': "%s/%s" % (
                health_jobs_in_hr().filter(status=TestJob.COMPLETE).count(),
                health_jobs_in_hr().count()),
            'device_type_table': DeviceTypeTable('devicetype', reverse(device_type_json)),
            'devices_table': DeviceTable('devices', reverse(index_devices_json)),
            'active_jobs_table': IndexJobTable(
                'active_jobs', reverse(index_active_jobs_json)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
        },
        RequestContext(request))


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


class TagsColumn(Column):

    def render(self, value):
        return ', '.join([x.name for x in value.all()])


class FailedJobTable(JobTable):
    failure_tags = TagsColumn()
    failure_comment = Column()

    def get_queryset(self, request):
        failures = [TestJob.INCOMPLETE, TestJob.CANCELED, TestJob.CANCELING]
        jobs = TestJob.objects.filter(status__in=failures)

        health = request.GET.get('health_check', None)
        if health:
            jobs = jobs.filter(health_check=_str_to_bool(health))

        dt = request.GET.get('device_type', None)
        if dt:
            jobs = jobs.filter(actual_device__device_type__name=dt)

        device = request.GET.get('device', None)
        if device:
            jobs = jobs.filter(actual_device__hostname=device)

        start = request.GET.get('start', None)
        if start:
            now = datetime.datetime.now()
            start = now + datetime.timedelta(int(start))

            end = request.GET.get('end', None)
            if end:
                end = now + datetime.timedelta(int(end))
                jobs = jobs.filter(start_time__range=(start, end))
        return jobs

    class Meta:
        exclude = ('status', 'submitter', 'end_time', 'priority', 'description')

    datatable_opts = {
        'aaSorting': [[2, 'desc']],
    }


def failed_jobs_json(request):
    return FailedJobTable.json(request, params=(request,))


def _str_to_bool(string):
    return string.lower() in ['1', 'true', 'yes']


@BreadCrumb("Failure Report", parent=reports)
def failure_report(request):
    return render_to_response(
        "lava_scheduler_app/failure_report.html",
        {
            'failed_job_table': FailedJobTable(
                'failure_report',
                reverse(failed_jobs_json),
                params=(request,)
            ),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(reports),
        },
        RequestContext(request))


@BreadCrumb("All Devices", parent=index)
def device_list(request):
    return render_to_response(
        "lava_scheduler_app/alldevices.html",
        {
            'devices_table': DeviceTable('devices', reverse(index_devices_json)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_list),
        },
        RequestContext(request))


def get_restricted_job(user, pk):
    """Returns JOB which is a TestJob object after checking for USER
    accessibility to the object.
    """
    job = TestJob.get_by_job_number(pk)

    if not job.is_accessible_by(user):
        raise PermissionDenied()
    return job


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


class DeviceTypeTable(DataTablesTable):

    def get_queryset(self):
        return DeviceType.objects.filter(display=True)\
            .annotate(idle=SumIf('device', condition='status=%s' % Device.IDLE),
                      offline=SumIf('device', condition='status in (%s,%s)' %
                                                        (Device.OFFLINE, Device.OFFLINING)),
                      busy=SumIf('device', condition='status in (%s,%s)' %
                                                     (Device.RUNNING, Device.RESERVED)),).order_by('name')

    def render_display(self, record):
        return "%d idle, %d offline, %d busy" % (record.idle,
                                                 record.offline, record.busy)

    datatable_opts = {
        "iDisplayLength": 50
    }

    name = IDLinkColumn("name")
    # columns must match fields which actually exist in the relevant table.
    display = Column()

    searchable_columns = ['name']


class HealthJobSummaryTable(DataTablesTable):

    Duration = Column()
    Complete = Column()
    Failed = Column()


def device_type_json(request):
    return DeviceTypeTable.json(request)


class NoDTDeviceTable(DeviceTable):
    def get_queryset(self, device_type):
        return Device.objects.filter(device_type=device_type)

    class Meta:
        exclude = ('device_type',)


def index_nodt_devices_json(request, pk):
    device_type = get_object_or_404(DeviceType, pk=pk)
    return NoDTDeviceTable.json(request, params=(device_type,))


@BreadCrumb("Device Type {pk}", parent=index, needs=['pk'])
def device_type_detail(request, pk):
    dt = get_object_or_404(DeviceType, pk=pk)
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

    return render_to_response(
        "lava_scheduler_app/device_type.html",
        {
            'device_type': dt,
            'running_jobs_num': TestJob.objects.filter(
                actual_device__in=Device.objects.filter(device_type=dt),
                status=TestJob.RUNNING).count(),
            'queued_jobs_num': TestJob.objects.filter(
                Q(status=TestJob.SUBMITTED), Q(requested_device_type=dt)
                | Q(requested_device__in=Device.objects.filter(device_type=dt))).count(),
            'health_job_summary_table': HealthJobSummaryTable('device_type',
                                                              params=(dt,),
                                                              data=health_summary_data),
            'devices_table_no_dt': NoDTDeviceTable('devices', reverse(index_nodt_devices_json,
                                                                      kwargs=dict(pk=pk)), params=(dt,)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_type_detail, pk=pk),
        },
        RequestContext(request))


class DeviceHealthTable(DataTablesTable):

    def get_queryset(self):
        return Device.objects.select_related(
            "hostname", "last_health_report_job")

    def render_hostname(self, record):
        return mark_safe('<a href="%s">%s</a>' % (
            record.get_device_health_url(), escape(record.pk)))

    def render_last_health_report_job(self, record):
        report = record.last_health_report_job
        if report is None:
            return ''
        else:
            return pklink(report)

    hostname = Column("hostname")
    health_status = Column()
    last_report_time = DateColumn(
        verbose_name="last report time",
        accessor="last_health_report_job.end_time")
    last_health_report_job = Column("last report job")

    searchable_columns = ['hostname']
    datatable_opts = {
        "iDisplayLength": 25
    }


def lab_health_json(request):
    return DeviceHealthTable.json(request)


@BreadCrumb("All Device Health", parent=index)
def lab_health(request):
    return render_to_response(
        "lava_scheduler_app/labhealth.html",
        {
            'device_health_table': DeviceHealthTable(
                'device_health', reverse(lab_health_json)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(lab_health),
        },
        RequestContext(request))


class HealthJobTable(JobTable):

    def get_queryset(self, device):
        return TestJob.objects.select_related("submitter",)\
            .filter(actual_device=device, health_check=True)

    class Meta:
        exclude = ('description', 'device')

    datatable_opts = {
        'aaSorting': [[4, 'desc']],
    }


def health_jobs_json(request, pk):
    device = get_object_or_404(Device, pk=pk)
    return HealthJobTable.json(params=(device,))


@BreadCrumb("All Health Jobs on Device {pk}", parent=index, needs=['pk'])
def health_job_list(request, pk):
    device = get_object_or_404(Device, pk=pk)

    return render_to_response(
        "lava_scheduler_app/health_jobs.html",
        {
            'device': device,
            'transition_table': DeviceTransitionTable(
                'transitions', reverse(transition_json, kwargs=dict(pk=device.pk)),
                params=(device,)),
            'health_job_table': HealthJobTable(
                'health_jobs', reverse(health_jobs_json, kwargs=dict(pk=pk)),
                params=(device,)),
            'show_maintenance': device.can_admin(request.user) and
            device.status in [Device.IDLE, Device.RUNNING, Device.RESERVED],
            'show_online': device.can_admin(request.user) and
            device.status in [Device.OFFLINE, Device.OFFLINING],
            'bread_crumb_trail': BreadCrumbTrail.leading_to(health_job_list, pk=pk),
        },
        RequestContext(request))


class AllJobsTable(JobTable):

    def get_queryset(self):
        return all_jobs_with_device_sort()

    datatable_opts = JobTable.datatable_opts.copy()

    datatable_opts.update({
        'iDisplayLength': 25,
    })


class MyJobsTable(DataTablesTable):

    def render_device(self, record):
        if record.actual_device:
            return pklink(record.actual_device)
        elif record.requested_device:
            return pklink(record.requested_device)
        else:
            return mark_safe(
                '<i>' + escape(record.requested_device_type.pk) + '</i>')

    def render_description(self, value):
        if value:
            return value
        else:
            return ''

    sub_id = RestrictedIDLinkColumn(accessor="id")
    status = Column()
    priority = Column()
    device = Column(accessor='device_sort')
    description = Column(attrs=Attrs(width="30%"))
    submit_time = DateColumn()
    end_time = DateColumn()
    duration = Column()

    datatable_opts = {
        'aaSorting': [[5, 'desc']],
    }
    datatable_opts.update({
        'iDisplayLength': 25,
    })
    searchable_columns = ['description']

    def get_queryset(self, user):
        return my_jobs_with_device_sort(user)


def myjobs_json(request):
    return MyJobsTable.json(request)


def alljobs_json(request):
    return AllJobsTable.json(request)


@BreadCrumb("All Jobs", parent=index)
def job_list(request):
    return render_to_response(
        "lava_scheduler_app/alljobs.html",
        {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(job_list),
            'alljobs_table': AllJobsTable('alljobs', reverse(alljobs_json)),
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
                job = TestJob.from_json_and_user(
                    request.POST.get("json-input"), request.user)

                if isinstance(job, type(list())):
                    response_data["job_list"] = job
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
    }

    log_file = job.output_file()

    if log_file:
        job_errors = getDispatcherErrors(job.output_file())
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
            'job_errors': job_errors,
            'job_has_error': len(job_errors) > 0,
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
        },
        RequestContext(request))


def multinode_job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk)
    response = HttpResponse(job.multinode_definition, mimetype='text/plain')
    response['Content-Disposition'] = \
        "attachment; filename=multinode_job_%d.json" % job.id
    return response


@BreadCrumb("My Jobs", parent=index)
def myjobs(request):
    return render_to_response(
        "lava_scheduler_app/myjobs.html",
        {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(myjobs),
            'myjobs_table': MyJobsTable('myjobs', reverse(myjobs_json),
                                        params=(request.user,)),
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
                multinode_job.cancel()
        else:
            job.cancel()
        return redirect(job)
    else:
        return HttpResponseForbidden(
            "you cannot cancel this job", content_type="text/plain")


@post_only
def job_resubmit(request, pk):

    response_data = {
        'is_authorized': False,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(job_list),
    }

    job = get_restricted_job(request.user, pk)
    if job.can_resubmit(request.user):
        response_data["is_authorized"] = True

        if job.is_multinode:
            definition = job.multinode_definition
        else:
            definition = job.display_definition

        try:
            job = TestJob.from_json_and_user(definition, request.user)

            if isinstance(job, type(list())):
                response_data["job_list"] = job
                return render_to_response(
                    "lava_scheduler_app/job_submit.html",
                    response_data, RequestContext(request))
            else:
                return redirect(job)
        except (JSONDataError, ValueError, DevicesUnavailableException) as e:
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


class RecentJobsTable(JobTable):

    def get_queryset(self, device):
        return device.recent_jobs()

    class Meta:
        exclude = ('device',)

    datatable_opts = {
        'aaSorting': [[5, 'desc']],
    }


def recent_jobs_json(request, pk):
    device = get_object_or_404(Device, pk=pk)
    return RecentJobsTable.json(request, params=(device,))


class DeviceTransitionTable(DataTablesTable):

    def get_queryset(self, device):
        qs = device.transitions.select_related('created_by')
        return qs

    def render_created_on(self, record):
        t = record
        base = filters.date(t.created_on, "Y-m-d H:i")
        return base

    def render_transition(self, record):
        t = record
        return mark_safe(
            '%s &rarr; %s' % (t.get_old_state_display(), t.get_new_state_display(),))

    def render_message(self, value):
        """
        render methods are only called if the value for a cell is determined to be not an empty value.
        When a value is in Column.empty_values, a default value is rendered instead
        (both Column.render and Table.render_FOO are skipped).
        http://django-tables2.readthedocs.org/en/latest/

        :param value: the value for the cell retrieved from the table data
        :return: the non-empty string to return for display
        """
        return value

    created_on = Column('when', attrs=Attrs(width="40%"))
    transition = Column('transition', sortable=False, accessor='old_state')
    created_by = Column('by')
    message = Column('reason')

    datatable_opts = {
        'aaSorting': [[0, 'desc']],
    }


def transition_json(request, pk):
    device = get_object_or_404(Device, pk=pk)
    return DeviceTransitionTable.json(request, params=(device,))


@BreadCrumb("Device {pk}", parent=index, needs=['pk'])
def device_detail(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.status in [Device.OFFLINE, Device.OFFLINING]:
        try:
            transition = device.transitions.filter(message__isnull=False).latest('created_on').message
        except DeviceStateTransition.DoesNotExist:
            transition = None
    else:
        transition = None
    return render_to_response(
        "lava_scheduler_app/device.html",
        {
            'device': device,
            'transition': transition,
            'transition_table': DeviceTransitionTable(
                'transitions', reverse(transition_json, kwargs=dict(pk=device.pk)),
                params=(device,)),
            'recent_job_table': RecentJobsTable(
                'jobs', reverse(recent_jobs_json, kwargs=dict(pk=device.pk)),
                params=(device,)),
            'show_maintenance': device.can_admin(request.user) and
            device.status in [Device.IDLE, Device.RUNNING, Device.RESERVED],
            'show_online': device.can_admin(request.user) and
            device.status in [Device.OFFLINE, Device.OFFLINING],
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_detail, pk=pk),
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
        device.put_into_online_mode(request.user, request.POST.get('reason'))
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot administer this device", content_type="text/plain")


@post_only
def device_looping_mode(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        device.put_into_looping_mode(request.user)
        return redirect(device)
    else:
        return HttpResponseForbidden(
            "you cannot administer this device", content_type="text/plain")
