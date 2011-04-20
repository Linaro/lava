from django.contrib import admin

from lava.scheduler.scheduler_app.models import (
    Device,
    DeviceType,
    Tag,
    TestSuite,
    TestCase,
    )

admin.site.register(Device)
admin.site.register(DeviceType)
admin.site.register(Tag)
admin.site.register(TestSuite)
admin.site.register(TestCase)
