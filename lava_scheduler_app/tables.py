from django.conf import settings
from django.template import defaultfilters as filters
from django.utils.safestring import mark_safe
from django.utils.html import escape
import django_tables2 as tables
from lava_scheduler_app.models import (
    TestJob,
    Device,
    DeviceType,
    Worker,
    DeviceStateTransition,
)
from lava.utils.lavatable import LavaTable, LavaView
from django.contrib.auth.models import User, Group
from django.db.models import Q
from datetime import datetime, timedelta
from markupsafe import escape


# The query_set is based in the view, so split that into a View class
# Avoid putting queryset functionality into tables.
# base new views on FiltereSingleTableView. These classes can go into
# views.py later.

# No function in this file is directly accessible via urls.py - those
# functions need to go in views.py


class IDLinkColumn(tables.Column):

    def __init__(self, verbose_name="ID", **kw):
        kw['verbose_name'] = verbose_name
        super(IDLinkColumn, self).__init__(**kw)

    def render(self, record, table=None):
        return pklink(record)


class RestrictedIDLinkColumn(IDLinkColumn):

    def render(self, record, table=None):

        if record.actual_device:
            device_type = record.actual_device.device_type
        elif record.requested_device:
            device_type = record.requested_device.device_type
        else:
            device_type = record.requested_device_type

        if len(device_type.devices_visible_to(table.context.get('request').user)) == 0:
            return "Unavailable"
        elif record.is_accessible_by(table.context.get('request').user):
            return pklink(record)
        else:
            return record.pk


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


class ExpandedStatusColumn(tables.Column):

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


class RestrictedDeviceColumn(tables.Column):

    def __init__(self, verbose_name="Restrictions", **kw):
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
        if record.status == Device.RETIRED:
            return "Retired, no submissions possible."
        if record.user:
            label = record.user.email
        if record.group:
            label = "all users in %s group" % record.group
        if record.is_public:
            message = "Unrestricted usage" \
                if label is None else "Unrestricted usage. Device owned by %s." % label
            return message
        return "Job submissions restricted to %s" % label


def all_jobs_with_custom_sort():
    jobs = TestJob.objects.select_related(
        "actual_device",
        "requested_device",
        "requested_device_type",
        "submitter",
        "user",
        "group").extra(select={'device_sort': 'coalesce('
                               'actual_device_id, '
                               'requested_device_id, requested_device_type_id)',
                               'duration_sort': 'end_time - start_time'}).all()
    return jobs.order_by('-submit_time')


class DateColumn(tables.Column):

    def __init__(self, **kw):
        self._format = kw.get('date_format', settings.DATETIME_FORMAT)
        super(DateColumn, self).__init__(**kw)

    def render(self, value):
        return filters.date(value, self._format)


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

    id = RestrictedIDLinkColumn(verbose_name="ID", accessor="id")
    device = tables.Column(accessor='device_sort')
    duration = tables.Column(accessor='duration_sort')
    duration.orderable = False
    submit_time = DateColumn()
    end_time = DateColumn()

    def render_device(self, record):
        if record.actual_device:
            device_type = record.actual_device.device_type
            retval = pklink(record.actual_device)
        elif record.requested_device:
            device_type = record.requested_device.device_type
            retval = pklink(record.requested_device)
        else:
            device_type = record.requested_device_type
            retval = mark_safe('<i>%s</i>' % escape(record.requested_device_type.pk))
        if len(device_type.devices_visible_to(self.context.get('request').user)) == 0:
            return "Unavailable"
        return retval

    def render_description(self, value):
        if value:
            return value
        else:
            return ''

    class Meta(LavaTable.Meta):
        model = TestJob
        # alternatively, use 'fields' value to include specific fields.
        exclude = [
            'is_public',
            'user',
            'group',
            'sub_id',
            'target_group',
            'submit_token',
            'health_check',
            'definition',
            'original_definition',
            'multinode_definition',
            'admin_notifications',
            '_results_link',
            '_results_bundle',
            'requested_device_type',
            'start_time',
            'requested_device',
            'log_file',
            'actual_device',
        ]
        fields = (
            'id', 'status', 'priority', 'device',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )
        sequence = (
            'id', 'status', 'priority', 'device',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )
        # filter view functions supporting relational mappings and returning a Q()
        queries = {
            'device_query': "device",  # active_device
            'owner_query': "submitter",  # submitter
            'job_status_query': 'status',
        }
        # fields which can be searched with default __contains queries
        # note the enums cannot be searched this way.
        searches = {
            'id': 'contains',
            'description': 'contains'
        }
        # dedicated time-based search fields
        times = {
            'submit_time': 'hours',
            'end_time': 'hours',
            #'duration': 'minutes' FIXME: needs a function call
        }


class IndexJobTable(JobTable):

    id = RestrictedIDLinkColumn(verbose_name="ID", accessor="id")
    device = tables.Column(accessor='device_sort')

    def __init__(self, *args, **kwargs):
        super(IndexJobTable, self).__init__(*args, **kwargs)
        self.length = 25

    class Meta(JobTable.Meta):
        fields = (
            'id', 'status', 'priority', 'device',
            'description', 'submitter', 'submit_time'
        )
        sequence = (
            'id', 'status', 'priority', 'device',
            'description', 'submitter', 'submit_time'
        )
        exclude = ('end_time', 'duration', )


def _str_to_bool(string):
    return string.lower() in ['1', 'true', 'yes']


class TagsColumn(tables.Column):

    def render(self, value):
        return ', '.join([x.name for x in value.all()])


class FailedJobTable(JobTable):

    id = RestrictedIDLinkColumn(verbose_name="ID", accessor="id")
    device = tables.Column(accessor='device_sort')
    duration = tables.Column(accessor='duration_sort')
    duration.orderable = False
    failure_tags = TagsColumn()
    failure_comment = tables.Column()

    def __init__(self, *args, **kwargs):
        super(FailedJobTable, self).__init__(*args, **kwargs)
        self.length = 10

    class Meta(JobTable.Meta):
        fields = (
            'id', 'status', 'device', 'submit_time'
        )
        sequence = (
            'id', 'status', 'device', 'submit_time'
        )
        exclude = ('submitter', 'end_time', 'priority', 'description')


class OverviewJobsTable(JobTable):

    id = RestrictedIDLinkColumn(verbose_name="ID", accessor="id")
    device = tables.Column(accessor='device_sort')
    duration = tables.Column(accessor='duration_sort')
    duration.orderable = False

    def __init__(self, *args, **kwargs):
        super(OverviewJobsTable, self).__init__(*args, **kwargs)
        self.length = 10

    class Meta(JobTable.Meta):
        fields = (
            'id', 'status', 'priority', 'device',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )


class RecentJobsTable(JobTable):

    id = RestrictedIDLinkColumn(verbose_name="ID", accessor="id")
    device = tables.Column(accessor='device_sort')

    def __init__(self, *args, **kwargs):
        super(RecentJobsTable, self).__init__(*args, **kwargs)
        self.length = 10

    class Meta(JobTable.Meta):
        fields = (
            'id', 'status', 'priority',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )
        sequence = (
            'id', 'status', 'priority',
            'description', 'submitter', 'submit_time', 'end_time',
            'duration'
        )
        exclude = ('device',)


class DeviceHealthTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(DeviceHealthTable, self).__init__(*args, **kwargs)
        self.length = 25

    def render_last_health_report_job(self, record):
        report = record.last_health_report_job
        if report is None:
            return ''
        else:
            return pklink(report)

    hostname = tables.TemplateColumn('''
    {% if record.too_long_since_last_heartbeat or record.status == record.RETIRED %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-offline-icon.png"
          alt="{{ offline }}" />
    {% else %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-available-icon.png"
          alt="{{ online }}" />
    {% endif %}&nbsp;&nbsp;
    {% if record.is_master %}
    <b><a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a></b>
    {% else %}
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    {% endif %}
        ''')
    worker_host = tables.TemplateColumn('''
    {% if record.too_long_since_last_heartbeat %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-offline-icon.png"
          alt="{{ offline }}" />
    {% else %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-available-icon.png"
          alt="{{ online }}" />
    {% endif %}&nbsp;&nbsp;
    {% if record.is_master %}
    <b><a href="{{ record.worker_host.get_absolute_url }}">{{ record.worker_host }}</a></b>
    {% else %}
    <a href="{{ record.worker_host.get_absolute_url }}">{{ record.worker_host }}</a>
    {% endif %}
        ''')

    health_status = tables.Column()
    last_report_time = DateColumn(
        verbose_name="last report time",
        accessor="last_health_report_job.end_time")
    last_health_report_job = tables.Column("last report job")

    class Meta(LavaTable.Meta):
        sequence = [
            'hostname', 'worker_host', 'health_status', 'last_report_time',
            'last_health_report_job'
        ]
        searches = {
            'hostname': 'contains',
        }
        queries = {
            'health_status_query': 'health_status',
        }


class DeviceTypeTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(DeviceTypeTable, self).__init__(*args, **kwargs)
        self.length = 50

    def render_idle(self, record):
        return "%d" % record.idle

    def render_offline(self, record):
        return "%d" % record.offline

    def render_busy(self, record):
        return "%d" % record.busy

    def render_restricted(self, record):
        return "%d" % record.restricted

    def render_queue(self, record):
        return TestJob.objects.filter(
            Q(status=TestJob.SUBMITTED),
            Q(requested_device_type=record.name) |
            Q(requested_device__in=Device.objects.filter(device_type=record.name))).count()

    name = IDLinkColumn("name")
    idle = tables.Column()
    offline = tables.Column()
    busy = tables.Column()
    restricted = tables.Column()
    # sadly, this needs to be not orderable as it would otherwise sort by the
    # accessor.
    queue = tables.Column(accessor="name", verbose_name="queue", orderable=False)

    class Meta(LavaTable.Meta):
        model = DeviceType
        exclude = [
            'display', 'health_check_job', 'owners_only'
        ]
        searches = {
            'name': 'contains',
        }


class QueueJobsTable(JobTable):

    id = RestrictedIDLinkColumn(accessor="id")
    device = tables.Column(accessor='device_sort')

    def __init__(self, *args, **kwargs):
        super(QueueJobsTable, self).__init__(*args, **kwargs)
        self.length = 50

    class Meta(JobTable.Meta):
        fields = (
            'id', 'device', 'description', 'submitter', 'submit_time',
        )
        sequence = (
            'id', 'device', 'description', 'submitter', 'submit_time',
        )
        exclude = ('status', 'priority', 'end_time', 'duration')


class DeviceTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(DeviceTable, self).__init__(*args, **kwargs)
        self.length = 50

    def render_device_type(self, record):
        return pklink(record.device_type)

    hostname = tables.TemplateColumn('''
    {% if record.too_long_since_last_heartbeat or record.status == record.RETIRED %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-offline-icon.png"
          alt="{{ offline }}" />
    {% else %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-available-icon.png"
          alt="{{ online }}" />
    {% endif %}&nbsp;&nbsp;
    {% if record.is_master %}
    <b><a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a></b>
    {% else %}
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    {% endif %}
        ''')
    worker_host = tables.TemplateColumn('''
    {% if record.too_long_since_last_heartbeat %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-offline-icon.png"
          alt="{{ offline }}" />
    {% else %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-available-icon.png"
          alt="{{ online }}" />
    {% endif %}&nbsp;&nbsp;
    {% if record.is_master %}
    <b><a href="{{ record.worker_host.get_absolute_url }}">{{ record.worker_host }}</a></b>
    {% else %}
    <a href="{{ record.worker_host.get_absolute_url }}">{{ record.worker_host }}</a>
    {% endif %}
        ''')
    device_type = tables.Column()
    status = ExpandedStatusColumn("status")
    owner = RestrictedDeviceColumn()
    owner.orderable = False
    health_status = tables.Column()

    class Meta(LavaTable.Meta):
        model = Device
        exclude = [
            'user', 'group', 'is_public', 'device_version',
            'physical_owner', 'physical_group', 'description',
            'current_job', 'last_health_report_job'
        ]
        sequence = [
            'hostname', 'worker_host', 'device_type', 'status',
            'owner', 'health_status'
        ]
        searches = {
            'hostname': 'contains',
        }
        queries = {
            'device_type_query': 'device_type',
            'device_status_query': 'status',
            'health_status_query': 'health_status',
            'restriction_query': 'restrictions',
        }


class NoDTDeviceTable(DeviceTable):

    class Meta(LavaTable.Meta):
        exclude = [
            'device_type',
            'user', 'group', 'is_public', 'device_version',
            'physical_owner', 'physical_group', 'description',
            'current_job', 'last_health_report_job'
        ]
        searches = {
            'hostname': 'contains',
        }
        queries = {
            'device_status_query': 'status',
            'health_status_query': 'health_status',
        }


class WorkerTable(tables.Table):

    def __init__(self, *args, **kwargs):
        super(WorkerTable, self).__init__(*args, **kwargs)
        self.length = 10

    hostname = tables.TemplateColumn('''
    {% if record.too_long_since_last_heartbeat %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-offline-icon.png"
          alt="{{ offline }}" />
    {% else %}
    <img src="{{ STATIC_URL }}lava_scheduler_app/images/dut-available-icon.png"
          alt="{{ online }}" />
    {% endif %}&nbsp;&nbsp;
    {% if record.is_master %}
    <b><a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a></b>
    {% else %}
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    {% endif %}
        ''')
    status = tables.TemplateColumn('''
    {% if record.too_long_since_last_heartbeat %}
    down
    {% else %}
    up
    {% endif %}
        ''')
    status.orderable = False

    is_master = tables.Column()
    uptime = tables.TemplateColumn('''
    {% if record.too_long_since_last_heartbeat %}
    ---
    {% else %}
    {{ record.uptime }}
    {% endif %}
        ''')
    arch = tables.Column()

    class Meta(LavaTable.Meta):
        model = Worker
        exclude = [
            'rpc2_url', 'description', 'hardware_info', 'software_info',
            'platform', 'last_heartbeat', 'last_complete_info_update'
        ]
        sequence = [
            'hostname', 'ip_address', 'status', 'is_master', 'uptime', 'arch'
        ]


class NoWorkerDeviceTable(DeviceTable):

    class Meta(LavaTable.Meta):
        exclude = [
            'worker_host',
            'user', 'group', 'is_public', 'device_version',
            'physical_owner', 'physical_group', 'description',
            'current_job', 'last_health_report_job'
        ]
        searches = {
            'hostname': 'contains',
        }
        queries = {
            'device_status_query': 'status',
            'health_status_query': 'health_status',
        }


class HealthJobSummaryTable(tables.Table):

    length = 10
    Duration = tables.Column()
    Complete = tables.Column()
    Failed = tables.Column()

    class Meta(LavaTable.Meta):
        model = None


class DeviceTransitionTable(LavaTable):

    def render_created_on(self, record):
        t = record
        base = "<a href='/scheduler/transition/%s'>%s</a>" \
               % (record.id, filters.date(t.created_on, "Y-m-d H:i"))
        return mark_safe(base)

    def render_transition(self, record):
        t = record
        return mark_safe(
            '%s &rarr; %s' % (t.get_old_state_display(), t.get_new_state_display(),))

    created_on = tables.Column('when')
    transition = tables.Column('transition', orderable=False, accessor='old_state')
    created_by = tables.Column('by', accessor='created_by')
    message = tables.TemplateColumn('''
    <div class="edit_transition" id="{{ record.id }}" style="width: 100%">{{ record.message }}</div>
        ''')

    class Meta(LavaTable.Meta):
        model = DeviceStateTransition
        exclude = [
            'id', 'device', 'job', 'old_state', 'new_state'
        ]
        sequence = [
            'created_on', 'transition', 'created_by', 'message'
        ]
        searches = {}
        queries = {}
        times = {}
