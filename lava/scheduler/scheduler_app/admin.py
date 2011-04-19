from django.contrib import admin

from lava.scheduler.scheduler_app.models import (
    Device,
    TestSuite,
    TestCase,
    )

admin.site.register(Device)
admin.site.register(TestSuite)
admin.site.register(TestCase)
