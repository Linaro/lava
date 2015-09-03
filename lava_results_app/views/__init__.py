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
"""
import csv
import yaml
from django.template import RequestContext
from django.http.response import HttpResponse, StreamingHttpResponse
from django.shortcuts import render_to_response
from lava_server.views import index as lava_index
from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)
from django.shortcuts import get_object_or_404
from lava_results_app.models import TestSuite, TestCase
from lava_results_app.tables import ResultsTable, SuiteTable
from lava_results_app.utils import StreamEcho
from lava_results_app.dbutils import export_testcase, testcase_export_fields
from lava_scheduler_app.models import TestJob
from lava_scheduler_app.tables import pklink
from django_tables2 import RequestConfig

from lava_results_app.models import TestSuite, TestCase
from lava.utils.lavatable import LavaView


class ResultsView(LavaView):
    """
    Base results view
    """
    def get_queryset(self):
        return TestSuite.objects.all().order_by('-job__id')


class SuiteView(LavaView):
    """
    View of a test suite
    """
    def get_queryset(self):
        return TestCase.objects.all().order_by('logged')


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
        "lava_results_app/query_list.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index),
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
            'bread_crumb_trail': BreadCrumbTrail.leading_to(testjob, job=job.id),
            'job': job,
            'job_link': pklink(job),
            'suite_table': suite_table,
        }, RequestContext(request))


def testjob_csv(request, job):
    job = get_object_or_404(TestJob, pk=job)
    response = HttpResponse(content_type='text/csv')
    filename = "lava_%s.csv" % job.id
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    writer = csv.DictWriter(
        response,
        quoting=csv.QUOTE_ALL,
        extrasaction='ignore',
        fieldnames=testcase_export_fields())
    writer.writeheader()
    for test_suite in job.test_suites.all():
        for row in test_suite.test_cases.all():
            writer.writerow(export_testcase(row))
    return response


def testjob_yaml(request, job):
    job = get_object_or_404(TestJob, pk=job)
    response = HttpResponse(content_type='text/yaml')
    filename = "lava_%s.yaml" % job.id
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    yaml_list = []
    for test_suite in job.test_suites.all():
        for test_case in test_suite.test_cases.all():
            yaml_list.append(export_testcase(test_case))
    yaml.dump(yaml_list, response)
    return response


@BreadCrumb("Suite {pk}", parent=testjob, needs=['job', 'pk'])
def suite(request, job, pk):
    job = get_object_or_404(TestJob, pk=job)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    data = SuiteView(request, model=TestCase, table_class=SuiteTable)
    suite_table = SuiteTable(
        data.get_table_data().filter(suite=test_suite)
    )
    RequestConfig(request, paginate={"per_page": suite_table.length}).configure(suite_table)
    return render_to_response(
        "lava_results_app/suite.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(suite, pk=pk, job=job.id),
            'job': job,
            'job_link': pklink(job),
            'suite_name': pk,
            'suite_table': suite_table,
        }, RequestContext(request))


def suite_csv(request, job, pk):
    job = get_object_or_404(TestJob, pk=job)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    response = HttpResponse(content_type='text/csv')
    filename = "lava_%s.csv" % test_suite.name
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    writer = csv.DictWriter(
        response,
        quoting=csv.QUOTE_ALL,
        extrasaction='ignore',
        fieldnames=testcase_export_fields())
    writer.writeheader()
    for row in test_suite.test_cases.all():
        writer.writerow(export_testcase(row))
    return response


def suite_csv_stream(request, job, pk):
    """
    Django is designed for short-lived requests.
    Streaming responses will tie a worker process for the entire duration of the response.
    This may result in poor performance.
    Generally speaking, you should perform expensive tasks outside of the
    request-response cycle, rather than resorting to a streamed response.
    https://docs.djangoproject.com/en/1.8/ref/request-response/#django.http.StreamingHttpResponse
    https://docs.djangoproject.com/en/1.8/howto/outputting-csv/
    """
    job = get_object_or_404(TestJob, pk=job)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)

    pseudo_buffer = StreamEcho()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse(
        (writer.writerow(export_testcase(row)) for row in test_suite.test_cases.all()),
        content_type="text/csv")
    filename = "lava_stream_%s.csv" % test_suite.name
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


def suite_yaml(request, job, pk):
    job = get_object_or_404(TestJob, pk=job)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    response = HttpResponse(content_type='text/yaml')
    filename = "lava_%s.yaml" % test_suite.name
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    yaml_list = []
    for test_case in test_suite.test_cases.all():
        yaml_list.append(export_testcase(test_case))
    yaml.dump(yaml_list, response)
    return response


@BreadCrumb("Test case {case}", parent=suite, needs=['job', 'pk', 'case'])
def testcase(request, job, pk, case):
    """
    Each testcase can appear multiple times in the same testsuite and testjob,
    the action_data.action_level distinguishes each testcase.
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
            'bread_crumb_trail': BreadCrumbTrail.leading_to(testcase, pk=pk, job=job.id, case=case),
            'job': job,
            'suite': test_suite,
            'job_link': pklink(job),
            'test_cases': test_cases,
        }, RequestContext(request))
