# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Administration interface of the Dashboard application
"""

from django import forms
from django.contrib import admin
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext as _

from dashboard_app.models import (
    Attachment,
    Bundle,
    BundleDeserializationError,
    BundleStream,
    HardwareDevice,
    NamedAttribute,
    SoftwarePackage,
    SoftwareSource,
    Tag,
    Test,
    TestCase,
    TestResult,
    TestRun,
    TestingEffort,
)


class BundleAdmin(admin.ModelAdmin):

    def bundle_stream_pathname(self, bundle):
        return bundle.bundle_stream.pathname
    bundle_stream_pathname.short_description = _("Bundle stream")

    list_display = ('bundle_stream_pathname', 'content_filename',
            'uploaded_by', 'uploaded_on', 'is_deserialized')
    list_filter = ('bundle_stream',)
    readonly_fields = ('is_deserialized',)
    date_hierarchy = 'uploaded_on'
    fieldsets = (
        ('Document', {
            'fields': ('_raw_content', '_gz_content', 'content_filename')}),
        ('Upload Details', {
            'fields': ('bundle_stream', 'uploaded_by')}),
        ('Deserialization', {
            'fields': ('is_deserialized',)}),
    )


class BundleDeserializationErrorAdmin(admin.ModelAdmin):
    list_display = ('bundle', 'error_message')
    search_fields = ('bundle__content_sha1',)


class BundleStreamAdminForm(forms.ModelForm):
    class Meta:
        model = BundleStream

    def clean(self):
        cleaned_data = self.cleaned_data
        if (cleaned_data.get('user', '') is not None and
                cleaned_data.get('group') is not None):
            raise forms.ValidationError('BundleStream cannot have both user '
                    'and name set at the same time')
        return super(BundleStreamAdminForm, self).clean()


class BundleStreamAdmin(admin.ModelAdmin):
    form = BundleStreamAdminForm
    list_display = ('pathname', 'user', 'group', 'slug', 'is_public', 'is_anonymous', 'name')
    list_filter = ('is_public', 'is_anonymous')
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ('pathname',)
    fieldsets = (
            ('Name and description', {
                'fields': ('name', 'slug', 'pathname')}),
            ('Ownership', {
                'fields': ('user', 'group')}),
            ('Access Rights', {
                'fields': ('is_public', 'is_anonymous')}),
            )


class SoftwarePackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'version')
    search_fields = ('name', 'version')


class SoftwareSourceAdmin(admin.ModelAdmin):
    list_display = ('project_name', 'branch_url', 'branch_vcs',
                    'branch_revision', 'commit_timestamp')
    list_filter = ('project_name',)
    search_fields = ('project_name', 'branch_url')


class HardwareDeviceAdmin(admin.ModelAdmin):
    class NamedAttributeInline(generic.GenericTabularInline):
        model = NamedAttribute
    list_display = ('description', 'device_type')
    list_filter = ('device_type',)
    search_fields = ('description',)
    inlines = [NamedAttributeInline]


class TestCaseAdmin(admin.ModelAdmin):
    list_display = ('test_case_id', 'test',)
    list_filter = ('test',)


class TestAdmin(admin.ModelAdmin):
    pass


class TestResultAdmin(admin.ModelAdmin):
    class NamedAttributeInline(generic.GenericTabularInline):
        model = NamedAttribute
    list_display = ('__unicode__', 'test', 'test_case', 'result', 'measurement')
    list_filter = ('test_case', 'result')
    inlines = [NamedAttributeInline]


class TestRunAdmin(admin.ModelAdmin):
    class NamedAttributeInline(generic.GenericTabularInline):
        model = NamedAttribute
    list_filter = ('test'),
    list_display = (
        'test',
        'analyzer_assigned_uuid',
        'bundle',
        'analyzer_assigned_date',
        'import_assigned_date')
    inlines = [NamedAttributeInline]


class TestingEffortAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'project')


admin.site.register(Attachment)
admin.site.register(Bundle, BundleAdmin)
admin.site.register(BundleDeserializationError, BundleDeserializationErrorAdmin)
admin.site.register(BundleStream, BundleStreamAdmin)
admin.site.register(HardwareDevice, HardwareDeviceAdmin)
admin.site.register(SoftwarePackage, SoftwarePackageAdmin)
admin.site.register(SoftwareSource, SoftwareSourceAdmin)
admin.site.register(Test, TestAdmin)
admin.site.register(TestCase, TestCaseAdmin)
admin.site.register(TestResult, TestResultAdmin)
admin.site.register(TestRun, TestRunAdmin)
admin.site.register(Tag)
admin.site.register(TestingEffort, TestingEffortAdmin)
