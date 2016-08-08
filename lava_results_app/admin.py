# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

"""
Administration interface of the LAVA Results application.
"""

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
    list_display = ('job_pk', 'action_level', 'action_name')
    ordering = ('-testdata__testjob__pk', '-action_level', )

    def job_pk(self, action):
        return action.testdata.testjob.pk


class QueryAdmin(admin.ModelAdmin):
    save_as = True


class TestCaseAdmin(admin.ModelAdmin):
    list_display = ('job_pk', 'suite_name', 'name', 'result')
    ordering = ('-suite__job__pk', 'suite__name', 'name')

    def job_pk(self, testcase):
        return testcase.suite.job.pk

    def suite_name(self, testcase):
        return testcase.suite.name


class TestSetAdmin(admin.ModelAdmin):
    list_display = ('suite', 'name')


class TestSuiteAdmin(admin.ModelAdmin):
    list_display = ('job_pk', 'name')
    ordering = ('-job__pk', 'name')

    def job_pk(self, testsuite):
        return testsuite.job.pk


class BugLinkAdmin(admin.ModelAdmin):
    list_display = ('url', 'content_type', 'content_object')

    def content_type(self, buglink):
        return ContentType.objects.get_for_id(buglink.content_type_id)

    def content_object(self, buglink):
        return ContentType.objects.get_for_id(
            buglink.content_type_id).get_object_for_this_type(
                pk=buglink.object_id).get_absolute_url()


admin.site.register(ActionData, ActionDataAdmin)
admin.site.register(Query, QueryAdmin)
admin.site.register(TestCase, TestCaseAdmin)
admin.site.register(TestSet, TestSetAdmin)
admin.site.register(TestSuite, TestSuiteAdmin)
admin.site.register(BugLink, BugLinkAdmin)
