# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
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

import csv
import io
import yaml

from django.http.response import HttpResponse

from lava_results_app.models import TestSuite, TestCase
from lava_results_app.utils import (
    export_testcase,
    get_testcases_with_limit,
    testcase_export_fields,
)
from lava_rest_app.base import views as base_views
from rest_framework import viewsets
from rest_framework_extensions.mixins import NestedViewSetMixin
from rest_framework.response import Response

from . import serializers

try:
    from rest_framework.decorators import detail_route
except ImportError:
    from rest_framework.decorators import action

    def detail_route(methods, suffix):
        return action(detail=True, methods=methods, suffix=suffix)


class TestJobViewSet(base_views.TestJobViewSet):
    """
    List TestJobs visible to the current user.

    You can submit a job via POST request on:

    * `/jobs/`

    The logs, test results and test suites of a specific TestJob are available at:

    * `/jobs/<job_id>/logs/`
    * `/jobs/<job_id>/suites/`

    The test results are also available in JUnit, TAP13, CSV and YAML at:

    * `/jobs/<job_id>/junit/`
    * `/jobs/<job_id>/tap13/`
    * `/jobs/<job_id>/csv/`
    * `/jobs/<job_id>/yaml/`
    """

    def suites(self, request, **kwargs):
        raise NotImplementedError()

    def tests(self, request, **kwargs):
        raise NotImplementedError()

    @detail_route(methods=["get"], suffix="csv")
    def csv(self, request, **kwargs):
        limit = request.query_params.get("limit", None)
        offset = request.query_params.get("offset", None)

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            quoting=csv.QUOTE_ALL,
            extrasaction="ignore",
            fieldnames=testcase_export_fields(),
        )
        writer.writeheader()
        for test_suite in self.get_object().testsuite_set.all():
            for row in test_suite.testcase_set.all():
                writer.writerow(export_testcase(row))

        response = HttpResponse(output.getvalue(), content_type="application/csv")
        response["Content-Disposition"] = (
            "attachment; filename=job_%d.csv" % self.get_object().id
        )
        return response

    @detail_route(methods=["get"], suffix="yaml")
    def yaml(self, request, **kwargs):
        limit = request.query_params.get("limit", None)
        offset = request.query_params.get("offset", None)

        yaml_list = []
        for test_suite in self.get_object().testsuite_set.all():
            for test_case in test_suite.testcase_set.all():
                yaml_list.append(export_testcase(test_case))

        response = HttpResponse(
            yaml.dump(yaml_list, Dumper=yaml.CDumper), content_type="application/yaml"
        )
        response["Content-Disposition"] = (
            "attachment; filename=job_%d.yaml" % self.get_object().id
        )
        return response

    @detail_route(methods=["get"], suffix="metadata")
    def metadata(self, request, **kwargs):
        return Response({"metadata": self.get_object().get_metadata_dict()})


class TestSuiteViewSet(NestedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TestSuite.objects
    serializer_class = serializers.TestSuiteSerializer
    filter_fields = "__all__"

    @detail_route(methods=["get"], suffix="csv")
    def csv(self, request, **kwargs):
        limit = request.query_params.get("limit", None)
        offset = request.query_params.get("offset", None)

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            quoting=csv.QUOTE_ALL,
            extrasaction="ignore",
            fieldnames=testcase_export_fields(),
        )
        writer.writeheader()
        for row in get_testcases_with_limit(self.get_object(), limit, offset):
            writer.writerow(export_testcase(row))

        response = HttpResponse(output.getvalue(), content_type="application/csv")
        response["Content-Disposition"] = (
            "attachment; filename=suite_%s.csv" % self.get_object().name
        )
        return response

    @detail_route(methods=["get"], suffix="yaml")
    def yaml(self, request, **kwargs):
        limit = request.query_params.get("limit", None)
        offset = request.query_params.get("offset", None)

        yaml_list = []
        for test_case in get_testcases_with_limit(self.get_object(), limit, offset):
            yaml_list.append(export_testcase(test_case))

        response = HttpResponse(
            yaml.dump(yaml_list, Dumper=yaml.CDumper), content_type="application/yaml"
        )
        response["Content-Disposition"] = (
            "attachment; filename=suite_%s.yaml" % self.get_object().name
        )
        return response


class TestCaseViewSet(NestedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TestCase.objects
    serializer_class = serializers.TestCaseSerializer
    filter_fields = "__all__"


class DeviceTypeViewSet(base_views.DeviceTypeViewSet):
    pass


class DeviceViewSet(base_views.DeviceViewSet):
    pass


class WorkerViewSet(base_views.WorkerViewSet):
    pass
