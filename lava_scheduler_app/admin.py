from django.contrib import admin
from lava_scheduler_app.models import (
    Device, DeviceStateTransition, DeviceType, TestJob, Tag,
    )

# XXX These actions should really go to another screen that asks for a reason.
# Sounds tedious to implement though.

def offline_action(modeladmin, request, queryset):
    for device in queryset:
        if device.can_admin(request.user):
            device.put_into_maintenance_mode(request.user, "admin action")
offline_action.short_description = "take offline"

def online_action(modeladmin, request, queryset):
    for device in queryset:
        if device.can_admin(request.user):
            device.put_into_online_mode(request.user, "admin action")
online_action.short_description = "take online"

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

def health_unknown(modeladmin, request, queryset):
    for device in queryset.filter(health_status=Device.HEALTH_PASS):
        device.health_status = Device.HEALTH_UNKNOWN
        device.save()
health_unknown.short_description = "set health_status to unknown"

class DeviceAdmin(admin.ModelAdmin):
    actions = [online_action, offline_action, health_unknown, retire_action]
    list_filter = ['device_type', 'status']
    raw_id_fields = ['current_job', 'last_health_report_job']


class TestJobAdmin(admin.ModelAdmin):
    raw_id_fields = ['_results_bundle']


class DeviceStateTransitionAdmin(admin.ModelAdmin):
    raw_id_fields = ['job']


admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceStateTransition, DeviceStateTransitionAdmin)
admin.site.register(DeviceType)
admin.site.register(TestJob, TestJobAdmin)
admin.site.register(Tag)
