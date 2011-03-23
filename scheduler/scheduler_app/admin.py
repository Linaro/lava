from scheduler_app.models import Device, TestSuite, TestCase
from django.contrib import admin

admin.site.register(Device)
admin.site.register(TestSuite)
admin.site.register(TestCase)
