from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from lava_scheduler_app.models import (
    Device, DeviceStateTransition, DeviceType, TestJob, Tag, JobFailureTag,
    User, Worker, DefaultDeviceOwner, DeviceDictionaryTable,
    Architecture, ProcessorFamily, BitWidth, Core
)


class DefaultOwnerInline(admin.StackedInline):
    """
    Exposes the default owner override class
    in the Django admin interface
    """
    model = DefaultDeviceOwner
    can_delete = False


class UserAdmin(UserAdmin):
    """
    Defines the override class for DefaultOwnerInline
    """
    inlines = (DefaultOwnerInline, )


#  Setup the override in the django admin interface at startup.
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


def offline_action(modeladmin, request, queryset):
    for device in queryset.filter(status__in=[Device.IDLE, Device.RUNNING, Device.RESERVED]):
        if device.can_admin(request.user):
            device.put_into_maintenance_mode(request.user, "admin action")
offline_action.short_description = "take offline"


def online_action(modeladmin, request, queryset):
    for device in queryset.filter(status__in=[Device.OFFLINE, Device.OFFLINING]):
        if device.can_admin(request.user):
            device.put_into_online_mode(request.user, "admin action")
online_action.short_description = "take online"


def online_action_without_health_check(modeladmin, request, queryset):
    for device in queryset.filter(status__in=[Device.OFFLINE, Device.OFFLINING]):
        if device.can_admin(request.user):
            device.put_into_online_mode(request.user, "admin action", True)
online_action_without_health_check.short_description = \
    "take online without manual health check"


def retire_action(modeladmin, request, queryset):
    for device in queryset:
        if device.can_admin(request.user):
            new_status = device.RETIRED
            DeviceStateTransition.objects.create(
                created_by=request.user, device=device, old_state=device.status,
                new_state=new_status, message="retiring", job=None).save()
            device.status = new_status
            device.save()
retire_action.short_description = "retire"


def cancel_action(modeladmin, request, queryset):
    for testjob in queryset:
        if testjob.can_cancel(request.user):
            testjob.cancel(request.user)
cancel_action.short_description = 'cancel selected jobs'


def health_unknown(modeladmin, request, queryset):
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
            return queryset.exclude(status=Device.RETIRED)
        if self.value() == 'CurrentJob':
            return queryset.filter(current_job__isnull=False)


class DeviceAdmin(admin.ModelAdmin):
    actions = [online_action, online_action_without_health_check,
               offline_action, health_unknown, retire_action]
    list_filter = ('device_type', 'status', ActiveDevicesFilter,
                   'health_status', 'worker_host')
    raw_id_fields = ['current_job', 'last_health_report_job']

    def exclusive_device(self, obj):
        return 'pipeline only' if obj.is_exclusive else ''

    fieldsets = (
        ('Properties', {
            'fields': ('device_type', 'hostname', 'worker_host', 'device_version')}),
        ('Device owner', {
            'fields': ('user', 'group', 'physical_owner', 'physical_group', 'is_public', 'is_pipeline')}),
        ('Advanced properties', {
            'fields': ('description', 'tags')}),
        ('Status', {
            'fields': ('status', 'health_status', 'last_health_report_job', 'current_job')}),
    )
    list_display = ('hostname', 'device_type', 'current_job', 'worker_host',
                    'status', 'health_status', 'is_public', 'is_pipeline', 'exclusive_device')
    search_fields = ('hostname', 'device_type__name')


class TestJobAdmin(admin.ModelAdmin):
    def requested_device_hostname(self, obj):
        return '' if obj.requested_device is None else obj.requested_device.hostname
    requested_device_hostname.short_description = 'Requested device'

    def requested_device_type_name(self, obj):
        return '' if obj.requested_device_type is None else obj.requested_device_type
    requested_device_type_name.short_description = 'Request device type'

    actions = [cancel_action]
    list_filter = ('status', 'requested_device_type', 'requested_device__hostname', 'actual_device')
    raw_id_fields = ['_results_bundle']
    fieldsets = (
        ('Owner', {
            'fields': ('user', 'group', 'submitter', 'submit_token', 'is_public')}),
        ('Request', {
            'fields': ('requested_device', 'requested_device_type', 'priority', 'health_check')}),
        ('Advanced properties', {
            'fields': ('description', 'tags', 'sub_id', 'target_group', 'vm_group')}),
        ('Current status', {
            'fields': ('actual_device', 'status', 'log_file')}),
        ('Results & Failures', {
            'fields': ('failure_tags', 'failure_comment', '_results_link', '_results_bundle')}),
    )
    list_display = ('id', 'status', 'submitter', 'requested_device_type_name', 'requested_device_hostname',
                    'actual_device', 'health_check', 'submit_time', 'start_time', 'end_time')


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
    def has_health_check(self, obj):
        return obj.health_check_job != ""
    has_health_check.boolean = True

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

    list_filter = ('name', 'display', 'cores',
                   'architecture', 'processor')
    list_display = ('name', 'has_health_check', 'display', 'owners_only',
                    'architecture_name', 'processor_name', 'cpu_model_name',
                    'list_of_cores', 'bit_count')


def hide_worker_action(modeladmin, request, queryset):
    for worker in queryset.filter(display=True):
        worker.display = False
        worker.save()
hide_worker_action.short_description = "Hide selected worker(s)"


def show_worker_action(modeladmin, request, queryset):
    for worker in queryset.filter(display=False):
        worker.display = True
        worker.save()
show_worker_action.short_description = "Show selected worker(s)"


class WorkerAdmin(admin.ModelAdmin):
    actions = [hide_worker_action, show_worker_action]
    list_display = ('hostname', 'display', 'ip_address', 'is_master',
                    'uptime', 'arch')


class DeviceDictionaryAdmin(admin.ModelAdmin):

    def device_hostname(self, obj):
        device_dict = obj.lookup_device_dictionary()
        return device_dict.hostname

    list_display = ('device_hostname', )
    ordering = ('kee', )  # django is unable to sort other than by database fields.
    actions = []


admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceStateTransition, DeviceStateTransitionAdmin)
admin.site.register(DeviceType, DeviceTypeAdmin)
admin.site.register(TestJob, TestJobAdmin)
admin.site.register(Tag)
admin.site.register(Architecture)
admin.site.register(ProcessorFamily)
admin.site.register(BitWidth)
admin.site.register(Core)
admin.site.register(JobFailureTag)
admin.site.register(Worker, WorkerAdmin)
admin.site.register(DeviceDictionaryTable, DeviceDictionaryAdmin)
