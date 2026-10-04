# Copyright (C) 2026 Linaro Limited
#
# Author: Fathi Boudra <fathi.boudra@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
"""
actual_device__hostname__in must filter the TestJob FK directly: Device.hostname
is the primary key, and a Device subquery makes the planner pick a backward PK
scan for the default -id ordering (gitlab #699).
"""

import pytest
from django.http import QueryDict

from lava_rest_app import filters
from lava_scheduler_app.models import Device, DeviceType, TestJob, User


@pytest.mark.django_db
def test_actual_device_hostname_in_filters_fk_without_join():
    user = User.objects.create_user("user")
    dt = DeviceType.objects.create(name="dt", display=True)
    for host in ("dev-a", "dev-b", "dev-c"):
        Device.objects.create(
            hostname=host,
            device_type=dt,
            health=Device.HEALTH_GOOD,
            state=Device.STATE_IDLE,
        )
    for host in ("dev-a", "dev-b", "dev-c"):
        TestJob.objects.create(submitter=user, actual_device_id=host)

    qs = filters.TestJobFilter(
        data=QueryDict("actual_device__hostname__in=dev-a,dev-b"),
        queryset=TestJob.objects.all(),
    ).qs

    assert sorted(j.actual_device_id for j in qs) == ["dev-a", "dev-b"]
    sql = str(qs.query)
    # no subquery/join through the device table
    assert "IN (SELECT" not in sql
    assert "IN (dev-a, dev-b)" in sql
