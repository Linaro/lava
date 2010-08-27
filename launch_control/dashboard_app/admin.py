"""
Administration interface of the Dashboard application
"""

from django.contrib import admin
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext as _

from launch_control.dashboard_app.models import (
        HardwareDevice,
        NamedAttribute,
        SoftwarePackage,
        )


class SoftwarePackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'version')
    search_fields = ('name', 'version')


class HardwareDeviceAdmin(admin.ModelAdmin):
    class NamedAttributeInline(generic.GenericTabularInline):
        model = NamedAttribute
    list_display = ('description', 'device_type')
    search_fields = ('description',)
    inlines = [NamedAttributeInline]


admin.site.register(HardwareDevice, HardwareDeviceAdmin)
admin.site.register(SoftwarePackage, SoftwarePackageAdmin)
