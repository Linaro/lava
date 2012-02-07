from django.contrib import admin
from lava_scheduler_app.models import (
    Device, DeviceStateTransition, DeviceType, TestJob, Tag,
    )

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

class DeviceAdmin(admin.ModelAdmin):
    actions = [offline_action]
    list_filter = ['device_type', 'status']

admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceStateTransition)
admin.site.register(DeviceType)
admin.site.register(TestJob)
admin.site.register(Tag)
