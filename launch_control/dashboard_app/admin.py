"""
Administration interface of the Dashboard application
"""

from django.contrib import admin
from django.utils.translation import ugettext as _

from launch_control.dashboard_app.models import (
        SoftwarePackage,
        )


class SoftwarePackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'version')
    search_fields = ('name', 'version')


admin.site.register(SoftwarePackage, SoftwarePackageAdmin)
