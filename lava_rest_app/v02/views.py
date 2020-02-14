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
import os
import pathlib
import voluptuous
import yaml
import lava_common.schemas as schemas

from django.conf import settings
from django.http.response import HttpResponse
from django.http import Http404

from lava_common.compat import yaml_dump, yaml_safe_load
from lava_results_app.models import TestSuite, TestCase
from lava_results_app.utils import (
    export_testcase,
    get_testcases_with_limit,
    testcase_export_fields,
)
from lava_rest_app.base import views as base_views
from lava_rest_app import filters
from lava_scheduler_app.dbutils import testjob_submission
from lava_scheduler_app.schema import SubmissionException
from rest_framework import status, viewsets
from rest_framework.permissions import (
    DjangoModelPermissions,
    DjangoModelPermissionsOrAnonReadOnly,
)
from rest_framework_extensions.mixins import NestedViewSetMixin
from rest_framework.response import Response
from rest_framework.exceptions import ParseError, PermissionDenied, ValidationError
from lava_scheduler_app.models import (
    Alias,
    Device,
    DeviceType,
    DevicesUnavailableException,
    Tag,
)

from . import serializers

try:
    from rest_framework.decorators import detail_route, action
except ImportError:
    from rest_framework.decorators import action

    def detail_route(methods, suffix, url_path=None):
        return action(detail=True, methods=methods, suffix=suffix)


class TestJobViewSet(base_views.TestJobViewSet):
    """
    List TestJobs visible to the current user.

    You can submit a job via POST request on:

    * `/jobs/`

    You can alidate the given job definition against the schema validator via POST request on:

    * `/jobs/validate/`

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

        response = HttpResponse(yaml_dump(yaml_list), content_type="application/yaml")
        response["Content-Disposition"] = (
            "attachment; filename=job_%d.yaml" % self.get_object().id
        )
        return response

    @detail_route(methods=["get"], suffix="metadata")
    def metadata(self, request, **kwargs):
        return Response({"metadata": self.get_object().get_metadata_dict()})

    @action(methods=["post"], detail=False, suffix="validate")
    def validate(self, request, **kwargs):
        definition = request.data.get("definition", None)
        strict = request.data.get("strict", False)
        if not definition:
            raise ValidationError({"definition": "Test job definition is required."})

        data = yaml_safe_load(definition)
        try:
            schemas.validate(
                data,
                strict=strict,
                extra_context_variables=settings.EXTRA_CONTEXT_VARIABLES,
            )
            return Response({"message": "Job valid."}, status=status.HTTP_200_OK)
        except voluptuous.Invalid as exc:
            return Response(
                {"message": "Job invalid: %s" % exc.msg}, status=status.HTTP_200_OK
            )

    @action(methods=["post"], detail=True, suffix="resubmit")
    def resubmit(self, request, **kwargs):
        if self.get_object().is_multinode:
            definition = self.get_object().multinode_definition
        else:
            definition = self.get_object().definition

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

        response = HttpResponse(yaml_dump(yaml_list), content_type="application/yaml")
        response["Content-Disposition"] = (
            "attachment; filename=suite_%s.yaml" % self.get_object().name
        )
        return response

    @detail_route(methods=["get"], suffix="cancel")
    def cancel(self, request, **kwargs):
        # django-rest-framework handles django's PermissionDenied error
        # automagically
        self.get_object().cancel(request.user)


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


class DeviceViewSet(base_views.DeviceViewSet, viewsets.ModelViewSet):
    lookup_value_regex = r"[\_\w0-9.-]+"
    serializer_class = serializers.DeviceSerializer
    filter_class = filters.DeviceFilter
    permission_classes = [DjangoModelPermissionsOrAnonReadOnly]

    def get_serializer_class(self):
        if self.action == "dictionary":
            return serializers.DictionarySerializer
        else:
            return serializers.DeviceSerializer

    @detail_route(methods=["get", "post"], suffix="dictionary")
    def dictionary(self, request, **kwargs):
        if request.method == "GET":
            job_ctx = None
            context = request.query_params.get("context", None)
            render = request.query_params.get("render", None)
            if context is not None:
                try:
                    job_ctx = yaml_safe_load(context)
                except yaml.YAMLError as exc:
                    raise ParseError(
                        "Job Context '%s' is not valid: %s" % (context, str(exc))
                    )

            config = self.get_object().load_configuration(
                job_ctx=job_ctx, output_format="raw" if not render else "yaml"
            )
            if config is None:
                raise ParseError(
                    "Device '%s' does not have a configuration"
                    % self.get_object().hostname
                )
            if render:
                filename = "%s.yaml" % self.get_object().hostname
                c_type = "application/yaml"
            else:
                filename = "%s.jinja2" % self.get_object().hostname
                c_type = "text/plain"
            response = HttpResponse(config.encode("utf-8"), content_type=c_type)
            response["Content-Disposition"] = "attachment; filename=%s" % filename
            return response

        elif request.method == "POST":
            if not request.user.has_perm("lava_scheduler_app.change_device"):
                raise PermissionDenied(
                    "Insufficient permissions. Please contact system administrator."
                )
            serializer = serializers.DictionarySerializer(data=request.data)
            if serializer.is_valid():
                if self.get_object().save_configuration(
                    request.data.get("dictionary", None)
                ):
                    return Response(
                        {"message": "device config successfully updated"},
                        status=status.HTTP_200_OK,
                    )
                else:
                    raise ParseError(
                        "Error updating configuration for device '%s'"
                        % self.get_object().hostname
                    )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WorkerViewSet(base_views.WorkerViewSet, viewsets.ModelViewSet):
    lookup_value_regex = r"[\_\w0-9.-]+"
    serializer_class = serializers.WorkerSerializer
    filter_class = filters.WorkerFilter
    permission_classes = [DjangoModelPermissionsOrAnonReadOnly]

    def get_serializer_class(self):
        if self.action == "env":
            return serializers.EnvironmentSerializer
        if self.action == "config":
            return serializers.ConfigSerializer
        else:
            return serializers.WorkerSerializer

    def _get_file(self, request, path, alternate_path):
        try:
            filename = path.name
            data = (path).read_text(encoding="utf-8")
        except OSError:
            try:
                filename = alternate_path.name
                data = (alternate_path).read_text(encoding="utf-8")
            except OSError:
                raise ParseError(
                    "Worker '%s' does not have '%s' file"
                    % (self.get_object().hostname, filename)
                )

        response = HttpResponse(data.encode("utf-8"), content_type="application/yaml")
        response["Content-Disposition"] = "attachment; filename=%s" % filename
        return response

    def _set_file(self, request, path, content):
        try:
            filename = path.name
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return Response(
                {"message": "content successfully updated"}, status=status.HTTP_200_OK
            )
        except OSError as e:
            raise ParseError(
                "Error updating '%s' for worker %s: %s"
                % (filename, self.get_object().hostname, str(e))
            )

    @detail_route(methods=["get", "post"], suffix="env")
    def env(self, request, **kwargs):
        filename = "env.yaml"
        if request.method == "GET":
            new_env_path = pathlib.Path(
                "%s/%s/%s"
                % (
                    settings.DISPATCHER_CONFIG_PATH,
                    self.get_object().hostname,
                    filename,
                )
            )
            old_env_path = pathlib.Path(
                "%s/%s" % (settings.GLOBAL_SETTINGS_PATH, filename)
            )
            return self._get_file(request, new_env_path, old_env_path)

        elif request.method == "POST":
            if not request.user.has_perm("lava_scheduler_app.change_worker"):
                raise PermissionDenied(
                    "Insufficient permissions. Please contact system administrator."
                )
            path = (
                pathlib.Path(settings.DISPATCHER_CONFIG_PATH)
                / self.get_object().hostname
                / filename
            )
            serializer = serializers.EnvironmentSerializer(data=request.data)
            if serializer.is_valid():
                return self._set_file(request, path, serializer.validated_data["env"])
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=["get", "post"], suffix="config")
    def config(self, request, **kwargs):
        if request.method == "GET":
            new_config_path = pathlib.Path(
                "%s/%s/dispatcher.yaml"
                % (settings.DISPATCHER_CONFIG_PATH, self.get_object().hostname)
            )
            old_config_path = pathlib.Path(
                "%s/%s.yaml"
                % (settings.GLOBAL_SETTINGS_PATH, self.get_object().hostname)
            )
            return self._get_file(request, new_config_path, old_config_path)

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
            serializer = serializers.ConfigSerializer(data=request.data)
            if serializer.is_valid():
                return self._set_file(
                    request, path, serializer.validated_data["config"]
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
