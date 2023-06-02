# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Administration interface of the LAVA Results application.
"""
from django.conf import settings
from django.contrib import admin

from lava_results_app.models import Query, TestCase, TestSet, TestSuite


class QueryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "query_group", "is_published", "is_archived")
    ordering = ("name", "owner", "query_group", "is_published", "is_archived")
    save_as = True

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE


class TestCaseAdmin(admin.ModelAdmin):
    list_display = ("job_pk", "suite_name", "name", "result")
    list_select_related = ("suite", "suite__job")
    ordering = ("-suite__job__pk", "suite__name", "name")
    raw_id_fields = ("suite",)

    def job_pk(self, testcase):
        return testcase.suite.job.pk

    def suite_name(self, testcase):
        return testcase.suite.name

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE


class TestSetAdmin(admin.ModelAdmin):
    list_display = ("suite", "name")
    raw_id_fields = ("suite",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE


class TestSuiteAdmin(admin.ModelAdmin):
    list_display = ("job_pk", "name")
    list_select_related = ("job",)
    ordering = ("-job__pk", "name")
    raw_id_fields = ("job",)

    def job_pk(self, testsuite):
        return testsuite.job.pk

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE


admin.site.register(Query, QueryAdmin)
admin.site.register(TestCase, TestCaseAdmin)
admin.site.register(TestSet, TestSetAdmin)
admin.site.register(TestSuite, TestSuiteAdmin)
