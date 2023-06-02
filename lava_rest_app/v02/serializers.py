# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from django.contrib.auth.models import Group, Permission
from rest_framework import serializers
from rest_framework.reverse import reverse as rest_reverse
from rest_framework_extensions.fields import ResourceUriField

from lava_rest_app.base import serializers as base_serializers
from lava_scheduler_app.models import (
    Alias,
    Device,
    DeviceType,
    GroupDevicePermission,
    GroupDeviceTypePermission,
    Tag,
    Worker,
)


class ChoiceField(serializers.ChoiceField):
    def to_representation(self, obj):
        return self.choices[obj]

    def to_internal_value(self, data):
        if data == "" and self.allow_blank:
            return ""
        try:
            return list(self.choices.keys())[
                list(self.choices.values()).index(str(data))
            ]
        except (KeyError, ValueError):
            self.fail("invalid_choice", input=data)


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
    unit = serializers.CharField(source="units")

    class Meta(base_serializers.TestCaseSerializer.Meta):
        exclude = ("units",)
        fields = None


class DeviceTypeSerializer(base_serializers.DeviceTypeSerializer):
    pass


class DictionarySerializer(serializers.Serializer):
    dictionary = serializers.CharField(style={"base_template": "textarea.html"})


class DeviceSerializer(base_serializers.DeviceSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "view" in self.context and self.context["view"].action in [
            "update",
            "partial_update",
        ]:
            # Hostname becomes read-only after device is created.
            self.fields.pop("hostname", None)

    state = serializers.CharField(source="get_state_display", read_only=True)
    health = ChoiceField(choices=Device.HEALTH_CHOICES)

    class Meta(base_serializers.DeviceSerializer.Meta):
        read_only_fields = ("last_health_report_job", "state")


class ConfigSerializer(serializers.Serializer):
    config = serializers.CharField(style={"base_template": "textarea.html"})


class EnvironmentSerializer(serializers.Serializer):
    env = serializers.CharField(style={"base_template": "textarea.html"})


class WorkerSerializer(base_serializers.WorkerSerializer):
    state = serializers.CharField(source="get_state_display", read_only=True)
    health = ChoiceField(choices=Worker.HEALTH_CHOICES, required=False)

    class Meta(base_serializers.WorkerSerializer.Meta):
        read_only_fields = ("last_ping", "state")


class AliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alias
        fields = "__all__"


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"


class GroupDeviceTypePermissionSerializer(serializers.ModelSerializer):
    group = serializers.SlugRelatedField(
        slug_field="name", queryset=Group.objects.all()
    )
    permission = serializers.SlugRelatedField(
        queryset=Permission.objects.filter(
            content_type__model=DeviceType._meta.object_name.lower()
        ),
        slug_field="codename",
    )

    class Meta:
        model = GroupDeviceTypePermission
        fields = "__all__"


class GroupDevicePermissionSerializer(serializers.ModelSerializer):
    group = serializers.SlugRelatedField(
        slug_field="name", queryset=Group.objects.all()
    )
    permission = serializers.SlugRelatedField(
        queryset=Permission.objects.filter(
            content_type__model=Device._meta.object_name.lower()
        ),
        slug_field="codename",
    )

    class Meta:
        model = GroupDevicePermission
        fields = "__all__"
