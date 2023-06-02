# Copyright (C) 2020 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import datetime
import importlib
import json

import pytest
import zmq
from django.utils import timezone

from lava_scheduler_app.models import Worker

lava_scheduler = importlib.import_module(
    "lava_server.management.commands.lava-scheduler"
)
Command = lava_scheduler.Command


@pytest.mark.django_db
def test_check_workers(mocker):
    Worker.objects.create(
        hostname="worker-01",
        health=Worker.HEALTH_ACTIVE,
        state=Worker.STATE_ONLINE,
        last_ping=timezone.now(),
    )
    Worker.objects.create(
        hostname="worker-02",
        health=Worker.HEALTH_ACTIVE,
        state=Worker.STATE_ONLINE,
        last_ping=timezone.now() - datetime.timedelta(seconds=10000),
    )
    Worker.objects.create(
        hostname="worker-03",
        health=Worker.HEALTH_MAINTENANCE,
        state=Worker.STATE_ONLINE,
        last_ping=timezone.now() - datetime.timedelta(seconds=10000),
    )

    now = timezone.now()
    mocker.patch("django.utils.timezone.now", return_value=now)

    cmd = Command()
    cmd.logger = mocker.Mock()
    cmd.check_workers()

    assert Worker.objects.get(hostname="worker-01").state == Worker.STATE_ONLINE
    assert Worker.objects.get(hostname="worker-02").state == Worker.STATE_OFFLINE
    assert Worker.objects.get(hostname="worker-03").state == Worker.STATE_OFFLINE


@pytest.mark.django_db
def test_get_available_dts(mocker):
    cmd = Command()
    cmd.logger = mocker.Mock()
    cmd.sub = mocker.Mock()

    # Ending the loop
    cmd.sub.recv_multipart = mocker.Mock(side_effect=[zmq.ZMQError])
    assert cmd.get_available_dts() == set()

    # Ending the loop
    cmd.sub.recv_multipart = mocker.Mock(
        side_effect=[
            [
                b"test.testjob",
                "",
                "",
                "",
                json.dumps({"state": "Submitted", "device_type": "qemu"}),
            ],
            [
                b"test.device",
                "",
                "",
                "",
                json.dumps(
                    {"state": "Idle", "health": "Good", "device_type": "docker"}
                ),
            ],
            [],
            [b"\x81"],
            zmq.ZMQError,
        ]
    )
    assert cmd.get_available_dts() == {"docker", "qemu"}


@pytest.mark.django_db
def test_main_loop(mocker):
    schedule = mocker.Mock()
    mocker.patch(__name__ + ".lava_scheduler.schedule", schedule)

    cmd = Command()
    cmd.logger = mocker.Mock()
    cmd.poller = mocker.Mock()
    cmd.check_workers = mocker.Mock()
    cmd.get_available_dts = mocker.Mock(side_effect=[{"qemu", "docker"}, KeyError])

    with pytest.raises(KeyError):
        cmd.main_loop()
    assert len(cmd.get_available_dts.mock_calls) == 2
    assert len(schedule.mock_calls) == 2
    assert schedule.mock_calls[0][1][1] == set()
    assert schedule.mock_calls[1][1][1] == {"qemu", "docker"}


@pytest.mark.django_db
def test_handle(mocker):
    mocker.patch("zmq.Context", mocker.Mock())
    cmd = Command()
    cmd.logger = mocker.Mock()
    cmd.main_loop = mocker.Mock(side_effect=KeyboardInterrupt)
    cmd.drop_privileges = mocker.Mock()

    cmd.handle(
        level="INFO",
        log_file="-",
        user="lavaserver",
        group="lavaserver",
        event_url="tcp://localhost:5500",
        ipv6=False,
    )
