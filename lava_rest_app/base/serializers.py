# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db import transaction
from rest_framework import serializers

from lava_results_app.models import TestCase, TestSuite
from lava_scheduler_app.models import Device, DeviceType, TestJob, Worker


class TestJobSerializer(serializers.ModelSerializer):
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
            "original_definition",
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
            "original_definition": {"read_only": True},
            "multinode_definition": {"read_only": True},
            "failure_tags": {"read_only": True},
            "failure_comment": {"read_only": True},
        }

    def get_fields(self, *args, **kwargs):
        fields = super().get_fields(*args, **kwargs)
        if not self.context.get("request").user.is_superuser:
            del fields["token"]
        return fields


class TestSuiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestSuite
        fields = "__all__"


class TestCaseSerializer(serializers.ModelSerializer):
    result = serializers.CharField(source="result_code", read_only=True)

    class Meta:
        model = TestCase
        fields = "__all__"


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


class DeviceSerializer(serializers.ModelSerializer):
    health = serializers.CharField(source="get_health_display")
    state = serializers.CharField(source="get_state_display")

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


class WorkerSerializer(serializers.ModelSerializer):
    health = serializers.CharField(source="get_health_display")
    state = serializers.CharField(source="get_state_display")

    class Meta:
        model = Worker
        fields = "__all__"

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
