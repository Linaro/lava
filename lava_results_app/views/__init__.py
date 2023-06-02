# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#         Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Views for the Results application
Keep to just the response rendering functions
"""

import contextlib
import csv
import logging
import os
from collections import OrderedDict
from json import dumps as json_dumps

import yaml
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.http import Http404
from django.http.response import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, loader, render
from django.views.decorators.http import require_POST
from django_tables2 import RequestConfig

from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_results_app.dbutils import export_testsuite
from lava_results_app.models import (
    QueryCondition,
    TestCase,
    TestData,
    TestSet,
    TestSuite,
)
from lava_results_app.tables import (
    ResultsIndexTable,
    ResultsTable,
    SuiteTable,
    TestJobResultsTable,
)
from lava_results_app.utils import (
    StreamEcho,
    check_request_auth,
    export_testcase,
    get_testcases_with_limit,
    testcase_export_fields,
)
from lava_scheduler_app.models import TestJob
from lava_scheduler_app.tables import pklink
from lava_scheduler_app.views import get_restricted_job
from lava_server.bread_crumbs import BreadCrumb, BreadCrumbTrail
from lava_server.compat import djt2_paginator_class
from lava_server.lavatable import LavaView
from lava_server.views import index as lava_index


class ResultsView(LavaView):
    """
    Base results view
    """

    def get_queryset(self):
        return (
            TestSuite.objects.all()
            .select_related(
                "job",
                "job__actual_device",
                "job__actual_device__device_type",
                "job__submitter",
            )
            .prefetch_related("job__viewing_groups")
        )


class SuiteView(LavaView):
    """
    View of a test suite
    """

    def get_queryset(self):
        return TestCase.objects.all().order_by("logged").select_related("suite")


@BreadCrumb("Results", parent=lava_index)
def index(request):
    data = ResultsView(request, model=TestSuite, table_class=ResultsTable)
    result_table = ResultsIndexTable(data.get_table_data())
    RequestConfig(
        request, paginate={"per_page": result_table.length, **djt2_paginator_class()}
    ).configure(result_table)
    template = loader.get_template("lava_results_app/index.html")
    return HttpResponse(
        template.render(
            {
                "bread_crumb_trail": BreadCrumbTrail.leading_to(index),
                "content_type_id": ContentType.objects.get_for_model(TestSuite).id,
                "result_table": result_table,
            },
            request=request,
        )
    )


@BreadCrumb("Query", parent=index)
def query(request):
    template = loader.get_template("lava_results_app/query_list.html")
    return HttpResponse(
        template.render(
            {"bread_crumb_trail": BreadCrumbTrail.leading_to(index)}, request=request
        )
    )


@BreadCrumb("Test job {job}", parent=index, needs=["job"])
def testjob(request, job):
    job = get_restricted_job(request.user, pk=job, request=request)
    data = ResultsView(request, model=TestSuite, table_class=TestJobResultsTable)
    suite_table = TestJobResultsTable(
        data.get_table_data().filter(job=job), request=request
    )
    failed_definitions = []
    yaml_dict = OrderedDict()

    if hasattr(job, "testdata"):
        for data in job.testdata.attributes.all().order_by("name"):
            yaml_dict[str(data.name)] = str(data.value)

    RequestConfig(request, paginate={"per_page": suite_table.length}).configure(
        suite_table
    )
    template = loader.get_template("lava_results_app/job.html")
    return HttpResponse(
        template.render(
            {
                "bread_crumb_trail": BreadCrumbTrail.leading_to(testjob, job=job.id),
                "job": job,
                "job_link": pklink(job),
                "suite_table": suite_table,
                "metadata": yaml_dict,
                "condition_choices": json_dumps(
                    QueryCondition.get_condition_choices(job)
                ),
                "available_content_types": json_dumps(
                    QueryCondition.get_similar_job_content_types()
                ),
            },
            request=request,
        )
    )


def testjob_csv(request, job):
    job = get_object_or_404(TestJob, pk=job)
    check_request_auth(request, job)

    def testjob_stream(test_cases, pseudo_buffer):
        fieldnames = testcase_export_fields()
        writer = csv.DictWriter(pseudo_buffer, fieldnames=fieldnames)
        # writer.writeheader does not return the string while writer.writerow
        # does. Copy writeheader code from csv.py and yield the value.
        yield writer.writerow(dict(zip(fieldnames, fieldnames)))

        for test_case in test_cases:
            yield writer.writerow(export_testcase(test_case))

    test_cases = TestCase.objects.filter(suite__job=job).select_related("suite")

    pseudo_buffer = StreamEcho()
    response = StreamingHttpResponse(
        testjob_stream(test_cases, pseudo_buffer), content_type="text/csv"
    )
    filename = "lava_%s.csv" % job.id
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    return response


def testjob_yaml(request, job):
    job = get_object_or_404(TestJob, pk=job)
    check_request_auth(request, job)

    test_cases = TestCase.objects.filter(suite__job=job).select_related("suite")

    def test_case_stream():
        for test_case in test_cases:
            yield yaml_safe_dump([export_testcase(test_case)])

    response = StreamingHttpResponse(test_case_stream(), content_type="text/yaml")
    filename = "lava_%s.yaml" % job.id
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    return response


def testjob_yaml_summary(request, job):
    job = get_object_or_404(TestJob, pk=job)
    check_request_auth(request, job)
    suites = job.testsuite_set.all()
    response = HttpResponse(content_type="text/yaml")
    filename = "lava_%s_summary.yaml" % job.id
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    yaml_list = []
    for test_suite in suites:
        yaml_list.append(export_testsuite(test_suite))
    yaml_safe_dump(yaml_list, response)
    return response


@BreadCrumb("Suite {pk}", parent=testjob, needs=["job", "pk"])
def suite(request, job, pk):
    job = get_restricted_job(request.user, pk=job, request=request)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    data = SuiteView(request, model=TestCase, table_class=SuiteTable)
    suite_table = SuiteTable(
        data.get_table_data().filter(suite=test_suite), request=request
    )
    RequestConfig(request, paginate={"per_page": suite_table.length}).configure(
        suite_table
    )
    template = loader.get_template("lava_results_app/suite.html")
    return HttpResponse(
        template.render(
            {
                "bread_crumb_trail": BreadCrumbTrail.leading_to(
                    suite, pk=pk, job=job.id
                ),
                "job": job,
                "job_link": pklink(job),
                "testsuite_content_type_id": ContentType.objects.get_for_model(
                    TestSuite
                ).id,
                "suite_name": pk,
                "suite_id": test_suite.id,
                "suite_table": suite_table,
            },
            request=request,
        )
    )


def suite_csv(request, job, pk):
    job = get_object_or_404(TestJob, pk=job)
    check_request_auth(request, job)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    querydict = request.GET
    offset = int(querydict.get("offset", default=0))
    limit = int(querydict.get("limit", default=0))
    response = HttpResponse(content_type="text/csv")
    filename = "lava_%s.csv" % test_suite.name
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    writer = csv.DictWriter(
        response,
        quoting=csv.QUOTE_ALL,
        extrasaction="ignore",
        fieldnames=testcase_export_fields(),
    )
    writer.writeheader()
    testcases = get_testcases_with_limit(test_suite, limit, offset)
    for row in testcases:
        writer.writerow(export_testcase(row))
    return response


def suite_csv_stream(request, job, pk):
    """
    Django is designed for short-lived requests.
    Streaming responses will tie a worker process for the entire duration of the response.
    This may result in poor performance.
    Generally speaking, you should perform expensive tasks outside of the
    request-response cycle, rather than resorting to a streamed response.
    https://docs.djangoproject.com/en/3.2/ref/request-response/#django.http.StreamingHttpResponse
    https://docs.djangoproject.com/en/3.2/howto/outputting-csv/
    """
    job = get_object_or_404(TestJob, pk=job)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    check_request_auth(request, job)
    querydict = request.GET
    offset = int(querydict.get("offset", default=0))
    limit = int(querydict.get("limit", default=0))

    pseudo_buffer = StreamEcho()
    writer = csv.writer(pseudo_buffer)
    testcases = get_testcases_with_limit(test_suite, limit, offset)
    response = StreamingHttpResponse(
        (writer.writerow(export_testcase(row)) for row in testcases),
        content_type="text/csv",
    )
    filename = "lava_stream_%s.csv" % test_suite.name
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    return response


def suite_yaml(request, job, pk):
    job = get_object_or_404(TestJob, pk=job)
    check_request_auth(request, job)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    querydict = request.GET
    offset = int(querydict.get("offset", default=0))
    limit = int(querydict.get("limit", default=0))
    response = HttpResponse(content_type="text/yaml")
    filename = "lava_%s.yaml" % test_suite.name
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    yaml_list = []
    testcases = get_testcases_with_limit(test_suite, limit, offset)
    for test_case in testcases:
        yaml_list.append(export_testcase(test_case))
    yaml_safe_dump(yaml_list, response)
    return response


def suite_testcase_count(request, job, pk):
    job = get_object_or_404(TestJob, pk=job)
    check_request_auth(request, job)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    test_case_count = test_suite.testcase_set.all().count()
    return HttpResponse(test_case_count, content_type="text/plain")


def metadata_export(request, job):
    """
    Dispatcher adds some metadata,
    Job submitter can add more.
    CSV is not supported as the user-supplied metadata can
    include nested dicts or lists.
    """
    job = get_object_or_404(TestJob, pk=job)
    check_request_auth(request, job)
    # testdata from job & export
    if not hasattr(job, "testdata"):
        raise Http404("No TestData present in test job.")
    response = HttpResponse(content_type="text/yaml")
    filename = "lava_metadata_%s.yaml" % job.id
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    yaml_dict = {}
    # hide internal python objects
    for data in job.testdata.attributes.all():
        yaml_dict[str(data.name)] = str(data.value)
    yaml_safe_dump(yaml_dict, response)
    return response


@BreadCrumb("TestSet {case}", parent=testjob, needs=["job", "pk", "ts", "case"])
def testset(request, job, ts, pk, case):
    job = get_restricted_job(request.user, pk=job, request=request)
    test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    test_set = get_object_or_404(TestSet, name=ts, suite=test_suite)
    test_cases = TestCase.objects.filter(name=case, test_set=test_set)
    template = loader.get_template("lava_results_app/case.html")
    return HttpResponse(
        template.render(
            {
                "bread_crumb_trail": BreadCrumbTrail.leading_to(
                    testset, pk=pk, job=job.id, ts=ts, case=case
                ),
                "job": job,
                "suite": test_suite,
                "job_link": pklink(job),
                "test_cases": test_cases,
            },
            request=request,
        )
    )


@BreadCrumb("Test case {case_id}", parent=suite, needs=["job", "pk", "case_id"])
def testcase(request, case_id, job=None, pk=None):
    """
    Each testcase can appear multiple times in the same testsuite and testjob,
    the action_data.action_level distinguishes each testcase.
    This view supports multiple ways to obtain test case/set. First is by
    test case ID, second by job ID, suite name and test case name and third by
    job ID, suite name and test set name.
    :param request: http request object
    :param job: ID of the TestJob
    :param pk: the name of the TestSuite
    :param case_id: the name or ID of one TestCase object in the TestSuite
    """
    test_sets = None
    try:
        case = TestCase.objects.get(pk=case_id)
    except (TestCase.DoesNotExist, ValueError):
        case = TestCase.objects.filter(
            name=case_id, suite__name=pk, suite__job__id=job
        ).first()
        if not case:
            test_sets = TestSet.objects.filter(name=case_id)
            if not test_sets:
                raise Http404("No TestCase/TestSet matches the given parameters.")
    if not job:
        job = case.suite.job
        # Auth check purposes only.
        job = get_restricted_job(request.user, pk=job.id, request=request)
    else:
        job = get_restricted_job(request.user, pk=job, request=request)
    if not pk:
        test_suite = case.suite
    else:
        test_suite = get_object_or_404(TestSuite, name=pk, job=job)
    if test_sets:
        # No test case was found.
        test_sets = test_sets.filter(suite=test_suite)
        test_cases = TestCase.objects.none()
    else:
        test_cases = TestCase.objects.filter(name=case.name, suite=test_suite)
    extra_source = {}
    logger = logging.getLogger("lava-master")
    for extra_case in test_cases:
        try:
            f_metadata = yaml_safe_load(extra_case.metadata)
            if not f_metadata:
                continue
        except (TypeError, yaml.YAMLError):
            logger.info("Unable to load extra case metadata for %s", extra_case)
            continue
        try:
            extra_data = f_metadata.get("extra")
            if extra_data and os.path.exists(extra_data):
                with open(f_metadata["extra"]) as extra_file:
                    items = yaml_safe_load(extra_file)
                # hide the !!python OrderedDict prefix from the output.
                for key, value in items.items():
                    extra_source.setdefault(extra_case.id, "")
                    extra_source[extra_case.id] += "%s: %s\n" % (key, value)
        except (AttributeError, TypeError, yaml.YAMLError):
            # In some old version of LAVA, extra_data is not a string but an OrderedDict
            # In this case, just skip it.
            pass
    template = loader.get_template("lava_results_app/case.html")
    trail_id = case.id if case else test_sets.first().name
    return HttpResponse(
        template.render(
            {
                "bread_crumb_trail": BreadCrumbTrail.leading_to(
                    testcase, pk=test_suite.name, job=job.id, case_id=trail_id
                ),
                "job": job,
                "sets": test_sets,
                "suite": test_suite,
                "job_link": pklink(job),
                "extra_source": extra_source,
                "test_cases": test_cases,
            },
            request=request,
        )
    )


def testcase_yaml(request, pk):
    testcase = get_object_or_404(TestCase, pk=pk)
    check_request_auth(request, testcase.suite.job)
    response = HttpResponse(content_type="text/yaml")
    filename = "lava_%s.yaml" % testcase.name
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename
    yaml_safe_dump(export_testcase(testcase), response)
    return response
