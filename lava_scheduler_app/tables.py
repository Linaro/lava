from __future__ import unicode_literals

import yaml
import django
import logging
import random
from django.contrib.admin.models import (
    ADDITION,
    CHANGE,
    LogEntry,
)
from django.template import defaultfilters as filters
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.timesince import timesince
import django_tables2 as tables
from lava_scheduler_app.models import (
    TestJob,
    Device,
    DeviceType,
    Worker,
)
from lava_results_app.models import TestCase
from lava.utils.lavatable import LavaTable
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
        kw['verbose_name'] = verbose_name
        super(IDLinkColumn, self).__init__(**kw)

    def render(self, record, table=None):  # pylint: disable=arguments-differ,unused-argument
        return pklink(record)


class RestrictedIDLinkColumn(IDLinkColumn):

    def render(self, record, table=None):
        user = table.context.get('request').user
        if record.can_view(user):
            return pklink(record)
        else:
            return record.pk


def pklink(record):
    job_id = record.pk
    if isinstance(record, TestJob):
        if record.sub_jobs_list:
            job_id = record.sub_id
    return mark_safe(
        '<a href="%s" title="job summary">%s</a>' % (
            record.get_absolute_url(),
            escape(job_id)))


class ExpandedStatusColumn(tables.Column):

    def __init__(self, verbose_name="Expanded Status", **kw):
        kw['verbose_name'] = verbose_name
        super(ExpandedStatusColumn, self).__init__(**kw)

    def render(self, record):
        """
        Expands the device status to include details of the job if the
        device is Reserved or Running. Logs error if reserved or running
        with no current job.
        """
        logger = logging.getLogger('lava_scheduler_app')
        if record.state == Device.STATE_RUNNING:
            current_job = record.current_job()
            return mark_safe("Running job #%s - %s submitted by %s" % (
                pklink(current_job),
                current_job.description,
                current_job.submitter))
        elif record.state == Device.STATE_RESERVED:
            current_job = record.current_job()
            return mark_safe("Reserved for job #%s (%s) \"%s\" submitted by %s" % (
                pklink(current_job),
                current_job.get_state_display(),
                current_job.description,
                current_job.submitter))
        elif record.state == Device.STATE_IDLE and record.health in [Device.HEALTH_BAD, Device.HEALTH_MAINTENANCE, Device.HEALTH_RETIRED]:
            return ""
        else:
            return record.get_simple_state_display()


class RestrictedDeviceColumn(tables.Column):

    def __init__(self, verbose_name="Submissions restricted to", **kw):
        kw['verbose_name'] = verbose_name
        super(RestrictedDeviceColumn, self).__init__(**kw)

    def render(self, record):
        """
        If the strings here are changed, ensure the strings in the restriction_query
        are changed to match.
        :param record: a database record
        :return: a text string describing the restrictions on this device.
        """
        label = None
        if record.health in [Device.HEALTH_BAD, Device.HEALTH_MAINTENANCE, Device.HEALTH_RETIRED]:
            return "no submissions possible."
        if record.is_public:
            return ""
        if record.user:
            label = record.user.email
        if record.group:
            label = "group %s" % record.group
        return label


def all_jobs_with_custom_sort():
    jobs = TestJob.objects.select_related(
        "actual_device",
        "actual_device__user",
        "actual_device__group",
        "actual_device__device_type",
        "requested_device_type",
        "submitter",
        "user",
        "group").extra(select={'device_sort': 'coalesce('
                                              'actual_device_id, '
                                              'requested_device_type_id)',
                               'duration_sort': "date_trunc('second', end_time - start_time)"}).all()
    return jobs.order_by('-submit_time')


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
    def __init__(self, *args, **kwargs):
        super(JobTable, self).__init__(*args, **kwargs)
        self.length = 25

    id = tables.Column(verbose_name="ID")
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html")
    actions.orderable = False
    device = tables.Column(accessor='device_sort')
    duration = tables.Column(accessor='duration_sort')
    duration.orderable = False
    submit_time = tables.DateColumn(format="Nd, g:ia")
    end_time = tables.DateColumn(format="Nd, g:ia")

    def render_state(self, record):
        if record.state == TestJob.STATE_RUNNING:
            return mark_safe('<span class="text-info"><strong>%s</strong></span>' %
                             record.get_state_display())
        elif record.state == TestJob.STATE_FINISHED:
            if record.health == TestJob.HEALTH_UNKNOWN:
                text = 'text-default'
            elif record.health == TestJob.HEALTH_COMPLETE:
                text = 'text-success'
            elif record.health == TestJob.HEALTH_INCOMPLETE:
                text = 'text-danger'
            elif record.health == TestJob.HEALTH_CANCELED:
                text = 'text-warning'
            return mark_safe('<span class="%s"><strong>%s</strong></span>' %
                             (text, record.get_health_display()))
        else:
            return mark_safe('<span class="text-muted"><strong>%s</strong></span>' %
                             record.get_state_display())

    def render_device(self, record):
        if record.actual_device:
            device_type = record.actual_device.device_type
            retval = pklink(record.actual_device)
        elif record.requested_device_type:
            device_type = record.requested_device_type
            retval = mark_safe('<i>%s</i>' % escape(record.requested_device_type.pk))
        elif record.dynamic_connection:
            return 'connection'
        else:
            return '-'
        if not device_type.some_devices_visible_to(self.context.get('request').user):
            return "Unavailable"
        return retval

    def render_description(self, value):  # pylint: disable=no-self-use
        if value:
            return value
        else:
            return ''

    class Meta(LavaTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = TestJob
        # alternatively, use 'fields' value to include specific fields.
        exclude = [
            'is_public',
            'user',
            'group',
            'sub_id',
            'target_group',
            'health_check',
            'definition',
            'original_definition',
            'multinode_definition',
            'admin_notifications',
            'requested_device_type',
            'start_time',
            'log_file',
            'actual_device',
            'health'
        ]
        fields = (
            'id', 'actions', 'state', 'health', 'device',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )
        sequence = (
            'id', 'actions', 'state', 'device',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )
        # filter view functions supporting relational mappings and returning a Q()
        queries = {
            'device_query': "device",  # active_device
            'owner_query': "submitter",  # submitter
            'job_state_query': 'state',
        }
        # fields which can be searched with default __contains queries
        # note the enums cannot be searched this way.
        searches = {
            'id': 'contains',
            'sub_id': 'contains',
            'description': 'contains'
        }
        # dedicated time-based search fields
        times = {
            'submit_time': 'hours',
            'end_time': 'hours',
        }


class IndexJobTable(JobTable):

    id = tables.Column(verbose_name="ID")
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html")
    actions.orderable = False
    device = tables.Column(accessor='device_sort')
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    def __init__(self, *args, **kwargs):
        super(IndexJobTable, self).__init__(*args, **kwargs)
        self.length = 25

    class Meta(JobTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = (
            'id', 'actions', 'state', 'health', 'priority', 'device',
            'description', 'submitter', 'submit_time'
        )
        sequence = (
            'id', 'actions', 'state', 'priority', 'device',
            'description', 'submitter', 'submit_time'
        )
        exclude = ('end_time', 'duration', )


class TagsColumn(tables.Column):

    def render(self, value):
        tag_id = 'tag-%s' % "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(8))
        tags = ''
        values = list(value.all())
        if len(values) > 0:
            tags = '<p class="collapse" id="%s">' % tag_id
            tags += ',<br>'.join('<abbr data-toggle="tooltip" title="%s">%s</abbr>' % (tag.description, tag.name) for tag in values)
            tags += '</p><a class="btn btn-xs btn-success" data-toggle="collapse" data-target="#%s"><span class="glyphicon glyphicon-eye-open"></span></a>' % tag_id
        return mark_safe(tags)


class FailedJobTable(JobTable):

    id = tables.Column(verbose_name="ID")
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html")
    actions.orderable = False
    device = tables.Column(accessor='device_sort')
    duration = tables.Column(accessor='duration_sort')
    duration.orderable = False
    failure_tags = TagsColumn()
    failure_comment = tables.Column(empty_values=())
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    def __init__(self, *args, **kwargs):
        super(FailedJobTable, self).__init__(*args, **kwargs)
        self.length = 10

    def render_failure_comment(self, record):
        if record.failure_comment:
            return record.failure_comment
        try:
            failure = TestCase.objects.get(suite__job=record, result=TestCase.RESULT_FAIL,
                                           suite__name='lava', name='job')
        except TestCase.DoesNotExist:
            return ''
        action_metadata = failure.action_metadata
        if action_metadata is not None and 'error_msg' in action_metadata:
            return yaml.dump(failure.action_metadata['error_msg'])
        else:
            return ''

    class Meta(JobTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = (
            'id', 'actions', 'state', 'device', 'submit_time'
        )
        sequence = (
            'id', 'actions', 'state', 'device', 'submit_time'
        )
        exclude = ('submitter', 'end_time', 'priority', 'description')


class LongestJobTable(JobTable):

    id = tables.Column(verbose_name="ID")
    id.orderable = False
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html")
    actions.orderable = False
    device = tables.Column(accessor='actual_device')
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
    running = tables.Column(accessor='start_time', verbose_name='Running')
    running.orderable = False

    def __init__(self, *args, **kwargs):
        super(LongestJobTable, self).__init__(*args, **kwargs)
        self.length = 10

    def render_running(self, record):  # pylint: disable=no-self-use
        if not record.start_time:
            return ''
        return str(timezone.now() - record.start_time)

    def render_device(self, record):  # pylint: disable=no-self-use
        if record.actual_device:
            return pklink(record.actual_device)
        return ''

    class Meta(JobTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = (
            'id', 'actions', 'state', 'device'
        )
        sequence = (
            'id', 'actions', 'state', 'device'
        )
        exclude = ('duration', 'end_time')


class OverviewJobsTable(JobTable):

    id = tables.Column(verbose_name="ID")
    id.orderable = False
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html")
    actions.orderable = False
    device = tables.Column(accessor='device_sort')
    duration = tables.Column(accessor='duration_sort')
    duration.orderable = False
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    def __init__(self, *args, **kwargs):
        super(OverviewJobsTable, self).__init__(*args, **kwargs)
        self.length = 10

    class Meta(JobTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = (
            'id', 'actions', 'device',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )
        sequence = (
            'id', 'actions'
        )


class RecentJobsTable(JobTable):

    id = tables.Column(verbose_name="ID")
    id.orderable = False
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html")
    actions.orderable = False
    device = tables.Column(accessor='device_sort')
    duration = tables.Column(accessor='duration_sort')
    duration.orderable = False
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    def __init__(self, *args, **kwargs):
        super(RecentJobsTable, self).__init__(*args, **kwargs)
        self.length = 10

    class Meta(JobTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = (
            'id', 'actions',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )
        sequence = (
            'id', 'actions', 'state',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )
        exclude = ('device',)


class DeviceHealthTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(DeviceHealthTable, self).__init__(*args, **kwargs)
        self.length = 25

    def render_last_health_report_job(self, record):  # pylint: disable=no-self-use
        report = record.last_health_report_job
        if report is None:
            return ''
        else:
            return pklink(report)

    hostname = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    ''')
    worker_host = tables.TemplateColumn('''
    <a href="{{ record.worker_host.get_absolute_url }}">{{ record.worker_host }}</a>
    ''')
    health = tables.Column()
    last_report_time = tables.DateColumn(
        verbose_name="last report time",
        accessor="last_health_report_job.end_time")
    last_health_report_job = tables.Column("last report job")

    class Meta(LavaTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        sequence = [
            'hostname', 'worker_host', 'health', 'last_report_time',
            'last_health_report_job'
        ]
        searches = {
            'hostname': 'contains',
        }
        queries = {
            'device_health_query': 'health',
        }


class DeviceTypeTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(DeviceTypeTable, self).__init__(*args, **kwargs)
        self.length = 50

    def render_idle(self, record):  # pylint: disable=no-self-use
        return record['idle'] if record['idle'] > 0 else ""

    def render_offline(self, record):  # pylint: disable=no-self-use
        return record['offline'] if record['offline'] > 0 else ""

    def render_busy(self, record):  # pylint: disable=no-self-use
        return record['busy'] if record['busy'] > 0 else ""

    def render_restricted(self, record):  # pylint: disable=no-self-use
        return record['restricted'] if record['restricted'] > 0 else ""

    def render_name(self, record):  # pylint: disable=no-self-use
        return pklink(DeviceType.objects.get(name=record['device_type']))

    def render_queue(self, record):  # pylint: disable=no-self-use
        count = TestJob.objects.filter(
            Q(state=TestJob.STATE_SUBMITTED),
            Q(requested_device_type=record['device_type'])).count()
        return count if count > 0 else ""

    name = tables.Column(accessor='idle', verbose_name='Name')
    # the change in the aggregation breaks the accessor.
    name.orderable = False
    idle = tables.Column()
    offline = tables.Column()
    busy = tables.Column()
    restricted = tables.Column()
    # sadly, this needs to be not orderable as it would otherwise sort by the accessor.
    queue = tables.Column(accessor="idle", verbose_name="Queue", orderable=False)

    class Meta(LavaTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = DeviceType
        exclude = [
            'display', 'disable_health_check', 'owners_only',
            'architecture', 'health_denominator', 'health_frequency',
            'processor', 'cpu_model', 'bits', 'cores', 'core_count', 'description'
        ]
        searches = {
            'name': 'contains',
        }


class DeviceTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(DeviceTable, self).__init__(*args, **kwargs)
        self.length = 50

    def render_device_type(self, record):  # pylint: disable=no-self-use
        return pklink(record.device_type)

    def render_health(self, record):
        if record.health == Device.HEALTH_GOOD:
            return mark_safe('<strong class="text-success">Good</strong>')
        elif record.health in [Device.HEALTH_UNKNOWN, Device.HEALTH_LOOPING]:
            return mark_safe('<span class="text-info">%s</span>' % record.get_health_display())
        elif record.health == Device.HEALTH_BAD:
            return mark_safe('<span class="text-danger">Bad</span>')
        elif record.health == Device.HEALTH_MAINTENANCE:
            return mark_safe('<span class="text-warning">Maintenance</span>')
        else:
            return mark_safe('<span class="text-muted">Retired</span>')

    hostname = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    ''')
    worker_host = tables.TemplateColumn('''
    <a href="{{ record.worker_host.get_absolute_url }}">{{ record.worker_host }}</a>
    ''')
    device_type = tables.Column()
    state = ExpandedStatusColumn("state")
    owner = RestrictedDeviceColumn()
    owner.orderable = False
    health = tables.Column(verbose_name='Health')
    tags = TagsColumn()

    class Meta(LavaTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = Device
        exclude = [
            'user', 'group', 'is_public', 'device_version',
            'physical_owner', 'physical_group', 'description',
            'current_job', 'last_health_report_job'
        ]
        sequence = [
            'hostname', 'worker_host', 'device_type', 'state',
            'health', 'owner'
        ]
        searches = {
            'hostname': 'contains',
        }
        queries = {
            'device_type_query': 'device_type',
            'device_state_query': 'state',
            'device_health_query': 'health',
            'restriction_query': 'restrictions',
            'tags_query': 'tags'
        }


class WorkerTable(tables.Table):  # pylint: disable=too-few-public-methods,no-init

    def __init__(self, *args, **kwargs):
        super(WorkerTable, self).__init__(*args, **kwargs)
        self.length = 10
        self.show_help = True

    hostname = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    ''')

    def render_state(self, record):
        if record.state == Worker.STATE_ONLINE:
            return mark_safe('<span class="glyphicon glyphicon-ok text-success"></span> %s' % record.get_state_display())
        elif record.health == Worker.HEALTH_ACTIVE:
            return mark_safe('<span class="glyphicon glyphicon-fire text-danger"></span> %s' % record.get_state_display())
        else:
            return mark_safe('<span class="glyphicon glyphicon-remove text-danger"></span> %s' % record.get_state_display())

    def render_health(self, record):
        if record.health == Worker.HEALTH_ACTIVE:
            return mark_safe('<span class="glyphicon glyphicon-ok text-success"></span> %s' % record.get_health_display())
        elif record.health == Worker.HEALTH_MAINTENANCE:
            return mark_safe('<span class="glyphicon glyphicon-wrench text-warning"></span> %s' % record.get_health_display())
        else:
            return mark_safe('<span class="glyphicon glyphicon-remove text-danger"></span> %s' % record.get_health_display())

    def render_last_ping(self, record):
        return timesince(record.last_ping)

    class Meta(LavaTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = Worker
        sequence = [
            'hostname', 'state', 'health', 'description'
        ]


class LogEntryTable(tables.Table):

    def __init__(self, *args, **kwargs):
        super(LogEntryTable, self).__init__(*args, **kwargs)
        self.length = 10

    action_time = tables.DateColumn(format="Nd, g:ia")
    object_id = tables.Column(verbose_name="Name")
    change_message = tables.Column(verbose_name="Reason", empty_values=[None])
    change_message.orderable = False

    def render_change_message(self, record):
        if django.VERSION > (1, 10):
            message = record.get_change_message()
        else:
            message = record.change_message
        if record.is_change():
            return message
        elif record.is_addition():
            return mark_safe('<span class="glyphicon glyphicon-plus text-success"></span> %s' % message)
        else:
            return mark_safe('<span class="glyphicon glyphicon-remove text-danger"></span> %s' % message)

    class Meta(LavaTable.Meta):
        model = LogEntry
        fields = (
            'action_time', 'object_id', 'user', 'change_message'
        )
        sequence = (
            'action_time', 'object_id', 'user', 'change_message'
        )


class DeviceLogEntryTable(LogEntryTable):

    class Meta(LogEntryTable.Meta):
        sequence = (
            'action_time', 'user', 'change_message'
        )
        exclude = [
            'object_id'
        ]


class NoWorkerDeviceTable(DeviceTable):

    class Meta(LavaTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        exclude = [
            'worker_host',
            'user', 'group', 'is_public', 'device_version',
            'physical_owner', 'physical_group', 'description',
            'last_health_report_job'
        ]
        searches = {
            'hostname': 'contains',
        }
        queries = {
            'device_state_query': 'state',
            'device_health_query': 'health',
        }


class HealthJobSummaryTable(tables.Table):  # pylint: disable=too-few-public-methods

    length = 10
    Duration = tables.Column()
    Complete = tables.Column()
    Failed = tables.Column()

    class Meta(LavaTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = None


class QueueJobsTable(JobTable):

    id = tables.Column(verbose_name="ID")
    id.orderable = False
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html")
    actions.orderable = False
    device = tables.Column(accessor='device_sort')
    in_queue = tables.TemplateColumn('''
    for {{ record.submit_time|timesince }}
    ''')
    in_queue.orderable = False
    submit_time = tables.DateColumn("Nd, g:ia")
    end_time = tables.DateColumn("Nd, g:ia")

    def __init__(self, *args, **kwargs):
        super(QueueJobsTable, self).__init__(*args, **kwargs)
        self.length = 50

    class Meta(JobTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        fields = (
            'id', 'actions', 'device', 'description', 'submitter',
            'submit_time', 'in_queue'
        )
        sequence = (
            'id', 'actions', 'device', 'description', 'submitter',
            'submit_time', 'in_queue'
        )
        exclude = ('state', 'health', 'priority', 'end_time', 'duration')


class PassingHealthTable(DeviceHealthTable):

    def __init__(self, *args, **kwargs):
        super(PassingHealthTable, self).__init__(*args, **kwargs)
        self.length = 25

    def render_device_type(self, record):  # pylint: disable=no-self-use
        return pklink(record.device_type)

    def render_last_health_report_job(self, record):  # pylint: disable=no-self-use
        report = record.last_health_report_job
        return mark_safe('<a href="%s">%s</a>' % (report.get_absolute_url(), report))

    device_type = tables.Column()

    class Meta(LavaTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        exclude = [
            'worker_host', 'last_report_time'
        ]
        sequence = [
            'hostname', 'device_type', 'health',
            'last_health_report_job'
        ]
        searches = {
            'hostname': 'contains',
        }
        queries = {
            'device_health_query': 'health',
        }


class RunningTable(LavaTable):
    """
    Provide the admins with some information on the activity of the instance.
    Multinode jobs reserve devices whilst still in SUBMITITED
    Except for dynamic connections, there should not be more active jobs than active devices of
    any particular DeviceType.
    """

    def __init__(self, *args, **kwargs):
        super(RunningTable, self).__init__(*args, **kwargs)
        self.length = 50

    # deprecated: dynamic connections are TestJob without a device

    def render_jobs(self, record):  # pylint: disable=no-self-use
        count = TestJob.objects.filter(
            Q(state=TestJob.STATE_RUNNING),
            Q(requested_device_type=record.name) |
            Q(actual_device__in=Device.objects.filter(device_type=record.name))
        ).count()
        return count if count > 0 else ""

    def render_reserved(self, record):  # pylint: disable=no-self-use
        count = Device.objects.filter(device_type=record.name, state=Device.STATE_RESERVED).count()
        return count if count > 0 else ""

    def render_running(self, record):  # pylint: disable=no-self-use
        count = Device.objects.filter(device_type=record.name, state=Device.STATE_RUNNING).count()
        return count if count > 0 else ""

    name = IDLinkColumn(accessor='name')

    reserved = tables.Column(accessor='display', orderable=False, verbose_name='Reserved')
    running = tables.Column(accessor='display', orderable=False, verbose_name='Running')
    jobs = tables.Column(accessor='display', orderable=False, verbose_name='Jobs')

    class Meta(LavaTable.Meta):  # pylint: disable=too-few-public-methods,no-init,no-self-use
        model = DeviceType
        sequence = [
            'name', 'reserved', 'running', 'jobs'
        ]
        exclude = [
            'display', 'disable_health_check', 'owners_only', 'architecture',
            'processor', 'cpu_model', 'bits', 'cores', 'core_count', 'description'
        ]
