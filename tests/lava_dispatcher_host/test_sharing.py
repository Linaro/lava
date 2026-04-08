# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from lava_dispatcher_host.utils import share_device_with_container_docker


@pytest.fixture(autouse=True)
def check_call(mocker):
    return mocker.patch("subprocess.check_call")


@pytest.fixture(autouse=True)
def call(mocker):
    return mocker.patch("subprocess.call")


@pytest.fixture(autouse=True)
def check_output(mocker):
    return mocker.patch("subprocess.check_output")


@pytest.fixture(autouse=True)
def stat(mocker):
    s = mocker.patch("os.stat")
    ret = s.return_value
    ret.st_uid = 999
    ret.st_gid = 999
    ret.st_mode = 0o664
    ret.st_rdev = 0xBD02
    return s


@pytest.fixture(autouse=True)
def docker_device_filter(mocker):
    mocker.patch("lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV1.apply")
    mocker.patch("lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.apply")


class TestDocker:
    def test_simple_sharing(self, check_output, call, mocker):
        check_output.return_value = "123456"  # get container_id
        mocker.patch("lava_dispatcher_host.open", mocker.mock_open())
        dev = "/dev/bus/usb/001/001"
        share_device_with_container_docker("container", dev, "1")
        assert call.call_args_list == [
            mocker.call(
                [
                    "docker",
                    "exec",
                    "container",
                    "sh",
                    "-c",
                    f"mkdir -p /dev/bus/usb/001 && mknod {dev} c 189 2 && chown 999:999 {dev} && chmod 664 {dev}",
                ]
            )
        ]

    def test_links(self, check_output, call, mocker, pyudev):
        check_output.return_value = "123456"  # get container_id
        mocker.patch("lava_dispatcher_host.open", mocker.mock_open())
        dev = "/dev/bus/usb/001/001"
        link = "/dev/ttyUSB1"
        pyudev.Devices.from_device_file.return_value.device_links = [link]
        share_device_with_container_docker("container", dev, "1")
        call.assert_called_with(
            [
                "docker",
                "exec",
                "container",
                "sh",
                "-c",
                f"mkdir -p /dev && ln -f -s {dev} {link}",
            ]
        )
