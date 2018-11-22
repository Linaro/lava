# -*- coding: utf-8 -*-
# Copyright (C) 2018 Linaro Limited
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

from lava_scheduler_app.models import Device, DeviceType, TestJob
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
    from django.core.urlresolvers import reverse
    from django.urls import NoReverseMatch

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


router = API()
router.register(r"jobs", TestJobViewSet)
router.register(r"devicetypes", DeviceTypeViewSet)
router.register(r"devices", DeviceViewSet)
