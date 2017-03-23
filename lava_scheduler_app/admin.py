from django import forms
from django.core.exceptions import ValidationError
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q
from lava_scheduler_app.models import (
    Device, DeviceStateTransition, DeviceType, TestJob, Tag, JobFailureTag,
    User, Worker, DefaultDeviceOwner,
    Architecture, ProcessorFamily, Alias, BitWidth, Core
)
from linaro_django_xmlrpc.models import AuthToken

# django admin API itself isn't pylint clean, so some settings must be suppressed.
# pylint: disable=no-self-use,function-redefined


class DefaultOwnerInline(admin.StackedInline):
    """
    Exposes the default owner override class
    in the Django admin interface
    """
    model = DefaultDeviceOwner
    can_delete = False


def expire_user_action(modeladmin, request, queryset):  # pylint: disable=unused-argument
    for user in queryset.filter(is_active=True):
        AuthToken.objects.filter(user=user).delete()
        user.is_staff = False
        user.is_superuser = False
        user.is_active = False
        for group in user.groups.all():
            group.user_set.remove(user)
        for permission in user.user_permissions.all():
            user.user_permissions.remove(permission)
        user.save()


expire_user_action.short_description = 'Expire user account'


class UserAdmin(UserAdmin):
    """
    Defines the override class for DefaultOwnerInline
    """
    inlines = (DefaultOwnerInline, )
    actions = [expire_user_action]


#  Setup the override in the django admin interface at startup.
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


def offline_action(modeladmin, request, queryset):  # pylint: disable=unused-argument
    for device in queryset.filter(status__in=[Device.IDLE, Device.RUNNING, Device.RESERVED]):
        if device.can_admin(request.user):
            device.put_into_maintenance_mode(request.user, "admin action")


offline_action.short_description = "take offline"


def online_action(modeladmin, request, queryset):  # pylint: disable=unused-argument
    for device in queryset.filter(status__in=[Device.OFFLINE, Device.OFFLINING]):
        if device.can_admin(request.user):
            device.put_into_online_mode(request.user, "admin action")


online_action.short_description = "take online"


def online_action_without_health_check(modeladmin, request, queryset):  # pylint: disable=unused-argument,invalid-name
    for device in queryset.filter(status__in=[Device.OFFLINE, Device.OFFLINING]):
        if device.can_admin(request.user):
            device.put_into_online_mode(request.user, "admin action", True)


online_action_without_health_check.short_description = \
    "take online without manual health check"


def retire_action(modeladmin, request, queryset):  # pylint: disable=unused-argument
    for device in queryset:
        if device.can_admin(request.user):
            new_status = device.RETIRED
            DeviceStateTransition.objects.create(
                created_by=request.user, device=device, old_state=device.status,
                new_state=new_status, message="retiring", job=None).save()
            device.status = new_status
            device.save()


retire_action.short_description = "retire"


def cancel_action(modeladmin, request, queryset):  # pylint: disable=unused-argument
    for testjob in queryset:
        if testjob.can_cancel(request.user):
            testjob.cancel(request.user)


cancel_action.short_description = 'cancel selected jobs'


def health_unknown(modeladmin, request, queryset):  # pylint: disable=unused-argument
    for device in queryset.filter(health_status=Device.HEALTH_PASS):
        device.health_status = Device.HEALTH_UNKNOWN
        device.save()


health_unknown.short_description = "set health_status to unknown"


class ActiveDevicesFilter(admin.SimpleListFilter):
    title = 'Active devices'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('NoRetired', 'Exclude retired'),
            ('CurrentJob', 'With a current Job')
        )

    def queryset(self, request, queryset):
        if self.value() == 'NoRetired':
            return queryset.exclude(status=Device.RETIRED).order_by('hostname')
        if self.value() == 'CurrentJob':
            return queryset.filter(current_job__isnull=False).order_by('hostname')


class RequestedDeviceFilter(admin.SimpleListFilter):
    title = 'Requested Device (except retired)'
    parameter_name = 'requested_device'

    def lookups(self, request, model_admin):
        list_of_types = []
        queryset = Device.objects.exclude(status=Device.RETIRED).order_by('hostname')
        for dev_type in queryset:
            list_of_types.append(
                (str(dev_type.hostname), dev_type.hostname)
            )
        return sorted(list_of_types, key=lambda tp: tp[1])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(requested_device__hostname=self.value())
        return queryset.order_by('requested_device__hostname')


class ActualDeviceFilter(admin.SimpleListFilter):
    title = 'Actual Device (except retired)'
    parameter_name = 'actual_device'

    def lookups(self, request, model_admin):
        list_of_types = []
        queryset = Device.objects.exclude(status=Device.RETIRED).order_by('hostname')
        for dev_type in queryset:
            list_of_types.append(
                (str(dev_type.hostname), dev_type.hostname)
            )
        return sorted(list_of_types, key=lambda tp: tp[1])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(actual_device__hostname=self.value())
        return queryset.order_by('actual_device__hostname')


class DeviceTypeFilter(admin.SimpleListFilter):
    title = 'Device Type'
    parameter_name = 'device_type'

    def lookups(self, request, model_admin):
        list_of_types = []
        queryset = DeviceType.objects.all()
        for dev_type in queryset:
            list_of_types.append(
                (str(dev_type.name), dev_type.name)
            )
        return sorted(list_of_types, key=lambda tp: tp[1])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(device_type__name=self.value())
        return queryset.order_by('device_type__name')


class RequestedDeviceTypeFilter(admin.SimpleListFilter):
    title = 'Requested Device Type'
    parameter_name = 'requested_device_type'

    def lookups(self, request, model_admin):
        list_of_types = []
        queryset = DeviceType.objects.order_by('name')
        for dev_type in queryset:
            list_of_types.append(
                (str(dev_type.name), dev_type.name)
            )
        return sorted(list_of_types, key=lambda tp: tp[1])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(requested_device_type__name=self.value())
        return queryset.order_by('requested_device_type__name')


class DeviceAdmin(admin.ModelAdmin):
    actions = [online_action, online_action_without_health_check,
               offline_action, health_unknown, retire_action]
    list_filter = (DeviceTypeFilter, 'status', ActiveDevicesFilter,
                   'health_status', 'worker_host')
    raw_id_fields = ['current_job', 'last_health_report_job']

    def has_health_check(self, obj):
        return bool(obj.get_health_check())
    has_health_check.boolean = True
    has_health_check.short_description = "Health check"

    def exclusive_device(self, obj):
        return obj.is_exclusive
    exclusive_device.boolean = True
    exclusive_device.short_description = "v2 only"

    fieldsets = (
        ('Properties', {
            'fields': (('device_type', 'hostname'), 'worker_host', 'device_version')}),
        ('Device owner', {
            'fields': (('user', 'group'), ('physical_owner', 'physical_group'), 'is_public', 'is_pipeline')}),
        ('Status', {
            'fields': (('status', 'health_status'), ('last_health_report_job', 'current_job'))}),
        ('Advanced properties', {
            'fields': ('description', 'tags', ('device_dictionary_yaml', 'device_dictionary_jinja')),
            'classes': ('collapse', )
        }),
    )
    readonly_fields = ('device_dictionary_yaml', 'device_dictionary_jinja')
    list_display = ('hostname', 'device_type', 'current_job', 'worker_host',
                    'status', 'health_status', 'has_health_check', 'is_public',
                    'is_pipeline', 'exclusive_device')
    search_fields = ('hostname', 'device_type__name')
    ordering = ['hostname']


class VisibilityForm(forms.ModelForm):

    def clean_viewing_groups(self):
        viewing_groups = self.cleaned_data['viewing_groups']
        visibility = self.cleaned_data['visibility']
        if len(viewing_groups) != 1 and visibility == TestJob.VISIBLE_GROUP:
            raise ValidationError("Group visibility must have exactly one viewing group.")
        elif len(viewing_groups) != 0 and visibility == TestJob.VISIBLE_PERSONAL:
            raise ValidationError("Personal visibility cannot have any viewing groups assigned.")
        elif len(viewing_groups) != 0 and visibility == TestJob.VISIBLE_PUBLIC:
            raise ValidationError("Pulibc visibility cannot have any viewing groups assigned.")
        return self.cleaned_data['viewing_groups']


class TestJobAdmin(admin.ModelAdmin):
    def requested_device_hostname(self, obj):
        return '' if obj.requested_device is None else obj.requested_device.hostname
    requested_device_hostname.short_description = 'Requested device'

    def requested_device_type_name(self, obj):
        return '' if obj.requested_device_type is None else obj.requested_device_type
    requested_device_type_name.short_description = 'Request device type'
    form = VisibilityForm
    actions = [cancel_action]
    list_filter = ('status', RequestedDeviceTypeFilter, RequestedDeviceFilter, ActualDeviceFilter)
    raw_id_fields = ['_results_bundle']
    fieldsets = (
        ('Owner', {
            'fields': ('user', 'group', 'submitter', 'submit_token', 'is_public', 'visibility', 'viewing_groups')}),
        ('Request', {
            'fields': ('requested_device', 'requested_device_type', 'priority', 'health_check')}),
        ('Advanced properties', {
            'fields': ('description', 'tags', 'sub_id', 'target_group', 'vm_group')}),
        ('Current status', {
            'fields': ('actual_device', 'status')}),
        ('Results & Failures', {
            'fields': ('failure_tags', 'failure_comment', '_results_link', '_results_bundle')}),
    )
    list_display = ('id', 'status', 'submitter', 'requested_device_type_name', 'requested_device_hostname',
                    'actual_device', 'health_check', 'submit_time', 'start_time', 'end_time')
    ordering = ['-submit_time']


class DeviceStateTransitionAdmin(admin.ModelAdmin):
    def device_hostname(self, obj):
        return obj.device.hostname

    raw_id_fields = ['job']
    list_filter = ('device__hostname', )
    list_display = ('device_hostname', 'old_state', 'new_state', 'created_on')
    fieldsets = (
        ('State', {
            'fields': ('device', 'old_state', 'new_state')}),
        ('Metadata', {
            'fields': ('created_by', 'job', 'message')})
    )


class DeviceTypeAdmin(admin.ModelAdmin):

    def architecture_name(self, obj):
        if obj.architecture:
            return obj.architecture
        return ''

    def processor_name(self, obj):
        if obj.processor:
            return obj.processor
        return ''

    def cpu_model_name(self, obj):
        if obj.cpu_model:
            return obj.cpu_model
        return ''

    def list_of_aliases(self, obj):
        if obj.aliases:
            return ', '.join([alias.name for alias in obj.aliases])

    def bit_count(self, obj):
        if obj.bits:
            return obj.bits
        return ''

    def list_of_cores(self, obj):
        if obj.core_count:
            return "%s x %s" % (
                obj.core_count,
                ','.join([core.name for core in obj.cores.all().order_by('name')]))
        return ''

    def health_check_frequency(self, device_type):
        if device_type.health_denominator == DeviceType.HEALTH_PER_JOB:
            return "every %d jobs" % device_type.health_frequency
        return "every %d hours" % device_type.health_frequency

    list_filter = ('name', 'display', 'cores',
                   'architecture', 'processor')
    list_display = ('name', 'display', 'owners_only', 'health_check_frequency',
                    'architecture_name', 'processor_name', 'cpu_model_name',
                    'list_of_cores', 'bit_count')
    ordering = ['name']


# API defined by django admin
def hide_worker_action(modeladmin, request, queryset):  # pylint: disable=unused-argument
    for worker in queryset.filter(display=True):
        worker.display = False
        worker.save()


hide_worker_action.short_description = "Hide selected worker(s)"


def show_worker_action(modeladmin, request, queryset):  # pylint: disable=unused-argument
    for worker in queryset.filter(display=False):
        worker.display = True
        worker.save()


show_worker_action.short_description = "Show selected worker(s)"


class WorkerAdmin(admin.ModelAdmin):
    actions = [hide_worker_action, show_worker_action]
    list_display = ('hostname', 'display', 'is_master')
    ordering = ['hostname']


class TagLowerForm(forms.ModelForm):

    def clean_name(self):
        name = self.cleaned_data['name']
        if name != name.lower():
            raise ValidationError("Tag names are case-insensitive.")
        return name


class TagAdmin(admin.ModelAdmin):
    form = TagLowerForm
    list_display = ('name', 'description')
    ordering = ['name']


admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceStateTransition, DeviceStateTransitionAdmin)
admin.site.register(DeviceType, DeviceTypeAdmin)
admin.site.register(TestJob, TestJobAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Architecture)
admin.site.register(ProcessorFamily)
admin.site.register(Alias)
admin.site.register(BitWidth)
admin.site.register(Core)
admin.site.register(JobFailureTag)
admin.site.register(Worker, WorkerAdmin)
