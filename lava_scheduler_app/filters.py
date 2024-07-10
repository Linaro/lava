# Copyright (C) 2026 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import django_filters as filters

from lava_scheduler_app.models import Device, TestJob


class JobTableFilter(filters.FilterSet):
    description = filters.CharFilter(field_name="description", lookup_expr="contains")
    # Use CharFilter to avoid leaking usernames, devices and device types
    device = filters.CharFilter(field_name="actual_device_id")
    device_type = filters.CharFilter(field_name="requested_device_type_id")
    submitter_name = filters.CharFilter(field_name="submitter__username")
    state = filters.TypedMultipleChoiceFilter(
        # Use verbose names (i.e. "Running") and convert them
        # to original integers when filtering.
        choices=tuple(
            (state_display, state_display)
            for state_value, state_display in TestJob.STATE_CHOICES
        ),
        coerce=TestJob.STATE_REVERSE.__getitem__,
        distinct=False,
    )
    health = filters.TypedMultipleChoiceFilter(
        # Use verbose names (i.e. "Complete") and convert them
        # to original integers when filtering.
        choices=tuple(
            (health_display, health_display)
            for health_value, health_display in TestJob.HEALTH_CHOICES
        ),
        coerce=TestJob.HEALTH_REVERSE.__getitem__,
        distinct=False,
    )
    submit_time = filters.DateTimeFromToRangeFilter(field_name="submit_time")
    end_time = filters.DateTimeFromToRangeFilter(field_name="end_time")


class DeviceTableFilters(filters.FilterSet):
    hostname = filters.CharFilter(field_name="hostname", lookup_expr="contains")
    device_type = filters.CharFilter(field_name="device_type_id")
    state = filters.TypedMultipleChoiceFilter(
        # Use verbose names (i.e. "Running") and convert them
        # to original integers when filtering.
        choices=tuple(
            (state_display, state_display)
            for state_value, state_display in Device.STATE_CHOICES
        ),
        coerce=Device.STATE_REVERSE.__getitem__,
        distinct=False,
    )
    health = filters.TypedMultipleChoiceFilter(
        # Use verbose names (i.e. "Looping") and convert them
        # to original integers when filtering.
        choices=tuple(
            (health_display.upper(), health_display)
            for health_value, health_display in Device.HEALTH_CHOICES
        ),
        coerce=Device.HEALTH_REVERSE.__getitem__,
        distinct=False,
    )
    tag = filters.CharFilter(field_name="tags__name", lookup_expr="exact")


class DeviceTypesOverviewTableFilters(filters.FilterSet):
    device_type = filters.CharFilter(
        field_name="device_type__name", lookup_expr="contains"
    )
