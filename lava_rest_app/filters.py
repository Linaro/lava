# Copyright (C) 2019 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json

import rest_framework_filters as filters
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.db import connections
from django_filters.filters import CharFilter

# Raised by the metadata filters below: unlike django.core ValidationError,
# rest_framework's version is turned into a 400 response by DRF.
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework_filters.filters import RelatedFilter

from lava_results_app.models import TestCase, TestSet, TestSuite
from lava_scheduler_app.models import (
    Alias,
    Architecture,
    BitWidth,
    Core,
    Device,
    DeviceType,
    GroupDevicePermission,
    GroupDeviceTypePermission,
    JobFailureTag,
    ProcessorFamily,
    Tag,
    TestJob,
    Worker,
)


class GroupFilter(filters.FilterSet):
    class Meta:
        model = Group
        fields = {
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"]
        }


class UserFilter(filters.FilterSet):
    group = RelatedFilter(
        GroupFilter, field_name="groups", queryset=Group.objects.all()
    )

    class Meta:
        model = User
        fields = {
            "username": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "email": ["exact", "in", "contains", "icontains", "startswith", "endswith"],
        }


class PermissionFilter(filters.FilterSet):
    class Meta:
        model = Permission
        fields = {
            "codename": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ]
        }


class ArchitectureFilter(filters.FilterSet):
    class Meta:
        model = Architecture
        fields = {
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"]
        }


class ProcessorFamilyFilter(filters.FilterSet):
    class Meta:
        model = ProcessorFamily
        fields = {
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"]
        }


class AliasFilter(filters.FilterSet):
    class Meta:
        model = Alias
        fields = {
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"]
        }


class BitWidthFilter(filters.FilterSet):
    class Meta:
        model = BitWidth
        fields = {"width": ["exact", "in"]}


class CoreFilter(filters.FilterSet):
    class Meta:
        model = Core
        fields = {
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"]
        }


class TagFilter(filters.FilterSet):
    class Meta:
        model = Tag
        fields = {
            "name": [
                "exact",
                "iexact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "description": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
        }


class JobFailureTagFilter(filters.FilterSet):
    class Meta:
        model = JobFailureTag
        fields = {
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"],
            "description": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
        }


class WorkerFilter(filters.FilterSet):
    health = CharFilter(method="filter_health")
    state = CharFilter(method="filter_state")

    def filter_health(self, queryset, name, value):
        try:
            value = Worker.HEALTH_REVERSE[value]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(zip(*Worker.HEALTH_CHOICES))[1])
            )
        return queryset.filter(health=value)

    def filter_state(self, queryset, name, value):
        try:
            value = Worker.STATE_REVERSE[value]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(zip(*Worker.STATE_CHOICES))[1])
            )
        return queryset.filter(state=value)

    class Meta:
        model = Worker
        fields = {
            "hostname": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "description": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "last_ping": ["exact", "lt", "gt"],
            "state": ["exact", "iexact", "in"],
            "health": ["exact", "iexact", "in"],
        }


class DeviceTypeFilter(filters.FilterSet):
    architecture = RelatedFilter(
        ArchitectureFilter,
        field_name="architecture",
        queryset=Architecture.objects.all(),
    )
    processor = RelatedFilter(
        ProcessorFamilyFilter,
        field_name="processor",
        queryset=ProcessorFamily.objects.all(),
    )
    alias = RelatedFilter(
        AliasFilter, field_name="aliases", queryset=Alias.objects.all()
    )
    bits = RelatedFilter(
        BitWidthFilter, field_name="bits", queryset=BitWidth.objects.all()
    )
    cores = RelatedFilter(CoreFilter, field_name="cores", queryset=Core.objects.all())
    health_denominator = CharFilter(method="filter_health_denominator")

    def filter_health_denominator(self, queryset, name, value):
        try:
            value = DeviceType.HEALTH_DENOMINATOR_REVERSE[value]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(zip(*DeviceType.HEALTH_DENOMINATOR))[1])
            )
        return queryset.filter(health_denominator=value)

    class Meta:
        model = DeviceType
        fields = {
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"],
            "cpu_model": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "description": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "health_frequency": ["exact", "in"],
            "disable_health_check": ["exact", "in"],
            "health_denominator": ["exact"],
            "display": ["exact", "in"],
            "core_count": ["exact", "in"],
        }


class DeviceFilter(filters.FilterSet):
    device_type = RelatedFilter(
        DeviceTypeFilter, field_name="device_type", queryset=DeviceType.objects.all()
    )
    physical_owner = RelatedFilter(
        UserFilter, field_name="physical_owner", queryset=User.objects.all()
    )
    physical_group = RelatedFilter(
        GroupFilter, field_name="physical_group", queryset=Group.objects.all()
    )
    tags = RelatedFilter(TagFilter, field_name="tags", queryset=Tag.objects.all())
    last_health_report_job = RelatedFilter(
        "TestJobFilter",
        field_name="last_health_report_job",
        queryset=TestJob.objects.filter(health_check=True),
    )
    worker_host = RelatedFilter(
        WorkerFilter, field_name="worker_host", queryset=Worker.objects.all()
    )
    health = CharFilter(method="filter_health")
    state = CharFilter(method="filter_state")

    def filter_health(self, queryset, name, value):
        try:
            # Need upper() here because HEALTH_REVERSE has inconsistent keys.
            value = Device.HEALTH_REVERSE[value.upper()]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(zip(*Device.HEALTH_CHOICES))[1])
            )
        return queryset.filter(health=value)

    def filter_state(self, queryset, name, value):
        try:
            value = Device.STATE_REVERSE[value]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(zip(*Device.STATE_CHOICES))[1])
            )
        return queryset.filter(state=value)

    class Meta:
        model = Device
        fields = {
            "hostname": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "device_version": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "description": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "state": ["exact", "iexact", "in"],
            "health": ["exact", "iexact", "in"],
            "is_synced": ["exact"],
        }


class MetadataFilterMixin:
    """
    Filter a model on the JSON field holding the metadata of a job
    definition. Only depends on django-filter, so that it keeps working
    whichever FilterSet base class it is mixed into.
    """

    # Query parameters named "metadata__<key>" filter on the "metadata"
    # dictionary of the job definition. The key can be followed by one of these
    # lookups, e.g. "metadata__branch__startswith=release/". When no lookup is
    # given, "exact" is used. Keys are looked up in order, so nested metadata
    # is reachable with "metadata__build__id=1234".
    METADATA_LOOKUPS = frozenset(
        (
            "endswith",
            "exact",
            "icontains",
            "iendswith",
            "iexact",
            "in",
            "iregex",
            "isnull",
            "istartswith",
            "regex",
            "startswith",
        )
    )
    # Lookups on the metadata dictionary as a whole. Metadata keys with one of
    # these names cannot be filtered on directly.
    METADATA_DICT_LOOKUPS = frozenset(
        (
            "contains",
            "has_any_keys",
            "has_key",
            "has_keys",
        )
    )
    METADATA_PREFIX = "metadata__"

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        return self.filter_metadata(queryset)

    def filter_metadata(self, queryset):
        """
        Turn "metadata__<key>[__<lookup>]" query parameters into lookups on the
        TestJob.metadata JSON field. django-filter cannot declare filters for
        keys that are only known at request time, so they are handled here.
        """
        for suffix, values in self._metadata_params():
            for value in values:
                if suffix in self.METADATA_DICT_LOOKUPS:
                    value = self._metadata_dict_value(suffix, value)
                    if suffix == "contains":
                        queryset = self._filter_contains(queryset, value)
                        continue
                    queryset = queryset.filter(**{f"metadata__{suffix}": value})
                    continue

                key, _, lookup = suffix.rpartition("__")
                if not key or lookup not in self.METADATA_LOOKUPS:
                    # No lookup suffix: the remainder is the metadata key path.
                    key, lookup = suffix, "exact"
                if lookup == "exact":
                    queryset = self._filter_contains(
                        queryset, self._nested_value(key.split("__"), value)
                    )
                    continue
                value = self._metadata_value(lookup, value)
                queryset = queryset.filter(**{f"metadata__{key}__{lookup}": value})
        return queryset

    @classmethod
    def _filter_contains(cls, queryset, data):
        # Containment can use the GIN index on metadata, while a comparison on
        # the extracted key cannot. It is a PostgreSQL feature: other backends
        # raise NotSupportedError, so they compare the keys instead.
        if connections[queryset.db].vendor == "postgresql":
            return queryset.filter(metadata__contains=data)
        return queryset.filter(**cls._contains_lookups(data))

    @classmethod
    def _contains_lookups(cls, data, prefix="metadata"):
        """
        Express a metadata containment query as lookups on the keys it holds.
        The result is the same for dictionaries and scalars. Lists are compared
        for equality rather than for inclusion.
        """
        lookups = {}
        for key, value in data.items():
            path = f"{prefix}__{key}"
            if isinstance(value, dict) and value:
                lookups.update(cls._contains_lookups(value, path))
            else:
                lookups[path] = value
        return lookups

    @staticmethod
    def _nested_value(keys, value):
        for key in reversed(keys):
            value = {key: value}
        return value

    def _metadata_params(self):
        data = self.data or {}
        lists = getattr(data, "lists", None)
        items = lists() if lists is not None else ((k, [v]) for k, v in data.items())
        for param, values in items:
            if not param.startswith(self.METADATA_PREFIX):
                continue
            suffix = param[len(self.METADATA_PREFIX) :]
            if not suffix:
                raise APIValidationError("Missing metadata key in %r" % param)
            yield suffix, [value for value in values if value != ""]

    @staticmethod
    def _metadata_dict_value(lookup, value):
        if lookup == "contains":
            try:
                data = json.loads(value)
            except ValueError:
                data = None
            if not isinstance(data, dict):
                raise APIValidationError(
                    "metadata__contains expects a JSON object, got %r" % value
                )
            return data
        if lookup == "has_key":
            return value
        return [key.strip() for key in value.split(",") if key.strip()]

    @staticmethod
    def _metadata_value(lookup, value):
        if lookup == "in":
            return [item.strip() for item in value.split(",")]
        if lookup == "isnull":
            if value.lower() in ("true", "1"):
                return True
            if value.lower() in ("false", "0"):
                return False
            raise APIValidationError("isnull expects a boolean, got %r" % value)
        return value


class TestJobFilter(MetadataFilterMixin, filters.FilterSet):
    requested_device_type = RelatedFilter(
        DeviceTypeFilter,
        field_name="requested_device_type",
        queryset=DeviceType.objects.all(),
    )
    actual_device = RelatedFilter(
        DeviceFilter, field_name="actual_device", queryset=Device.objects.all()
    )
    tags = RelatedFilter(TagFilter, field_name="tags", queryset=Tag.objects.all())
    viewing_groups = RelatedFilter(
        GroupFilter, field_name="viewing_groups", queryset=Group.objects.all()
    )
    submitter = RelatedFilter(
        UserFilter, field_name="submitter", queryset=User.objects.all()
    )
    failure_tags = RelatedFilter(
        JobFailureTagFilter,
        field_name="failure_tags",
        queryset=JobFailureTag.objects.all(),
    )
    health = CharFilter(method="filter_health")
    health__in = CharFilter(method="filter_health_in")
    state = CharFilter(method="filter_state")
    state__in = CharFilter(method="filter_state_in")

    def filter_health(self, queryset, name, value):
        try:
            value = TestJob.HEALTH_REVERSE[value]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(zip(*TestJob.HEALTH_CHOICES))[1])
            )
        return queryset.filter(health=value)

    def filter_health_in(self, queryset, name, value):
        try:
            value = [TestJob.HEALTH_REVERSE[health] for health in value.split(",")]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(zip(*TestJob.HEALTH_CHOICES))[1])
            )
        return queryset.filter(health__in=value)

    def filter_state(self, queryset, name, value):
        try:
            value = TestJob.STATE_REVERSE[value]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(zip(*TestJob.STATE_CHOICES))[1])
            )
        return queryset.filter(state=value)

    def filter_state_in(self, queryset, name, value):
        try:
            value = [TestJob.STATE_REVERSE[state] for state in value.split(",")]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(zip(*TestJob.STATE_CHOICES))[1])
            )
        return queryset.filter(state__in=value)

    class Meta:
        model = TestJob
        fields = {
            "id": ["exact", "lt", "gt", "in"],
            "submit_time": ["exact", "lt", "gt", "isnull"],
            "start_time": ["exact", "lt", "gt", "isnull"],
            "end_time": ["exact", "lt", "gt", "isnull"],
            "health_check": ["exact"],
            "target_group": [
                "exact",
                "iexact",
                "in",
                "contains",
                "icontains",
                "startswith",
            ],
            "state": ["exact", "iexact", "in"],
            "health": ["exact", "iexact", "in"],
            "priority": ["exact", "in", "lt", "lte", "gt", "gte"],
            "description": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "definition": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "original_definition": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "multinode_definition": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "failure_comment": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
                "isnull",
            ],
        }


class TestSuiteFilter(filters.FilterSet):
    class Meta:
        model = TestSuite
        fields = {
            "id": ["exact", "lt", "gt"],
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"],
        }


class TestSetFilter(filters.FilterSet):
    suite = RelatedFilter(
        "TestSuiteFilter", field_name="suite", queryset=TestSuite.objects.all()
    )

    class Meta:
        model = TestSet
        fields = {
            "id": ["exact", "lt", "gt"],
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"],
        }


class TestCaseFilter(filters.FilterSet):
    result = CharFilter(method="filter_result")
    suite = RelatedFilter(
        "TestSuiteFilter", field_name="suite", queryset=TestSuite.objects.all()
    )
    test_set = RelatedFilter(
        "TestSetFilter", field_name="test_set", queryset=TestSet.objects.all()
    )

    def filter_result(self, queryset, name, value):
        try:
            value = TestCase.RESULT_MAP[value.lower()]
        except KeyError:
            raise ValidationError(
                "Select a valid choice. %s is not one of the available choices: %s"
                % (value, list(TestCase.RESULT_MAP.keys()))
            )
        return queryset.filter(result=value)

    class Meta:
        model = TestCase
        exclude = {}
        fields = {
            "id": ["exact", "lt", "gt", "in"],
            "start_log_line": ["exact", "lt", "lte", "gt", "gte"],
            "end_log_line": ["exact", "lt", "lte", "gt", "gte"],
            "logged": ["exact", "lt", "lte", "gt", "gte"],
            "measurement": ["exact", "lt", "lte", "gt", "gte"],
            "metadata": [
                "exact",
                "in",
                "contains",
                "icontains",
                "startswith",
                "endswith",
            ],
            "units": ["exact", "in", "contains", "icontains", "startswith", "endswith"],
            "name": ["exact", "in", "contains", "icontains", "startswith", "endswith"],
        }


class GroupDeviceTypePermissionFilter(filters.FilterSet):
    device_type = RelatedFilter(
        DeviceTypeFilter, field_name="devicetype", queryset=DeviceType.objects.all()
    )
    group = RelatedFilter(GroupFilter, field_name="group", queryset=Group.objects.all())
    permission = RelatedFilter(
        PermissionFilter, field_name="permission", queryset=Permission.objects.all()
    )

    class Meta:
        model = GroupDeviceTypePermission
        exclude = {}


class GroupDevicePermissionFilter(filters.FilterSet):
    device = RelatedFilter(
        DeviceFilter, field_name="device", queryset=DeviceType.objects.all()
    )
    group = RelatedFilter(GroupFilter, field_name="group", queryset=Group.objects.all())
    permission = RelatedFilter(
        PermissionFilter, field_name="permission", queryset=Permission.objects.all()
    )

    class Meta:
        model = GroupDevicePermission
        exclude = {}
