# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import warnings

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q

from lava_scheduler_app.models import (
    Alias,
    Architecture,
    BitWidth,
    Core,
    Device,
    DeviceType,
    GroupDevicePermission,
    GroupDeviceTypePermission,
    GroupWorkerPermission,
    JobFailureTag,
    NotificationRecipient,
    ProcessorFamily,
    RemoteArtifactsAuth,
    Tag,
    TestJob,
    User,
    Worker,
)
from linaro_django_xmlrpc.models import AuthToken

# django admin API itself isn't pylint clean, so some settings must be suppressed.


class GroupObjectPermissionInline(admin.TabularInline):
    extra = 0
    supported_permissions = (
        DeviceType.PERMISSIONS_PRIORITY
        + Device.PERMISSIONS_PRIORITY
        + Worker.PERMISSIONS_PRIORITY
    )

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        supported_codenames = [x.split(".")[1] for x in self.supported_permissions]
        if db_field.name == "permission":
            kwargs["queryset"] = Permission.objects.filter(
                content_type__model=self.parent_model._meta.object_name.lower(),
                codename__in=supported_codenames,
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class GroupDeviceTypePermissionInline(GroupObjectPermissionInline):
    model = GroupDeviceTypePermission
    extra = 0


class GroupDevicePermissionInline(GroupObjectPermissionInline):
    model = GroupDevicePermission
    extra = 0


class GroupWorkerPermissionInline(GroupObjectPermissionInline):
    model = GroupWorkerPermission
    extra = 0


class AliasAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, _, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("name",)
        return self.readonly_fields

    list_display = ("name", "device_type")


class ArchitectureAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, _, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("name",)
        return self.readonly_fields


class BitWidthAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, _, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("width",)
        return self.readonly_fields


class CoreAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, _, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("name",)
        return self.readonly_fields


def expire_user_action(modeladmin, request, queryset):
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


expire_user_action.short_description = "Expire user account"


class CustomGroupAdminForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        User.objects.all(),
        widget=admin.widgets.FilteredSelectMultiple("Users", False),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            initial_users = self.instance.user_set.values_list("pk", flat=True)
            self.initial["users"] = initial_users

    def save(self, *args, **kwargs):
        kwargs["commit"] = True
        return super().save(*args, **kwargs)

    def save_m2m(self):
        self.instance.user_set.clear()
        self.instance.user_set.add(*self.cleaned_data["users"])


class CustomGroupAdmin(GroupAdmin):
    form = CustomGroupAdminForm


class RemoteArtifactsAuthInline(admin.TabularInline):
    model = RemoteArtifactsAuth
    extra = 0


class CustomUserAdmin(UserAdmin):
    actions = [expire_user_action]

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE

    inlines = [RemoteArtifactsAuthInline]


#  Setup the override in the django admin interface at startup.
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)


def cancel_action(modeladmin, request, queryset):
    with transaction.atomic():
        for testjob in queryset:
            # TODO: hacky. until django 2.0+ is used and select_for_update gets
            # the 'of' argument.
            warnings.warn(
                "select_for_update should be applied to the whole queryset at once, once we upgrade to django 2+",
                DeprecationWarning,
            )
            testjob = TestJob.objects.select_for_update().get(pk=testjob.pk)
            if testjob.can_cancel(request.user):
                if testjob.is_multinode:
                    for job in testjob.sub_jobs_list:
                        job.go_state_canceling()
                        job.save()
                else:
                    testjob.go_state_canceling()
                    testjob.save()


cancel_action.short_description = "cancel selected jobs"


def fail_action(modeladmin, request, queryset):
    if request.user.is_superuser:
        with transaction.atomic():
            for testjob in queryset.filter(state=TestJob.STATE_CANCELING):
                # TODO: hacky. until django 2.0+ is used and select_for_update
                # gets the 'of' argument.
                warnings.warn(
                    "select_for_update should be applied to the whole queryset at once, once we upgrade to django 2+",
                    DeprecationWarning,
                )
                testjob = TestJob.objects.select_for_update().get(pk=testjob.pk)
                testjob.go_state_finished(TestJob.HEALTH_INCOMPLETE)
                testjob.save()


fail_action.short_description = "fail selected jobs"


class ActiveDevicesFilter(admin.SimpleListFilter):
    title = "Active devices"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return (("NoRetired", "Exclude retired"), ("CurrentJob", "With a current Job"))

    def queryset(self, request, queryset):
        if self.value() == "NoRetired":
            return queryset.exclude(health=Device.HEALTH_RETIRED).order_by("hostname")
        if self.value() == "CurrentJob":
            return queryset.filter(
                state__in=[Device.STATE_RESERVED, Device.STATE_RUNNING]
            ).order_by("hostname")


class ActualDeviceFilter(admin.SimpleListFilter):
    title = "Actual Device (except retired)"
    parameter_name = "actual_device"

    def lookups(self, request, model_admin):
        list_of_types = []
        queryset = Device.objects.exclude(health=Device.HEALTH_RETIRED).order_by(
            "hostname"
        )
        for dev_type in queryset:
            list_of_types.append((str(dev_type.hostname), dev_type.hostname))
        return sorted(list_of_types, key=lambda tp: tp[1])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(actual_device__hostname=self.value())
        return queryset.order_by("actual_device__hostname")


class DeviceTypeFilter(admin.SimpleListFilter):
    title = "Device Type"
    parameter_name = "device_type"

    def lookups(self, request, model_admin):
        list_of_types = []
        queryset = DeviceType.objects.all()
        for dev_type in queryset:
            list_of_types.append((str(dev_type.name), dev_type.name))
        return sorted(list_of_types, key=lambda tp: tp[1])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(device_type__name=self.value())
        return queryset.order_by("device_type__name")


class RequestedDeviceTypeFilter(admin.SimpleListFilter):
    title = "Requested Device Type"
    parameter_name = "requested_device_type"

    def lookups(self, request, model_admin):
        list_of_types = []
        queryset = DeviceType.objects.order_by("name")
        for dev_type in queryset:
            list_of_types.append((str(dev_type.name), dev_type.name))
        return sorted(list_of_types, key=lambda tp: tp[1])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(requested_device_type__name=self.value())
        return queryset.order_by("requested_device_type__name")


def _update_devices_health(request, queryset, health):
    with transaction.atomic():
        for device in queryset:
            # TODO: hacky. until django 2.0+ is used and select_for_update gets
            # the 'of' argument.
            warnings.warn(
                "select_for_update should be applied to the whole queryset at once, once we upgrade to django 2+",
                DeprecationWarning,
            )
            device = Device.objects.select_for_update().get(pk=device.pk)

            old_health_display = device.get_health_display()
            device.health = health
            device.save()
            device.log_admin_entry(
                request.user,
                "%s → %s" % (old_health_display, device.get_health_display()),
            )


def device_health_good(modeladmin, request, queryset):
    _update_devices_health(request, queryset, Device.HEALTH_GOOD)


def device_health_unknown(modeladmin, request, queryset):
    _update_devices_health(request, queryset, Device.HEALTH_UNKNOWN)


def device_health_maintenance(modeladmin, request, queryset):
    _update_devices_health(request, queryset, Device.HEALTH_MAINTENANCE)


def device_health_retired(modeladmin, request, queryset):
    _update_devices_health(request, queryset, Device.HEALTH_RETIRED)


device_health_good.short_description = "Update health of selected devices to Good"
device_health_unknown.short_description = "Update health of selected devices to Unknown"
device_health_maintenance.short_description = (
    "Update health of selected devices to Maintenance"
)
device_health_retired.short_description = "Update health of selected devices to Retired"


class DeviceAdmin(admin.ModelAdmin):
    list_filter = (
        DeviceTypeFilter,
        "state",
        ActiveDevicesFilter,
        "health",
        "worker_host",
        "is_synced",
    )
    raw_id_fields = ["last_health_report_job"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("worker_host", "device_type")
            .prefetch_related(
                Prefetch(
                    "testjobs",
                    queryset=TestJob.objects.filter(~Q(state=TestJob.STATE_FINISHED)),
                    to_attr="running_jobs",
                )
            )
        )

    def has_health_check(self, obj):
        return bool(obj.get_health_check())

    has_health_check.boolean = True
    has_health_check.short_description = "HC"

    def health_check_enabled(self, obj):
        return not obj.device_type.disable_health_check

    health_check_enabled.boolean = True
    health_check_enabled.short_description = "HC enabled"

    def get_readonly_fields(self, _, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("hostname",)
        return self.readonly_fields

    def valid_device(self, obj):
        return bool(obj.is_valid())

    valid_device.boolean = True
    valid_device.short_description = "Config"

    def device_dictionary_jinja(self, obj):
        return obj.load_configuration(output_format="raw")

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE

    fieldsets = (
        (
            "Properties",
            {"fields": ("hostname", "device_type", "worker_host", "device_version")},
        ),
        ("Device owner", {"fields": (("physical_owner", "physical_group"),)}),
        (
            "Status",
            {
                "fields": (
                    ("state", "health"),
                    ("last_health_report_job", "current_job"),
                )
            },
        ),
        (
            "Advanced properties",
            {
                "fields": (
                    "description",
                    "is_synced",
                    "tags",
                    ("device_dictionary_jinja"),
                ),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ("device_dictionary_jinja", "state", "current_job")
    list_display = (
        "hostname",
        "device_type",
        "current_job",
        "worker_host",
        "state",
        "health",
        "has_health_check",
        "health_check_enabled",
        "valid_device",
        "is_synced",
    )
    search_fields = ("hostname", "device_type__name")
    ordering = ["hostname"]
    actions = [
        device_health_good,
        device_health_unknown,
        device_health_maintenance,
        device_health_retired,
    ]
    inlines = [GroupDevicePermissionInline]


class TestJobAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("requested_device_type", "actual_device", "submitter")
        )

    def requested_device_type_name(self, obj):
        return "" if obj.requested_device_type is None else obj.requested_device_type

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE

    requested_device_type_name.short_description = "Request device type"
    actions = [cancel_action, fail_action]
    list_filter = ("state", RequestedDeviceTypeFilter, ActualDeviceFilter, "submitter")
    fieldsets = (
        ("Owner", {"fields": ("submitter", "viewing_groups", "is_public")}),
        ("Request", {"fields": ("requested_device_type", "priority", "health_check")}),
        (
            "Advanced properties",
            {"fields": ("description", "tags", "sub_id", "target_group")},
        ),
        ("Current status", {"fields": ("actual_device", "state", "health")}),
        ("Results & Failures", {"fields": ("failure_tags", "failure_comment")}),
    )
    readonly_fields = ("state",)
    list_display = (
        "id",
        "state",
        "health",
        "submitter",
        "requested_device_type_name",
        "actual_device",
        "health_check",
        "submit_time",
        "start_time",
        "end_time",
    )
    ordering = ["-submit_time"]


def disable_health_check_action(modeladmin, request, queryset):
    queryset.update(disable_health_check=False)


disable_health_check_action.short_description = "disable health checks"


class DeviceTypeAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("architecture", "bits", "processor")
        )

    def architecture_name(self, obj):
        if obj.architecture:
            return obj.architecture
        return ""

    architecture_name.short_description = "arch"

    def processor_name(self, obj):
        if obj.processor:
            return obj.processor
        return ""

    processor_name.short_description = "proc"

    def cpu_model_name(self, obj):
        if obj.cpu_model:
            return obj.cpu_model
        return ""

    cpu_model_name.short_description = "cpu"

    def bit_count(self, obj):
        if obj.bits:
            return obj.bits
        return ""

    bit_count.short_description = "bits"

    def list_of_cores(self, obj):
        if obj.core_count:
            return "%s x %s" % (
                obj.core_count,
                ",".join([core.name for core in obj.cores.all().order_by("name")]),
            )
        return ""

    list_of_cores.short_description = "cores"

    def get_readonly_fields(self, _, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("name",)
        return self.readonly_fields

    def health_check_enabled(self, obj):
        return not obj.disable_health_check

    health_check_enabled.boolean = True
    health_check_enabled.short_description = "HC enabled"

    def health_check_frequency(self, device_type):
        if device_type.health_denominator == DeviceType.HEALTH_PER_JOB:
            return "every %d jobs" % device_type.health_frequency
        return "every %d hours" % device_type.health_frequency

    health_check_frequency.short_description = "HC frequency"

    actions = [disable_health_check_action]
    list_filter = ("name", "display", "cores", "architecture", "processor")
    list_display = (
        "name",
        "display",
        "health_check_enabled",
        "health_check_frequency",
        "architecture_name",
        "processor_name",
        "cpu_model_name",
        "list_of_cores",
        "bit_count",
    )
    fieldsets = (
        ("Properties", {"fields": ("name", "description", "display")}),
        (
            "Health checks",
            {
                "fields": (
                    ("health_frequency", "health_denominator"),
                    "disable_health_check",
                )
            },
        ),
        (
            "Meta data",
            {
                "fields": (
                    "architecture",
                    "processor",
                    ("cores", "core_count"),
                    "bits",
                    "cpu_model",
                )
            },
        ),
    )
    ordering = ["name"]
    inlines = [GroupDeviceTypePermissionInline]


def worker_health_active(ModelAdmin, request, queryset):
    with transaction.atomic():
        for worker in queryset.select_for_update():
            worker.go_health_active(request.user)
            worker.save()


def worker_health_maintenance(ModelAdmin, request, queryset):
    with transaction.atomic():
        for worker in queryset.select_for_update():
            worker.go_health_maintenance(request.user)
            worker.save()


def worker_health_retired(ModelAdmin, request, queryset):
    with transaction.atomic():
        for worker in queryset.select_for_update():
            worker.go_health_retired(request.user)
            worker.save()


worker_health_active.short_description = "Update health of selected workers to Active"
worker_health_maintenance.short_description = (
    "Update health of selected workers to Maintenance"
)
worker_health_retired.short_description = "Update health of selected workers to Retired"


class WorkerAdmin(admin.ModelAdmin):
    list_display = ("hostname", "state", "health")
    readonly_fields = ("state",)
    ordering = ["hostname"]
    actions = [worker_health_active, worker_health_maintenance, worker_health_retired]
    inlines = [GroupWorkerPermissionInline]

    def get_readonly_fields(self, _, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("hostname",)
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE


class TagLowerForm(forms.ModelForm):
    def clean_name(self):
        name = self.cleaned_data["name"]
        if name != name.lower():
            raise ValidationError("Tag names are case-insensitive.")
        return name


class TagAdmin(admin.ModelAdmin):
    form = TagLowerForm
    list_display = ("name", "description")
    ordering = ["name"]

    def get_readonly_fields(self, _, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("name",)
        return self.readonly_fields


class NotificationRecipientAdmin(admin.ModelAdmin):
    def handle(self, obj):
        if obj.method == NotificationRecipient.EMAIL:
            return obj.email_address
        else:
            return "%s@%s" % (obj.irc_handle, obj.irc_server_name)

    list_display = ("method", "handle", "status")
    list_filter = ("method", "status")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE


admin.site.register(Alias, AliasAdmin)
admin.site.register(Architecture, ArchitectureAdmin)
admin.site.register(BitWidth, BitWidthAdmin)
admin.site.register(Core, CoreAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceType, DeviceTypeAdmin)
admin.site.register(JobFailureTag)
admin.site.register(NotificationRecipient, NotificationRecipientAdmin)
admin.site.register(ProcessorFamily)
admin.site.register(TestJob, TestJobAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Worker, WorkerAdmin)
