# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import csv
import io

import voluptuous
import yaml
from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.http.response import HttpResponse
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv
from rest_framework import status, viewsets
from rest_framework.exceptions import ParseError, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import (
    AllowAny,
    DjangoModelPermissions,
    DjangoModelPermissionsOrAnonReadOnly,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.utils import formatting
from rest_framework_extensions.mixins import NestedViewSetMixin

from lava_common import schemas
from lava_common.schemas.test import testdef
from lava_common.version import __version__
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_rest_app import filters
from lava_rest_app.base import views as base_views
from lava_rest_app.base.pasers import PlainTextParser
from lava_results_app.models import TestCase, TestSuite
from lava_results_app.utils import (
    export_testcase,
    get_testcases_with_limit,
    testcase_export_fields,
)
from lava_scheduler_app.dbutils import testjob_submission
from lava_scheduler_app.models import (
    Alias,
    Device,
    DevicesUnavailableException,
    DeviceType,
    GroupDevicePermission,
    GroupDeviceTypePermission,
    Tag,
    TestJob,
)
from lava_scheduler_app.schema import SubmissionException
from lava_scheduler_app.views import __set_device_health__
from lava_server.files import File

from . import serializers

try:
    from rest_framework.decorators import action, detail_route
except ImportError:
    from rest_framework.decorators import action

    def detail_route(methods, suffix, url_path=None):
        return action(detail=True, methods=methods, suffix=suffix)


class TestJobViewSet(base_views.TestJobViewSet):
    """
    List TestJobs visible to the current user.

    You can submit a job via POST request on:

    * `/jobs/`

    You can validate the given job definition against the schema validator via POST request on:

    * `/jobs/validate/`

    You can validate the given test definition against the schema validator via POST request on:

    * `/jobs/validate_testdef/`

    The logs, test results and test suites of a specific TestJob are available at:

    * `/jobs/<job_id>/logs/`

    Test suites present in the job are available at:

    * `/jobs/<job_id>/suites/`

    Test results for the job are available at:

    * `/jobs/<job_id>/tests/`

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
            yaml_safe_dump(yaml_list), content_type="application/yaml"
        )
        response["Content-Disposition"] = (
            "attachment; filename=job_%d.yaml" % self.get_object().id
        )
        return response

    @detail_route(methods=["get"], suffix="metadata")
    def metadata(self, request, **kwargs):
        return Response({"metadata": self.get_object().get_metadata_dict()})

    @action(
        methods=["post"], detail=False, suffix="validate", permission_classes=[AllowAny]
    )
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

    @action(
        methods=["post"],
        detail=False,
        suffix="validate-testdef",
        permission_classes=[AllowAny],
    )
    def validate_testdef(self, request, **kwargs):
        definition = request.data.get("definition", None)
        if not definition:
            raise ValidationError({"definition": "Test definition is required."})

        data = yaml_safe_load(definition)
        try:
            testdef.validate(data)
            return Response(
                {"message": "Test definition valid."}, status=status.HTTP_200_OK
            )
        except voluptuous.MultipleInvalid as exc:
            return Response(
                {"message": "Test defnition invalid: %s" % str(exc)},
                status=status.HTTP_200_OK,
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

    @detail_route(methods=["get"], suffix="cancel")
    def cancel(self, request, **kwargs):
        # django-rest-framework will allow anyone to call this method.
        # Permissions on who can cancel the job are handled by LAVA internally.
        # If the job is already finished or canceling is in progress
        # this method would report as you successfully cancelled the job
        # even if you don't have required permissions.
        with transaction.atomic():
            job = TestJob.objects.select_for_update().get(pk=kwargs["pk"])
            job.cancel(request.user)
        return Response(
            {"message": "Job cancel signal sent."}, status=status.HTTP_200_OK
        )


class TestSuiteViewSet(NestedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    List TestSuites visible to the current user.

    You can access test results for each suite at:

    * `/suites/<suite_id>/tests`
    """

    queryset = TestSuite.objects
    serializer_class = serializers.TestSuiteSerializer
    filterset_class = filters.TestSuiteFilter

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
            yaml_safe_dump(yaml_list), content_type="application/yaml"
        )
        response["Content-Disposition"] = (
            "attachment; filename=suite_%s.yaml" % self.get_object().name
        )
        return response


class TestCaseViewSet(NestedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TestCase.objects
    serializer_class = serializers.TestCaseSerializer
    filterset_class = filters.TestCaseFilter


class DeviceTypeViewSet(base_views.DeviceTypeViewSet):
    @detail_route(methods=["get", "post"], suffix="health-check")
    def health_check(self, request, **kwargs):
        if request.method == "GET":
            if not self.get_object().can_view(request.user):
                raise Http404(
                    "Device-type '%s' was not found." % self.get_object().name
                )

            try:
                response = HttpResponse(
                    File("health-check", self.get_object().name).read().encode("utf-8"),
                    content_type="application/yaml",
                )
                response["Content-Disposition"] = (
                    "attachment; filename=%s_health_check.yaml" % self.get_object().name
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
                File("health-check", self.get_object().name).write(config)
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
                response = HttpResponse(
                    File("device-type", self.get_object().name).read().encode("utf-8"),
                    content_type="application/yaml",
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
                File("device-type", self.get_object().name).write(template)
                return Response(
                    {"message": "template updated"}, status=status.HTTP_204_NO_CONTENT
                )
            except OSError as exc:
                raise ParseError(
                    "Unable to write device-type template: %s" % exc.strerror
                )


class DeviceViewSet(base_views.DeviceViewSet, viewsets.ModelViewSet):
    parser_classes = [JSONParser, FormParser, MultiPartParser, PlainTextParser]

    lookup_value_regex = r"[\_\w0-9.-]+"
    serializer_class = serializers.DeviceSerializer
    filterset_class = filters.DeviceFilter
    permission_classes = [DjangoModelPermissionsOrAnonReadOnly]

    def get_serializer_class(self):
        if self.action == "dictionary":
            return serializers.DictionarySerializer
        else:
            return serializers.DeviceSerializer

    @detail_route(methods=["post"], suffix="set_health")
    def set_health(self, request, **kwargs):
        if not request.user.has_perm("lava_scheduler_app.change_device"):
            raise PermissionDenied(
                "Insufficient permissions. Please contact system administrator."
            )
        device = self.get_object()
        reason = request.data.get("reason", None)
        health = request.data.get("health", None)
        if health is not None:
            health = health.upper()
        response = __set_device_health__(device, request.user, health, reason)
        if response is None:
            data = {"message": "OK"}
            return Response(data, status=status.HTTP_202_ACCEPTED)
        else:
            data = {"message": response.content}
            return Response(data, status=response.status_code)

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
            if not self.get_object().can_change(request.user):
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

    @action(
        methods=["post"], detail=False, suffix="validate", permission_classes=[AllowAny]
    )
    def validate(self, request, **kwargs):
        """
        Takes a string of a device dictionary to validate if it can be
        rendered and loaded correctly.
        """
        devicedict = request.data
        if not devicedict:
            raise ValidationError({"device": "Device dictionary is required."})

        try:
            template = JinjaSandboxEnv(
                loader=File("device").loader(), autoescape=False, trim_blocks=True
            ).from_string(devicedict)
            yaml_safe_load(template.render())
            return Response(
                {"message": "Device dictionary valid."}, status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {"message": "Device dictionary invalid: %s" % str(exc)},
                status=status.HTTP_200_OK,
            )


class WorkerViewSet(base_views.WorkerViewSet, viewsets.ModelViewSet):
    lookup_value_regex = r"[\_\w0-9.-]+"
    serializer_class = serializers.WorkerSerializer
    filterset_class = filters.WorkerFilter
    permission_classes = [DjangoModelPermissionsOrAnonReadOnly]

    def get_serializer_class(self):
        if self.action == "env":
            return serializers.EnvironmentSerializer
        if self.action == "config":
            return serializers.ConfigSerializer
        else:
            return serializers.WorkerSerializer

    def _get_file(self, request, kind, filename):
        try:
            data = File(kind, self.get_object().hostname).read()
        except OSError:
            raise ParseError(
                "Worker '%s' does not have '%s' file"
                % (self.get_object().hostname, kind)
            )
        response = HttpResponse(data.encode("utf-8"), content_type="application/yaml")
        response["Content-Disposition"] = "attachment; filename=%s" % filename
        return response

    def _set_file(self, request, kind, content):
        try:
            File(kind, self.get_object().hostname).write(content)

            return Response(
                {"message": "content successfully updated"}, status=status.HTTP_200_OK
            )
        except OSError as e:
            raise ParseError(
                f"Error updating '{kind}' for worker {self.get_object().hostname}: {e}"
            )

    @detail_route(methods=["get", "post"], suffix="env")
    def env(self, request, **kwargs):
        if request.method == "GET":
            return self._get_file(request, "env", "env.yaml")

        elif request.method == "POST":
            if not request.user.has_perm("lava_scheduler_app.change_worker"):
                raise PermissionDenied(
                    "Insufficient permissions. Please contact system administrator."
                )

            serializer = serializers.EnvironmentSerializer(data=request.data)
            if serializer.is_valid():
                return self._set_file(request, "env", serializer.validated_data["env"])
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @detail_route(methods=["get", "post"], suffix="config")
    def config(self, request, **kwargs):
        if request.method == "GET":
            return self._get_file(request, "dispatcher", "dispatcher.yaml")

        elif request.method == "POST":
            if not request.user.has_perm("lava_scheduler_app.change_worker"):
                raise PermissionDenied(
                    "Insufficient permissions. Please contact system administrator."
                )

            serializer = serializers.ConfigSerializer(data=request.data)
            if serializer.is_valid():
                return self._set_file(
                    request, "dispatcher", serializer.validated_data["config"]
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AliasViewSet(viewsets.ModelViewSet):
    queryset = Alias.objects
    serializer_class = serializers.AliasSerializer
    filterset_fields = "__all__"
    filterset_class = filters.AliasFilter
    ordering_fields = "__all__"
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        visible_device_types = DeviceType.objects.filter(display=True).visible_by_user(
            self.request.user
        )
        return self.queryset.filter(device_type__in=visible_device_types)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects
    serializer_class = serializers.TagSerializer
    filterset_fields = "__all__"
    filterset_class = filters.TagFilter
    ordering_fields = "__all__"
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        return self.queryset.all()


class GroupDeviceTypePermissionViewSet(viewsets.ModelViewSet):
    queryset = GroupDeviceTypePermission.objects
    serializer_class = serializers.GroupDeviceTypePermissionSerializer
    filterset_fields = "__all__"
    filterset_class = filters.GroupDeviceTypePermissionFilter
    ordering_fields = "__all__"
    permission_classes = [base_views.IsSuperUser]

    def get_queryset(self):
        return self.queryset.all()


class GroupDevicePermissionViewSet(viewsets.ModelViewSet):
    queryset = GroupDevicePermission.objects
    serializer_class = serializers.GroupDevicePermissionSerializer
    filterset_fields = "__all__"
    filterset_class = filters.GroupDevicePermissionFilter
    ordering_fields = "__all__"
    permission_classes = [base_views.IsSuperUser]

    def get_queryset(self):
        return self.queryset.all()


class SystemViewSet(viewsets.ViewSet):
    """
    System utility methods.

    Endpoints:

    * `/system/master_config/`
    * `/system/version/`
    * `/system/whoami/`
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_view_name(self):
        name = self.__class__.__name__
        name = formatting.remove_trailing_string(name, "View")
        name = formatting.remove_trailing_string(name, "ViewSet")
        name = formatting.camelcase_to_spaces(name)
        suffix = getattr(self, "suffix", None)
        # Hack for page title display in BrowsableAPIRenderer.
        if suffix and suffix != "List":
            return suffix

        return name

    def list(self, request, **kwargs):
        return Response()

    @action(detail=False, methods=["get"], suffix="master_config")
    def master_config(self, request, **kwargs):
        """
        Description
        -----------
        Return a dictionary containing the master and logger ZMQ
        socket addresses for this instance.

        Return value
        ------------
        Returns a dictionary containing the following keys:

        ```json
        {
          "EVENT_SOCKET": "tcp://*:5500",
          "EVENT_TOPIC": "org.linaro.validation",
          "EVENT_NOTIFICATION": true,
          "LOG_SIZE_LIMIT": 10,
        }
        ```
        """
        ret_dict = {
            "EVENT_TOPIC": settings.EVENT_TOPIC,
            "EVENT_SOCKET": settings.EVENT_SOCKET,
            "EVENT_NOTIFICATION": settings.EVENT_NOTIFICATION,
            "LOG_SIZE_LIMIT": settings.LOG_SIZE_LIMIT,
        }
        return Response(data=ret_dict)

    @action(detail=False, methods=["get"], suffix="version")
    def version(self, request, **kwargs):
        """
        Description
        -----------
        Return the current version

        Return value
        ------------
        Returns a dictionary containing the following keys:

        ```json
        {
          "version": "<version_string>",
        }
        ```
        """
        return Response(data={"version": __version__})

    @action(detail=False, methods=["get"], suffix="whoami")
    def whoami(self, request, **kwargs):
        """
        Description
        -----------
        Return the name of the user making the request

        Return value
        ------------
        Returns a dictionary containing the following keys:

        ```json
        {
          "user": "<username>",
        }
        ```
        """
        return Response(data={"user": request.user.username})
