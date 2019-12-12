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


from lava_rest_app.base import serializers as base_serializers
from lava_scheduler_app.models import Alias, Tag

from rest_framework_extensions.fields import ResourceUriField
from rest_framework.reverse import reverse as rest_reverse
from rest_framework import serializers


class TestJobSerializer(base_serializers.TestJobSerializer):
    pass


class TestSuiteResourceUriField(ResourceUriField):
    def get_url(self, obj, view_name, request, format):
        url_kwargs = {"parent_lookup_job_id": obj.job_id, "pk": obj.pk}
        return rest_reverse(
            view_name, kwargs=url_kwargs, request=request, format=format
        )


class TestSuiteSerializer(base_serializers.TestSuiteSerializer):
    resource_uri = TestSuiteResourceUriField(
        view_name="jobs-suite-detail", read_only=True
    )


class TestCaseResourceUriField(ResourceUriField):
    def get_url(self, obj, view_name, request, format):
        url_kwargs = {
            "parent_lookup_suite__job_id": obj.suite.job_id,
            "parent_lookup_suite_id": obj.suite_id,
            "pk": obj.pk,
        }
        return rest_reverse(
            view_name, kwargs=url_kwargs, request=request, format=format
        )


class TestCaseSerializer(base_serializers.TestCaseSerializer):
    resource_uri = TestCaseResourceUriField(
        view_name="suites-test-detail", read_only=True
    )


class DeviceTypeSerializer(base_serializers.DeviceTypeSerializer):
    pass


class DeviceSerializer(base_serializers.DeviceSerializer):
    pass


class WorkerSerializer(base_serializers.WorkerSerializer):
    pass


class AliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alias
        fields = "__all__"


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"
