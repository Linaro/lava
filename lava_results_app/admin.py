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

from lava_results_app.models import (
    ActionData,
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


admin.site.register(ActionData, ActionDataAdmin)
admin.site.register(Query, QueryAdmin)
admin.site.register(TestCase, TestCaseAdmin)
admin.site.register(TestSet, TestSetAdmin)
admin.site.register(TestSuite, TestSuiteAdmin)
