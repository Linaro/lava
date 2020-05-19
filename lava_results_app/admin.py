# -*- coding: utf-8 -*-
# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

"""
Administration interface of the LAVA Results application.
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from lava_results_app.models import (
    ActionData,
    BugLink,
    Query,
    TestCase,
    TestSet,
    TestSuite,
)


class ActionDataAdmin(admin.ModelAdmin):
    list_display = ("job_pk", "action_level", "action_name")
    list_select_related = ("testdata__testjob",)
    ordering = ("-testdata__testjob__pk", "-action_level")
    raw_id_fields = ("testdata", "testcase")

    def job_pk(self, action):
        return action.testdata.testjob.pk

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE


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


class BugLinkAdmin(admin.ModelAdmin):
    list_display = ("url", "content_type", "content_object")

    def content_type(self, buglink):
        return ContentType.objects.get_for_id(buglink.content_type_id)

    def content_object(self, buglink):
        return (
            ContentType.objects.get_for_id(buglink.content_type_id)
            .get_object_for_this_type(pk=buglink.object_id)
            .get_absolute_url()
        )


admin.site.register(ActionData, ActionDataAdmin)
admin.site.register(Query, QueryAdmin)
admin.site.register(TestCase, TestCaseAdmin)
admin.site.register(TestSet, TestSetAdmin)
admin.site.register(TestSuite, TestSuiteAdmin)
admin.site.register(BugLink, BugLinkAdmin)
