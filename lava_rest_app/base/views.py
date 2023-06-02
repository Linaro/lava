# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import io

import junit_xml
import tap
from django.http.response import FileResponse, HttpResponse
from rest_framework import status, viewsets
from rest_framework.permissions import BasePermission

import lava_server.compat  # pylint: disable=unused-import
from lava_results_app.models import TestCase
from lava_scheduler_app.dbutils import testjob_submission
from lava_scheduler_app.logutils import logs_instance
from lava_scheduler_app.models import (
    Device,
    DevicesUnavailableException,
    DeviceType,
    TestJob,
    Worker,
)
from lava_scheduler_app.schema import SubmissionException
from linaro_django_xmlrpc.models import AuthToken

try:
    from rest_framework.decorators import detail_route
except ImportError:
    from rest_framework.decorators import action

    def detail_route(methods, suffix):
        return action(detail=True, methods=methods, suffix=suffix)


from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from lava_rest_app import filters

from . import serializers


def safe_str2int(in_value):
    out_value = in_value
    if isinstance(in_value, str) and in_value.isnumeric():
        out_value = int(in_value)
        if out_value >= 0:
            return out_value
    return out_value


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


class IsSuperUser(BasePermission):
    """
    Allows access only to superusers.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class TestJobViewSet(viewsets.ModelViewSet):
    """
    List TestJobs visible to the current user.

    You can submit a job via POST request on:

    * `/jobs/`

    The logs, test results and test suites of a specific TestJob are available at:

    * `/jobs/<job_id>/logs/`
    * `/jobs/<job_id>/suites/`
    * `/jobs/<job_id>/tests/`

    The test results are also available in JUnit and TAP13 at:

    * `/jobs/<job_id>/junit/`
    * `/jobs/<job_id>/tap13/`
    """

    queryset = TestJob.objects
    serializer_class = serializers.TestJobSerializer
    filterset_fields = (
        "submitter",
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
        "failure_tags",
        "failure_comment",
    )
    ordering_fields = ("id", "start_time", "end_time", "submit_time")
    filterset_class = filters.TestJobFilter

    def get_queryset(self):
        return (
            self.queryset.select_related("submitter")
            .prefetch_related("tags", "failure_tags", "viewing_groups")
            .visible_by_user(self.request.user)
        )

    def get_permissions(self):
        if self.action in ["update", "destroy", "partial_update"]:
            self.permission_classes = [IsSuperUser]
        return super().get_permissions()

    @detail_route(methods=["get"], suffix="junit")
    def junit(self, request, **kwargs):
        suites = []
        classname_prefix = request.query_params.get("classname_prefix", "")
        if classname_prefix != "":
            classname_prefix = str(classname_prefix) + "_"
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
                    classname="%s%s" % (classname_prefix, case.suite.name),
                    timestamp=case.logged.isoformat(),
                )
                if case.result == TestCase.RESULT_FAIL:
                    logs = None
                    # TODO: is this of any use? (yaml inside xml!)
                    if (
                        case.start_log_line is not None
                        and case.end_log_line is not None
                    ):
                        logs = logs_instance.read(
                            self.get_object(), case.start_log_line, case.end_log_line
                        )
                    tc.add_failure_info("failed", output=logs)
                elif case.result == TestCase.RESULT_SKIP:
                    tc.add_skipped_info("skipped")
                cases.append(tc)
            suites.append(
                junit_xml.TestSuite(
                    suite.name,
                    test_cases=cases,
                    timestamp=suite.get_end_datetime().isoformat(),
                )
            )

        data = junit_xml.to_xml_report_string(suites, encoding="utf-8")
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
            if start == 0 and end is None:
                data = logs_instance.open(self.get_object())
                response = FileResponse(data, content_type="application/yaml")
            else:
                data = logs_instance.read(self.get_object(), start, end)
                response = HttpResponse(data, content_type="application/yaml")
            if not data:
                raise NotFound()
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
        serializer = serializers.TestSuiteSerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)

    @detail_route(methods=["get"], suffix="tap13")
    def tap13(self, request, **kwargs):
        stream = io.StringIO()
        count = TestCase.objects.filter(suite__job=self.get_object()).count()
        tracker = tap.tracker.Tracker(plan=count, streaming=True, stream=stream)

        # Loop on all test cases
        for suite in self.get_object().testsuite_set.all().order_by("id"):
            for case in suite.testcase_set.all().order_by("id"):
                if case.result == TestCase.RESULT_FAIL:
                    if (
                        case.start_log_line is not None
                        and case.end_log_line is not None
                    ):
                        logs = logs_instance.read(
                            self.get_object(), case.start_log_line, case.end_log_line
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
                    tracker.add_not_ok(suite.name, case.name, "TODO unknown result")
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
        serializer = serializers.TestCaseSerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)

    def create(self, request, **kwargs):
        serializer = serializers.TestJobSerializer(
            data=request.data, context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        definition = serializer.validated_data["definition"]

        try:
            job = testjob_submission(definition, self.request.user)
        except SubmissionException as exc:
            return Response(
                {"message": "Problem with submitted job data: %s" % exc},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (ValueError, KeyError) as exc:
            return Response(
                {"message": "job submission failed: %s." % exc},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (Device.DoesNotExist, DeviceType.DoesNotExist):
            return Response(
                {"message": "Specified device or device type not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DevicesUnavailableException as exc:
            return Response(
                {"message": "Devices unavailable: %s" % exc},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if isinstance(job, list):
            job_ids = [j.sub_id for j in job]
        else:
            job_ids = [job.id]

        return Response(
            {"message": "job(s) successfully submitted", "job_ids": job_ids},
            status=status.HTTP_201_CREATED,
        )


class DeviceTypeViewSet(viewsets.ModelViewSet):
    queryset = DeviceType.objects
    serializer_class = serializers.DeviceTypeSerializer
    filterset_fields = (
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
    )
    filterset_class = filters.DeviceTypeFilter

    def get_queryset(self):
        return DeviceType.objects.visible_by_user(self.request.user).prefetch_related(
            "cores", "aliases"
        )

    def get_permissions(self):
        if self.action in ["create", "update", "destroy", "partial_update"]:
            self.permission_classes = [IsSuperUser]
        return super().get_permissions()


class DeviceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Device.objects
    serializer_class = serializers.DeviceSerializer
    filterset_fields = (
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
        "is_synced",
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
        "is_synced",
    )
    filterset_class = filters.DeviceFilter

    def get_queryset(self):
        query = (
            Device.objects.select_related("physical_owner", "physical_group")
            .prefetch_related("tags")
            .visible_by_user(self.request.user)
        )
        if not self.request.query_params.get("all", False):
            query = query.exclude(health=Device.HEALTH_RETIRED)
        return query

    def get_permissions(self):
        if self.action in ["create", "update", "destroy", "partial_update"]:
            self.permission_classes = [IsSuperUser]
        return super().get_permissions()


class WorkerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Worker.objects
    serializer_class = serializers.WorkerSerializer
    filterset_fields = "__all__"
    ordering_fields = "__all__"

    def get_queryset(self):
        return self.queryset.all()
