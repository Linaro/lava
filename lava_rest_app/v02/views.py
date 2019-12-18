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

import contextlib
import csv
import io
import os
import pathlib
import yaml

from django.conf import settings
from django.http.response import HttpResponse
from django.http import Http404

from lava_results_app.models import TestSuite, TestCase
from lava_results_app.utils import (
    export_testcase,
    get_testcases_with_limit,
    testcase_export_fields,
)
from lava_rest_app.base import views as base_views
from lava_rest_app import filters
from rest_framework import status, viewsets
from rest_framework.permissions import (
    DjangoModelPermissions,
    DjangoModelPermissionsOrAnonReadOnly,
)
from rest_framework_extensions.mixins import NestedViewSetMixin
from rest_framework.response import Response
from rest_framework.exceptions import ParseError, PermissionDenied, ValidationError
from lava_scheduler_app.models import Alias, Tag

from . import serializers

try:
    from rest_framework.decorators import detail_route
except ImportError:
    from rest_framework.decorators import action

    def detail_route(methods, suffix, url_path=None):
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
    @detail_route(methods=["get", "post"], suffix="health-check")
    def health_check(self, request, **kwargs):
        if request.method == "GET":
            if not self.get_object().can_view(request.user):
                raise Http404(
                    "Device-type '%s' was not found." % self.get_object().name
                )

            try:
                filename = "%s.yaml" % os.path.join(
                    settings.HEALTH_CHECKS_PATH, self.get_object().name
                )
                with open(filename, "r") as f_in:
                    response = HttpResponse(
                        f_in.read().encode("utf-8"), content_type="application/yaml"
                    )
                    response["Content-Disposition"] = (
                        "attachment; filename=%s_health_check.yaml"
                        % self.get_object().name
                    )
                    return response
            except FileNotFoundError:
                raise ParseError(
                    "Device-type '%s' health check was not found."
                    % self.get_object().name
                )
            except OSError as exc:
                raise ParseError(
                    "Unable to read health check configuration: %s" % exc.strerror
                )

        elif request.method == "POST":
            if not request.user.has_perm("lava_scheduler_app.change_device"):
                raise PermissionDenied(
                    "Insufficient permissions. Please contact system administrator."
                )
            config = request.data.get("config", None)
            if not config:
                raise ValidationError(
                    {"config": "Health check configuration is required."}
                )

            try:
                filename = "%s.yaml" % os.path.join(
                    settings.HEALTH_CHECKS_PATH, self.get_object().name
                )
                with open(filename, "w") as f_out:
                    f_out.write(config)
                return Response(
                    {"message": "health check updated"},
                    status=status.HTTP_204_NO_CONTENT,
                )
            except OSError as exc:
                raise ParseError(
                    "Unable to write health check configuration: %s" % exc.strerror
                )

    @detail_route(methods=["get", "post"], suffix="template")
    def template(self, request, **kwargs):
        if request.method == "GET":
            if not self.get_object().can_view(request.user):
                raise Http404(
                    "Device-type '%s' was not found." % self.get_object().name
                )

            try:
                filename = "%s.jinja2" % os.path.join(
                    settings.DEVICE_TYPES_PATH, self.get_object().name
                )
                with open(filename, "r") as f_in:
                    response = HttpResponse(
                        f_in.read().encode("utf-8"), content_type="application/yaml"
                    )
                    response["Content-Disposition"] = (
                        "attachment; filename=%s.jinja2" % self.get_object().name
                    )
                    return response
            except FileNotFoundError:
                raise ParseError(
                    "Device-type '%s' template was not found." % self.get_object().name
                )
            except OSError as exc:
                raise ParseError(
                    "Unable to read device-type configuration: %s" % exc.strerror
                )

        elif request.method == "POST":
            if not request.user.has_perm("lava_scheduler_app.change_device"):
                raise PermissionDenied(
                    "Insufficient permissions. Please contact system administrator."
                )
            template = request.data.get("template", None)
            if not template:
                raise ValidationError({"template": "Device type template is required."})
            try:
                filename = "%s.jinja2" % os.path.join(
                    settings.DEVICE_TYPES_PATH, self.get_object().name
                )
                with open(filename, "w") as f_out:
                    f_out.write(template)
                return Response(
                    {"message": "template updated"}, status=status.HTTP_204_NO_CONTENT
                )
            except OSError as exc:
                raise ParseError(
                    "Unable to write device-type template: %s" % exc.strerror
                )


class DeviceViewSet(base_views.DeviceViewSet):
    pass


class WorkerViewSet(base_views.WorkerViewSet, viewsets.ModelViewSet):
    lookup_value_regex = r"[\w0-9.]+"
    serializer_class = serializers.WorkerSerializer
    filter_class = filters.WorkerFilter
    permission_classes = [DjangoModelPermissionsOrAnonReadOnly]

    @detail_route(methods=["get", "post"], suffix="env")
    def env(self, request, **kwargs):
        if request.method == "GET":
            base = pathlib.Path(settings.GLOBAL_SETTINGS_PATH)
            dispatcher_config = pathlib.Path(settings.DISPATCHER_CONFIG_PATH)
            with contextlib.suppress(OSError):
                data = (
                    dispatcher_config / self.get_object().hostname / "env.yaml"
                ).read_text(encoding="utf-8")
                response = HttpResponse(
                    data.encode("utf-8"), content_type="application/yaml"
                )
                response["Content-Disposition"] = "attachment; filename=env.yaml"
                return response

            with contextlib.suppress(OSError):
                data = (base / "env.yaml").read_text(encoding="utf-8")
                response = HttpResponse(
                    data.encode("utf-8"), content_type="application/yaml"
                )
                response["Content-Disposition"] = "attachment; filename=env.yaml"
                return response

            raise ParseError(
                "Worker '%s' does not have environment data"
                % self.get_object().hostname
            )

        elif request.method == "POST":
            if not request.user.has_perm("lava_scheduler_app.change_worker"):
                raise PermissionDenied(
                    "Insufficient permissions. Please contact system administrator."
                )

            path = (
                pathlib.Path(settings.DISPATCHER_CONFIG_PATH)
                / self.get_object().hostname
                / "env.yaml"
            )
            env = request.data.get("env", None)
            try:
                path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                path.write_text(env, encoding="utf-8")
                return Response(
                    {"message": "env successfully updated"}, status=status.HTTP_200_OK
                )
            except OSError as e:
                raise ParseError(
                    "Error updating environment for worker %s: %s"
                    % (self.get_object().hostname, str(e))
                )

    @detail_route(methods=["get", "post"], suffix="config")
    def config(self, request, **kwargs):
        if request.method == "GET":
            base = pathlib.Path(settings.DISPATCHER_CONFIG_PATH)
            with contextlib.suppress(OSError):
                data = (
                    base / self.get_object().hostname / "dispatcher.yaml"
                ).read_text(encoding="utf-8")
                response = HttpResponse(
                    data.encode("utf-8"), content_type="application/yaml"
                )
                response["Content-Disposition"] = "attachment; filename=dispatcher.yaml"
                return response

            with contextlib.suppress(OSError):
                data = (base / ("%s.yaml" % self.get_object().hostname)).read_text(
                    encoding="utf-8"
                )
                response = HttpResponse(
                    data.encode("utf-8"), content_type="application/yaml"
                )
                response["Content-Disposition"] = (
                    "attachment; filename=%s.yaml" % self.get_object().hostname
                )
                return response

            raise ParseError(
                "Worker '%s' does not have a configuration" % self.get_object().hostname
            )

        elif request.method == "POST":
            if not request.user.has_perm("lava_scheduler_app.change_worker"):
                raise PermissionDenied(
                    "Insufficient permissions. Please contact system administrator."
                )

            path = (
                pathlib.Path(settings.DISPATCHER_CONFIG_PATH)
                / self.get_object().hostname
                / "dispatcher.yaml"
            )
            config = request.data.get("config", None)
            try:
                path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                path.write_text(config, encoding="utf-8")
                return Response(
                    {"message": "config successfully updated"},
                    status=status.HTTP_200_OK,
                )
            except OSError as e:
                raise ParseError(
                    "Error updating configuration for worker %s: %s"
                    % (self.get_object().hostname, str(e))
                )


class AliasViewSet(viewsets.ModelViewSet):
    queryset = Alias.objects
    serializer_class = serializers.AliasSerializer
    filter_fields = "__all__"
    filter_class = filters.AliasFilter
    ordering_fields = "__all__"
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        return self.queryset.filter(device_type__display=True)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects
    serializer_class = serializers.TagSerializer
    filter_fields = "__all__"
    filter_class = filters.TagFilter
    ordering_fields = "__all__"
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        return self.queryset.all()
