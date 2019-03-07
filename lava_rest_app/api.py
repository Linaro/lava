# -*- coding: utf-8 -*-
# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
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

import io
import junit_xml
import tap

from lava_scheduler_app.models import Device, DeviceType, TestJob, Worker
from lava_results_app.models import TestSuite, TestCase
from lava_scheduler_app.views import filter_device_types
from lava_scheduler_app.logutils import read_logs
from linaro_django_xmlrpc.models import AuthToken

from django.http.response import HttpResponse

from rest_framework import routers, serializers, views, viewsets
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import detail_route
from rest_framework.exceptions import NotFound, AuthenticationFailed
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


def safe_str2int(in_value):
    out_value = in_value
    if isinstance(in_value, str) and in_value.isnumeric():
        out_value = int(in_value)
        if out_value >= 0:
            return out_value
    return out_value


# django-rest-framework from Debian stretch (v3.8.2) does not provide this
# class.
# Manually backport the class from a recent version
try:
    from rest_framework.routers import APIRootView
except ImportError:
    from collections import OrderedDict
    from django.urls import NoReverseMatch, reverse

    class APIRootView(views.APIView):
        """
        The default basic root view for DefaultRouter
        """

        _ignore_model_permissions = True
        schema = None  # exclude from schema
        api_root_dict = None

        def get(self, request, *args, **kwargs):
            # Return a plain {"name": "hyperlink"} response.
            ret = OrderedDict()
            namespace = request.resolver_match.namespace
            for key, url_name in self.api_root_dict.items():
                if namespace:
                    url_name = namespace + ":" + url_name
                try:
                    ret[key] = reverse(
                        url_name,
                        args=args,
                        kwargs=kwargs,
                        request=request,
                        format=kwargs.get("format", None),
                    )
                except NoReverseMatch:
                    # Don't bail out if eg. no list routes exist, only detail routes.
                    continue

            return Response(ret)


class LavaApiRootView(APIRootView):
    pass


class API(routers.DefaultRouter):
    APIRootView = LavaApiRootView


class LavaObtainAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = AuthToken.objects.filter(user=user)
        token = None
        if tokens.exists():
            token = tokens[0]  # return 1st available token
        else:
            token, _ = AuthToken.objects.get_or_create(
                user=user, description="Created by REST API call"
            )
        if not token:
            # this shouldn't happen
            raise AuthenticationFailed()
        return Response({"token": token.secret})


class TestJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestJob
        fields = (
            "id",
            "submitter",
            "visibility",
            "viewing_groups",
            "description",
            "health_check",
            "requested_device_type",
            "tags",
            "actual_device",
            "submit_time",
            "start_time",
            "end_time",
            "state",
            "health",
            "priority",
            "definition",
            "original_definition",
            "multinode_definition",
            "admin_notifications",
            "failure_tags",
            "failure_comment",
        )


class TestSuiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestSuite
        fields = "__all__"


class TestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = "__all__"


class TestJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List TestJobs visible to the current user.

    The logs, test results and test suites of a specific TestJob are available at:

    * `/jobs/<job_id>/logs/`
    * `/jobs/<job_id>/suites/`
    * `/jobs/<job_id>/tests/`

    The test results are also available in JUnit and TAP13 at:

    * `/jobs/<job_id>/junit/`
    * `/jobs/<job_id>/tap13/`
    """

    queryset = TestJob.objects
    serializer_class = TestJobSerializer
    filter_fields = (
        "submitter",
        "visibility",
        "viewing_groups",
        "description",
        "health_check",
        "requested_device_type",
        "tags",
        "actual_device",
        "submit_time",
        "start_time",
        "end_time",
        "state",
        "health",
        "priority",
        "definition",
        "original_definition",
        "multinode_definition",
        "admin_notifications",
        "failure_tags",
        "failure_comment",
    )
    ordering_fields = ("id", "start_time", "end_time", "submit_time")

    def get_queryset(self):
        return self.queryset.prefetch_related(
            "tags", "failure_tags", "viewing_groups"
        ).visible_by_user(self.request.user)

    @detail_route(methods=["get"], suffix="junit")
    def junit(self, request, **kwargs):
        suites = []
        for suite in self.get_object().testsuite_set.all().order_by("id"):
            cases = []
            for case in suite.testcase_set.all().order_by("id"):
                # Grab the duration
                md = case.action_metadata
                duration = None
                if md is not None:
                    duration = md.get("duration")
                    if duration is not None:
                        duration = float(duration)

                # Build the test case junit object
                tc = junit_xml.TestCase(
                    case.name,
                    elapsed_sec=duration,
                    classname=case.suite.name,
                    timestamp=case.logged,
                )
                if case.result == TestCase.RESULT_FAIL:
                    logs = None
                    # TODO: is this of any use? (yaml inside xml!)
                    if (
                        case.start_log_line is not None
                        and case.end_log_line is not None
                    ):
                        logs = read_logs(
                            self.get_object().output_dir,
                            case.start_log_line,
                            case.end_log_line,
                        )
                    tc.add_error_info("failed", output=logs)
                elif case.result == TestCase.RESULT_SKIP:
                    tc.add_skipped_info("skipped")
                cases.append(tc)
            suites.append(junit_xml.TestSuite(suite.name, test_cases=cases))

        data = junit_xml.TestSuite.to_xml_string(suites, encoding="utf-8")
        response = HttpResponse(data, content_type="application/xml")
        response["Content-Disposition"] = (
            "attachment; filename=job_%d.xml" % self.get_object().id
        )
        return response

    @detail_route(methods=["get"], suffix="logs")
    def logs(self, request, **kwargs):
        start = safe_str2int(request.query_params.get("start", 0))
        end = safe_str2int(request.query_params.get("end", None))
        try:
            data = read_logs(self.get_object().output_dir, start, end)
            if not data:
                raise NotFound()
            response = HttpResponse(data, content_type="application/yaml")
            response["Content-Disposition"] = (
                "attachment; filename=job_%d.yaml" % self.get_object().id
            )
            return response
        except FileNotFoundError:
            raise NotFound()

    @detail_route(methods=["get"], suffix="suites")
    def suites(self, request, **kwargs):
        suites = self.get_object().testsuite_set.all().order_by("id")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(suites, request)
        serializer = TestSuiteSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @detail_route(methods=["get"], suffix="tap13")
    def tap13(self, request, **kwargs):
        stream = io.StringIO()
        count = TestCase.objects.filter(suite__job=self.get_object()).count()
        # Handle old versions of tap
        # Should be removed once python3-tap has been backported to
        # stretch-backports or once Stretch is no longer supported.
        if hasattr(tap.tracker.Tracker, "set_plan"):
            tracker = tap.tracker.Tracker(plan=count, streaming=True, stream=stream)
        else:
            tracker = tap.tracker.Tracker(streaming=True, stream=stream)

        # Loop on all test cases
        for suite in self.get_object().testsuite_set.all().order_by("id"):
            for case in suite.testcase_set.all().order_by("id"):
                if case.result == TestCase.RESULT_FAIL:
                    if (
                        case.start_log_line is not None
                        and case.end_log_line is not None
                    ):
                        logs = read_logs(
                            self.get_object().output_dir,
                            case.start_log_line,
                            case.end_log_line,
                        )
                        logs = "\n ".join(logs.split("\n"))
                        tracker.add_not_ok(
                            suite.name, case.name, diagnostics=" ---\n " + logs + "..."
                        )
                    else:
                        tracker.add_not_ok(suite.name, case.name)
                elif case.result == TestCase.RESULT_SKIP:
                    tracker.add_skip(suite.name, case.name, "test skipped")
                elif case.result == TestCase.RESULT_UNKNOWN:
                    tracker.add_not_ok(suite.name, case.name, "TODO unknow result")
                else:
                    tracker.add_ok(suite.name, case.name)

        # Send back the stream
        stream.seek(0)
        response = HttpResponse(stream, content_type="application/yaml")
        response["Content-Disposition"] = (
            "attachment; filename=job_%d.yaml" % self.get_object().id
        )
        return response

    @detail_route(methods=["get"], suffix="tests")
    def tests(self, request, **kwargs):
        tests = TestCase.objects.filter(suite__job=self.get_object()).order_by("id")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(tests, request)
        serializer = TestCaseSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class DeviceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceType
        fields = (
            "name",
            "architecture",
            "processor",
            "cpu_model",
            "aliases",
            "bits",
            "cores",
            "core_count",
            "description",
            "health_frequency",
            "disable_health_check",
            "health_denominator",
            "display",
            "owners_only",
        )


class DeviceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeviceType.objects
    serializer_class = DeviceTypeSerializer
    filter_fields = (
        "name",
        "architecture",
        "processor",
        "cpu_model",
        "aliases",
        "bits",
        "cores",
        "core_count",
        "description",
        "health_frequency",
        "disable_health_check",
        "health_denominator",
        "display",
        "owners_only",
    )

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        return DeviceType.objects.filter(name__in=visible)


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = (
            "hostname",
            "device_type",
            "device_version",
            "physical_owner",
            "physical_group",
            "description",
            "tags",
            "state",
            "health",
            "last_health_report_job",
            "worker_host",
        )


class DeviceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Device.objects
    serializer_class = DeviceSerializer
    filter_fields = (
        "hostname",
        "device_type",
        "device_version",
        "physical_owner",
        "physical_group",
        "description",
        "tags",
        "state",
        "health",
        "worker_host",
    )
    ordering_fields = (
        "hostname",
        "device_type",
        "device_version",
        "physical_owner",
        "physical_group",
        "description",
        "tags",
        "state",
        "health",
        "worker_host",
    )

    def get_queryset(self):
        visible = filter_device_types(self.request.user)
        query = Device.objects.filter(device_type__in=visible)
        if not self.request.query_params.get("all", False):
            query = query.exclude(health=Device.HEALTH_RETIRED)
        return query


class WorkerSerializer(serializers.ModelSerializer):
    health = serializers.CharField(source="get_health_display")
    state = serializers.CharField(source="get_state_display")

    class Meta:
        model = Worker
        fields = "__all__"


class WorkerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Worker.objects
    serializer_class = WorkerSerializer
    filter_fields = "__all__"
    ordering_fields = "__all__"

    def get_queryset(self):
        return self.queryset.all()


router = API()
router.register(r"devices", DeviceViewSet)
router.register(r"devicetypes", DeviceTypeViewSet)
router.register(r"jobs", TestJobViewSet)
router.register(r"workers", WorkerViewSet)
