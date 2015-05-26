# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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
Views for the Results application
Keep to just the response rendering functions
Use results.py for View classes and dbutils for data handling.
"""


from django.template import RequestContext
from django.shortcuts import render_to_response
from lava_server.views import index as lava_index
from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)
from django.shortcuts import (
    get_object_or_404,
)
from lava.utils.lavatable import LavaView
from lava_results_app.results import ResultsView, SuiteView
from lava_results_app.models import TestSuite, TestCase
from lava_results_app.tables import ResultsTable, SuiteTable
from lava_scheduler_app.models import TestJob
from lava_scheduler_app.tables import pklink
from django_tables2 import (
    Column,
    TemplateColumn,
    RequestConfig,
)


@BreadCrumb("Results", parent=lava_index)
def index(request):
    data = ResultsView(request, model=TestSuite, table_class=ResultsTable)
    result_table = ResultsTable(
        data.get_table_data(),
    )
    RequestConfig(request, paginate={"per_page": result_table.length}).configure(result_table)
    return render_to_response(
        "lava_results_app/index.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
            'result_table': result_table,
        }, RequestContext(request))


@BreadCrumb("Query", parent=index)
def query(request):
    return render_to_response(
        "lava_results_app/query.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
        }, RequestContext(request))


@BreadCrumb("Suite {job} {pk}", parent=index, needs=['job', 'pk'])
def suite(request, job, pk):
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    job = get_object_or_404(TestJob, pk=job)
    data = SuiteView(request, model=TestCase, table_class=SuiteTable)
    suite_table = SuiteTable(
        data.get_table_data().filter(suite=test_suite)
    )
    RequestConfig(request, paginate={"per_page": suite_table.length}).configure(suite_table)
    return render_to_response(
        "lava_results_app/suite.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
            'job': job,
            'job_link': pklink(job),
            'suite_name': pk,
            'suite_table': suite_table,
        }, RequestContext(request))


@BreadCrumb("Test case {job} {pk} {case}", parent=index, needs=['job', 'pk', 'case'])
def testcase(request, job, pk, case):
    """
    Each testcase can appear multiple times in the same testsuite and testjob,
    the action_level distinguishes each testcase.
    :param request: http request object
    :param job: ID of the TestJob
    :param pk: the name of the TestSuite
    :param case: the name of one or more TestCase objects in the TestSuite
    """
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    job = get_object_or_404(TestJob, pk=job)
    test_cases = TestCase.objects.filter(name=case, suite=test_suite)
    return render_to_response(
        "lava_results_app/case.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
            'job': job,
            'suite': test_suite,
            'job_link': pklink(job),
            'test_cases': test_cases,
        }, RequestContext(request))


@BreadCrumb("Test job {job}", parent=index, needs=['job'])
def testjob(request, job):
    job = get_object_or_404(TestJob, pk=job)
    data = ResultsView(request, model=TestSuite, table_class=ResultsTable)
    suite_table = ResultsTable(
        data.get_table_data().filter(job=job)
    )
    RequestConfig(request, paginate={"per_page": suite_table.length}).configure(suite_table)
    return render_to_response(
        "lava_results_app/job.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
            'job': job,
            'job_link': pklink(job),
            'suite_table': suite_table,
        }, RequestContext(request))
