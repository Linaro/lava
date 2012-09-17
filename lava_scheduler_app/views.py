from collections import defaultdict
import logging
import os
import simplejson
import StringIO
import datetime
from dateutil.relativedelta import relativedelta

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

from django_tables2 import Attrs, Column

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
    Tag,
    Device,
    DeviceType,
    DeviceStateTransition,
    TestJob,
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
    return mark_safe(
        '<a href="%s">%s</a>' % (
            record.get_absolute_url(),
            escape(record.pk)))


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
    return TestJob.objects.select_related(
        "actual_device", "requested_device", "requested_device_type",
        "submitter", "user", "group").extra(
        select={
            'device_sort': 'coalesce(actual_device_id, requested_device_id, requested_device_type_id)'
            }).all()



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

    id = RestrictedIDLinkColumn()
    status = Column()
    device = Column(accessor='device_sort')
    description = Column(attrs=Attrs(width="30%"))
    submitter = Column()
    submit_time = DateColumn()
    end_time = DateColumn()

    datatable_opts = {
        'aaSorting': [[0, 'desc']],
        }
    searchable_columns=['description']


class IndexJobTable(JobTable):
    def get_queryset(self):
        return all_jobs_with_device_sort().filter(
            status__in=[TestJob.SUBMITTED, TestJob.RUNNING])

    class Meta:
        exclude = ('end_time',)


def index_active_jobs_json(request):
    return IndexJobTable.json(request)


class DeviceTable(DataTablesTable):

    def get_queryset(self):
        return Device.objects.select_related("device_type")

    hostname = IDLinkColumn("hostname")
    device_type = Column()
    status = Column()
    health_status = Column()

    searchable_columns=['hostname']


def index_devices_json(request):
    return DeviceTable.json(request)

def health_jobs_in_hr(hr=-24):
    return TestJob.objects.filter(health_check=True,
           start_time__gte=(datetime.datetime.now()
               + relativedelta(hours=hr))).exclude(status__in=[TestJob.SUBMITTED, TestJob.RUNNING])

def _online_total():
    ''' returns a tuple of (num_online, num_not_retired) '''
    r = Device.objects.all().values('status').annotate(count=Count('status'))
    offline = total = 0
    for res in r:
        if res['status'] in [Device.OFFLINE, Device.OFFLINING]:
            offline += res['count']
        if res['status'] != Device.RETIRED:
            total += res['count']

    return (total-offline,total)

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

    res = TestJob.objects.filter(
            health_check=health_check,
            start_time__range=(start_date, end_date),
            status__in=(
                TestJob.COMPLETE,
                TestJob.INCOMPLETE, TestJob.CANCELED, TestJob.CANCELING),
        ).values(
            'status'
        )
    return {
        'pass': res.filter(status=TestJob.COMPLETE).count(),
        'fail': res.exclude(status=TestJob.COMPLETE).count(),
        'date': start_date.strftime('%m-%d'),
    }

@BreadCrumb("Reports", parent=lava_index)
def reports(request):
    health_day_report = []
    health_week_report = []
    job_day_report = []
    job_week_report = []
    for day in reversed(range(7)):
        health_day_report.append(job_report(day*-1-1, day*-1, True))
        job_day_report.append(job_report(day*-1-1, day*-1, False))
    for week in reversed(range(10)):
        health_week_report.append(job_report(week*-7-7, week*-7, True))
        job_week_report.append(job_report(week*-7-7, week*-7, False))

    long_running = TestJob.objects.filter(
            status__in = [TestJob.RUNNING, TestJob.CANCELING]
        ).order_by('start_time')[:5]

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
    job =  get_object_or_404(TestJob.objects, pk=pk)
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
        aggregate = SumIfSQL(
                col, source=source, is_summary=is_summary, **self.extra)
        query.aggregates[alias] = aggregate

class DeviceTypeTable(DataTablesTable):

    def get_queryset(self):
        return DeviceType.objects.filter(display=True).annotate(
            idle=SumIf('device', condition='status=%s' % Device.IDLE),
            offline=SumIf('device', condition='status in (%s,%s)' % (
                Device.OFFLINE, Device.OFFLINING)),
            busy=SumIf('device', condition='status=%s' % Device.RUNNING),
            ).order_by('name')

    def render_status(self, record):
        return "%s idle, %s offline, %s busy" % (record.idle, record.offline,
                record.busy)

    name = IDLinkColumn("name")
    status = Column()

    searchable_columns = ['name']


class HealthJobSummaryTable(DataTablesTable):
    """
    The Table will return 1 day, 1 week, 1 month offset health job count.
    The value is defined when table instance is created in device_type_detail()
    """

    def render_Duration(self, record):
        matrix = {-24:"24hours", -24*7:"Week", -24*7*30:"Month"}
        return matrix[record]

    def render_Complete(self, record):
        device_type = self.params[0]
        num = health_jobs_in_hr(record).filter(
                actual_device__in=Device.objects.filter(
                device_type=device_type), status=TestJob.COMPLETE).count()
        return num

    def render_Failed(self, record):
        device_type = self.params[0]
        num = health_jobs_in_hr(record).filter(
                actual_device__in=Device.objects.filter(
                device_type=device_type), status__in=[TestJob.INCOMPLETE,
                    TestJob.CANCELED, TestJob.CANCELING]).count()
        return num

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
    return render_to_response(
        "lava_scheduler_app/device_type.html",
        {
            'device_type': dt,
            'running_jobs_num': TestJob.objects.filter(
                actual_device__in=Device.objects.filter(device_type=dt),
                status=TestJob.RUNNING).count(),
            'queued_jobs_num': TestJob.objects.filter(
                Q(status=TestJob.SUBMITTED), Q(requested_device_type=dt)
                | Q(requested_device__in=Device.objects.filter(device_type=dt))
                ).count(),
            # data return 1 day, 1 week, 1 month offset
            'health_job_summary_table': HealthJobSummaryTable(
                'device_type', params=(dt,), data=[-24, -24*7, -24*7*30]),
            'devices_table_no_dt': NoDTDeviceTable('devices',
                reverse(index_nodt_devices_json, kwargs=dict(pk=pk)), params=(dt,)),
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

    searchable_columns=['hostname']
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
        return TestJob.objects.select_related(
            "submitter",
            ).filter(
            actual_device=device,
            health_check=True)

    class Meta:
        exclude = ('description', 'device')


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
            'show_maintenance': device.can_admin(request.user) and \
                device.status in [Device.IDLE, Device.RUNNING],
            'show_online': device.can_admin(request.user) and \
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


@BreadCrumb("Job #{pk}", parent=index, needs=['pk'])
def job_detail(request, pk):
    job = get_restricted_job(request.user, pk)

    data = {
        'job': job,
        'show_cancel': job.status <= TestJob.RUNNING and job.can_cancel(request.user),
        'bread_crumb_trail': BreadCrumbTrail.leading_to(job_detail, pk=pk),
        'show_reload_page' : job.status <= TestJob.RUNNING,
    }

    log_file = job.log_file
    if log_file:
        try:
            log_file.open()
        except IOError:
            log_file = None

    if log_file:
        job_errors = getDispatcherErrors(log_file)
        job_log_messages = getDispatcherLogMessages(log_file)

        levels = defaultdict(int)
        for kl in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            levels[kl] = 0
        for level, msg, _ in job_log_messages:
            levels[level] += 1
        levels = sorted(levels.items(), key=lambda (k,v):logging._levelNames.get(k))
        data.update({
            'job_file_present': True,
            'job_errors' : job_errors,
            'job_has_error' : len(job_errors) > 0,
            'job_log_messages' : job_log_messages,
            'levels': levels,
            'job_file_size' : log_file.size,
            })
    else:
        data.update({
            'job_file_present': False,
            })

    return render_to_response(
        "lava_scheduler_app/job.html", data, RequestContext(request))


def job_definition(request, pk):
    job = get_restricted_job(request.user, pk)
    log_file = job.log_file
    if log_file:
        try:
            log_file.open()
        except IOError:
            log_file = None
    return render_to_response(
        "lava_scheduler_app/job_definition.html",
        {
            'job': job,
            'job_file_present': bool(log_file),
        },
        RequestContext(request))


def job_definition_plain(request, pk):
    job = get_restricted_job(request.user, pk)
    response = HttpResponse(job.definition, mimetype='text/plain')
    response['Content-Disposition'] = "attachment; filename=job_%d.json"%job.id
    return response


@BreadCrumb("Complete log", parent=job_detail, needs=['pk'])
def job_log_file(request, pk):
    job = get_restricted_job(request.user, pk)
    content = formatLogFile(job.log_file)
    return render_to_response(
        "lava_scheduler_app/job_log_file.html",
        {
            'job': TestJob.objects.get(pk=pk),
            'job_file_present': bool(job.log_file),
            'sections' : content,
            'job_file_size' : job.log_file.size,
        },
        RequestContext(request))


def job_log_file_plain(request, pk):
    job = get_restricted_job(request.user, pk)
    response = HttpResponse(job.log_file, mimetype='text/plain')
    response['Content-Disposition'] = "attachment; filename=job_%d.log"%job.id
    return response


def job_log_incremental(request, pk):
    start = int(request.GET.get('start', 0))
    job = get_restricted_job(request.user, pk)
    log_file = job.log_file
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
    log_file = job.log_file
    log_file.seek(start)
    new_content = log_file.read()
    nl_index = new_content.rfind('\n', -NEWLINE_SCAN_SIZE)
    if nl_index >= 0:
        new_content = new_content[:nl_index+1]
    m = formatLogFile(StringIO.StringIO(new_content))
    response = HttpResponse(
        simplejson.dumps(m), content_type='application/json')
    response['X-Current-Size'] = str(start + len(new_content))
    if job.status not in [TestJob.RUNNING, TestJob.CANCELING]:
        response['X-Is-Finished'] = '1'
    return response


LOG_CHUNK_SIZE = 512*1024
NEWLINE_SCAN_SIZE = 80


def job_output(request, pk):
    start = request.GET.get('start', 0)
    try:
        start = int(start)
    except ValueError:
        return HttpResponseBadRequest("invalid start")
    count_present = 'count' in request.GET
    job = get_restricted_job(request.user, pk)
    log_file = job.log_file
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
        content = content[:nl_index+1]
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
        job.cancel()
        return redirect(job)
    else:
        return HttpResponseForbidden(
            "you cannot cancel this job", content_type="text/plain")


def job_json(request, pk):
    job = get_restricted_job(request.user, pk)
    json_text = simplejson.dumps({
        'status': job.get_status_display(),
        'results_link': job.results_link,
        })
    content_type = 'application/json'
    if 'callback' in request.GET:
        json_text = '%s(%s)'%(request.GET['callback'], json_text)
        content_type = 'text/javascript'
    return HttpResponse(json_text, content_type=content_type)


class RecentJobsTable(JobTable):

    def get_queryset(self, device):
        return device.recent_jobs()

    class Meta:
        exclude = ('device',)


def recent_jobs_json(request, pk):
    device = get_object_or_404(Device, pk=pk)
    return RecentJobsTable.json(request, params=(device,))


class DeviceTransitionTable(DataTablesTable):

    def get_queryset(self, device):
        qs = device.transitions.select_related('created_by')
        qs = qs.extra(select={'prev': """
        select t.created_on
          from lava_scheduler_app_devicestatetransition as t
         where t.device_id=%s and t.created_on < lava_scheduler_app_devicestatetransition.created_on
         order by t.created_on desc
         limit 1 """},
                      select_params=[device.pk])
        return qs

    def render_created_on(self, record):
        t = record
        base = filters.date(t.created_on, "Y-m-d H:i")
        if t.prev:
            base += ' (after %s)' % (filters.timesince(t.prev, t.created_on))
        return base

    def render_transition(self, record):
        t = record
        return mark_safe(
            '%s &rarr; %s' % (t.get_old_state_display(), t.get_new_state_display(),))

    def render_message(self, value):
        if value is None:
            return ''
        else:
            return value

    created_on = Column('when', attrs=Attrs(width="40%"))
    transition = Column('transition', sortable=False)
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
            'show_maintenance': device.can_admin(request.user) and \
                device.status in [Device.IDLE, Device.RUNNING],
            'show_online': device.can_admin(request.user) and \
                device.status in [Device.OFFLINE, Device.OFFLINING],
            'bread_crumb_trail': BreadCrumbTrail.leading_to(device_detail, pk=pk),
        },
        RequestContext(request))


@post_only
def device_maintenance_mode(request, pk):
    device = Device.objects.get(pk=pk)
    if device.can_admin(request.user):
        device.put_into_maintenance_mode(request.user, request.POST.get('reason'))
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

