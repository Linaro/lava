# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from lava_dispatcher.utils.containers import DeviceContainerMappingMixin


@pytest.fixture
def add_device_container_mapping(mocker):
    return mocker.patch("lava_dispatcher.utils.containers.add_device_container_mapping")


@pytest.fixture
def action(mocker):
    a = DeviceContainerMappingMixin()
    a.job = mocker.MagicMock()
    a.job.job_id = "99"
    a.job.parameters = {"dispatcher": {"prefix": "xx-"}}
    a.job.device = {"device_info": []}
    return a


class TestDeviceContainerMappingMixin:
    def test_basics(self, action, add_device_container_mapping, mocker):
        action.job.device["device_info"].append({"board_id": "0123456789"})
        action.add_device_container_mappings("foobar", "docker")
        add_device_container_mapping.assert_called_with(
            "xx-99", {"serial_number": "0123456789"}, "foobar", container_type="docker"
        )

    def test_does_not_modify_device_info(self, action, add_device_container_mapping):
        action.job.device["device_info"].append({"board_id": "0123456789"})
        action.add_device_container_mappings("foobar", "docker")
        assert action.job.device["device_info"] == [{"board_id": "0123456789"}]
