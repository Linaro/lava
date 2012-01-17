from django.contrib import admin
from lava_scheduler_app.models import (
        Device, DeviceType,
        TestJob, Tag, DeviceHealth,
        )

class DeviceHealthAdmin(admin.ModelAdmin):
    list_display = ('device', 'health')

admin.site.register(Device)
admin.site.register(DeviceType)
admin.site.register(TestJob)
admin.site.register(Tag)
admin.site.register(DeviceHealth, DeviceHealthAdmin)
