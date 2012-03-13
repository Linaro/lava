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

def health_unknown(modeladmin, request, queryset):
    for device in queryset.filter(health_status=Device.HEALTH_PASS):
        device.health_status = Device.HEALTH_UNKNOWN
        device.save()
health_unknown.short_description = "set health_status to unknown"

class DeviceAdmin(admin.ModelAdmin):
    actions = [online_action, offline_action, health_unknown]
    list_filter = ['device_type', 'status']

admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceStateTransition)
admin.site.register(DeviceType)
admin.site.register(TestJob)
admin.site.register(Tag)
