# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from rest_framework import serializers
from rest_framework.reverse import reverse as rest_reverse
from rest_framework_extensions.fields import ResourceUriField
from rest_framework_extensions.serializers import PartialUpdateSerializerMixin

from lava_results_app.models import TestCase, TestSuite
from lava_scheduler_app.models import (
    Alias,
    Device,
    DeviceType,
    GroupDevicePermission,
    GroupDeviceTypePermission,
    Tag,
    TestJob,
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


class TestSuiteResourceUriField(ResourceUriField):
    def get_url(self, obj, view_name, request, format):
        url_kwargs = {"parent_lookup_job_id": obj.job_id, "pk": obj.pk}
        return rest_reverse(
            view_name, kwargs=url_kwargs, request=request, format=format
        )


class TestJobSerializer(PartialUpdateSerializerMixin, serializers.ModelSerializer):
    health = serializers.CharField(source="get_health_display", read_only=True)
    state = serializers.CharField(source="get_state_display", read_only=True)
    submitter = serializers.CharField(source="submitter.username", read_only=True)
    definition = serializers.CharField(style={"base_template": "textarea.html"})

    class Meta:
        model = TestJob
        fields = (
            "id",
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
            "multinode_definition",
            "failure_tags",
            "failure_comment",
            "token",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "submitter": {"read_only": True},
            "viewing_groups": {"read_only": True},
            "description": {"read_only": True},
            "health_check": {"read_only": True},
            "requested_device_type": {"read_only": True},
            "tags": {"read_only": True},
            "actual_device": {"read_only": True},
            "submit_time": {"read_only": True},
            "start_time": {"read_only": True},
            "end_time": {"read_only": True},
            "state": {"read_only": True},
            "health": {"read_only": True},
            "priority": {"read_only": True},
            "multinode_definition": {"read_only": True},
            "failure_tags": {"read_only": True},
            "failure_comment": {"read_only": True},
        }

    def __init__(self, *args, **kwargs):
        kwargs["partial"] = True
        super().__init__(*args, **kwargs)

    def get_fields(self, *args, **kwargs):
        fields = super().get_fields(*args, **kwargs)
        if not self.context.get("request").user.is_superuser:
            del fields["token"]
        return fields


class TestSuiteSerializer(serializers.ModelSerializer):
    resource_uri = TestSuiteResourceUriField(
        view_name="jobs-suite-detail", read_only=True
    )

    class Meta:
        model = TestSuite
        fields = "__all__"


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


class TestCaseSerializer(serializers.ModelSerializer):
    result = serializers.CharField(source="result_code", read_only=True)
    resource_uri = TestCaseResourceUriField(
        view_name="suites-test-detail", read_only=True
    )
    unit = serializers.CharField(source="units")

    class Meta:
        model = TestCase
        exclude = ("units",)
        fields = None


class DictionarySerializer(serializers.Serializer):
    dictionary = serializers.CharField(style={"base_template": "textarea.html"})


class DeviceTypeSerializer(serializers.ModelSerializer):
    health_denominator = serializers.ReadOnlyField(
        source="get_health_denominator_display"
    )

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
        )


class DeviceSerializer(PartialUpdateSerializerMixin, serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        kwargs["partial"] = True
        super().__init__(*args, **kwargs)
        if "view" in self.context and self.context["view"].action in [
            "update",
            "partial_update",
        ]:
            # Hostname becomes read-only after device is created.
            self.fields.pop("hostname", None)

    def update(self, instance, validated_data):
        old_health_display = None
        if validated_data.get("health") is not None:
            # Log entry if the health changed
            if validated_data["health"] != instance.health:
                old_health_display = instance.get_health_display()

        device = super().update(instance, validated_data)
        if old_health_display is not None:
            device.log_admin_entry(
                self.context["request"].user,
                "%s → %s" % (old_health_display, device.get_health_display()),
            )
        return device

    state = serializers.CharField(source="get_state_display", read_only=True)
    health = ChoiceField(choices=Device.HEALTH_CHOICES)

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
            "is_synced",
        )
        read_only_fields = ("last_health_report_job", "state")


class ConfigSerializer(serializers.Serializer):
    config = serializers.CharField(style={"base_template": "textarea.html"})


class EnvironmentSerializer(serializers.Serializer):
    env = serializers.CharField(style={"base_template": "textarea.html"})


class WorkerSerializer(PartialUpdateSerializerMixin, serializers.ModelSerializer):
    state = serializers.CharField(source="get_state_display", read_only=True)
    health = ChoiceField(choices=Worker.HEALTH_CHOICES, required=False)

    def __init__(self, *args, **kwargs):
        kwargs["partial"] = True
        super().__init__(*args, **kwargs)

    def get_fields(self, *args, **kwargs):
        fields = super().get_fields(*args, **kwargs)
        if not self.context.get("request").user.is_superuser:
            del fields["token"]
        return fields

    def update(self, instance, validated_data):
        if validated_data.get("health") is not None:
            health = validated_data["health"]
            user = self.context["request"].user
            with transaction.atomic():
                # Use the worker helpers
                if health == Worker.HEALTH_ACTIVE:
                    instance.go_health_active(user)
                elif health == Worker.HEALTH_MAINTENANCE:
                    instance.go_health_maintenance(user)
                elif health == Worker.HEALTH_RETIRED:
                    instance.go_health_retired(user)
            # "health" was already updated, drop it
            del validated_data["health"]
        return super().update(instance, validated_data)

    class Meta:
        model = Worker
        fields = "__all__"
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
