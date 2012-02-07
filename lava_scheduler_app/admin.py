from django.contrib import admin
from lava_scheduler_app.models import (
    Device, DeviceStateTransition, DeviceType, TestJob, Tag,
    )

admin.site.register(Device)
admin.site.register(DeviceStateTransition)
admin.site.register(DeviceType)
admin.site.register(TestJob)
admin.site.register(Tag)
