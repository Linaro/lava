# Copyright (C) 2026 Linaro Limited
#
# Author: Fathi Boudra <fathi.boudra@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json

import pytest
from django.core.management import call_command

from lava_scheduler_app.models import (
    Device,
    DeviceType,
    LavaLogEntryDevice,
    LavaLogEntryWorker,
    LavaLogFlag,
    User,
    Worker,
)


@pytest.mark.django_db
def test_export_reads_device_log_entries(tmp_path):
    user = User.objects.create_user(username="exporter", password="pass")  # nosec
    dt = DeviceType.objects.create(name="juno")
    device = Device.objects.create(hostname="juno01", device_type=dt)
    worker = Worker.objects.create(hostname="worker-01")

    LavaLogEntryDevice.objects.create(
        device=device,
        worker=worker,
        user=user,
        action_flag=LavaLogFlag.CHANGE,
        change_message="Good → Bad",
    )
    # No health transition in the message: not exported.
    LavaLogEntryDevice.objects.create(
        device=device,
        worker=worker,
        user=user,
        action_flag=LavaLogFlag.CHANGE,
        change_message="no transition here",
    )
    # Worker-level entry with a transition: must not be exported.
    LavaLogEntryWorker.objects.create(
        worker=worker,
        user=user,
        action_flag=LavaLogFlag.CHANGE,
        change_message="Offline → Online",
    )

    call_command(
        "transition_exporter",
        output_dir=tmp_path,
        start_date="2000-01-01",
    )

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert [entry["change_message"] for entry in data] == ["Good → Bad"]
    assert data[0]["device_name"] == "juno01"
    assert data[0]["old_health"] == "Good"
    assert data[0]["new_health"] == "Bad"
