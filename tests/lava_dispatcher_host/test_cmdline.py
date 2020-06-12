# Copyright (C) 2019 Linaro Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import pytest
import subprocess

from lava_dispatcher_host.cmdline import main
import lava_dispatcher_host


@pytest.fixture(autouse=True)
def setup(mocker):
    mocker.patch("subprocess.check_call")
    mocker.patch("subprocess.call", return_value=0)


def test_no_args():
    main(["lava-dispatcher-host"])


def test_rules_no_cmd():
    main(["lava-dispatcher-host", "rules"])


def test_devices_no_cmd():
    main(["lava-dispatcher-host", "devices"])


def test_gen_udev_rules(mocker):
    get_udev_rules = mocker.spy(lava_dispatcher_host.cmdline, "get_udev_rules")
    main(["lava-dispatcher-host", "rules", "show"])
    get_udev_rules.assert_called_once()


def test_install_udev_rules(mocker):
    mocker.patch("os.path.exists", return_value=False)
    __open__ = mocker.mock_open(read_data="RULE")
    mocker.patch("lava_dispatcher_host.cmdline.open", __open__)
    main(["lava-dispatcher-host", "rules", "install"])
    __open__().write.assert_called_once_with(mocker.ANY)
    subprocess.check_call.assert_called_once_with(
        ["udevadm", "control", "--reload-rules"]
    )


def test_install_udev_rules_exists(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("lava_dispatcher_host.cmdline.get_udev_rules", return_value="RULES")
    __open__ = mocker.mock_open(read_data="RULES")
    mocker.patch("lava_dispatcher_host.cmdline.open", __open__)

    main(["lava-dispatcher-host", "rules", "install"])
    subprocess.check_call.assert_not_called()


def test_install_udev_rules_no_udev_running(mocker):
    mocker.patch("os.path.exists", return_value=False)
    __open__ = mocker.mock_open(read_data="RULE")
    mocker.patch("lava_dispatcher_host.cmdline.open", __open__)

    subprocess.call.return_value = 1
    main(["lava-dispatcher-host", "rules", "install"])
    subprocess.call.assert_called_once_with(
        ["udevadm", "control", "--ping"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.check_call.assert_not_called()


def test_share_device(mocker):
    share_device_with_container = mocker.patch(
        "lava_dispatcher_host.cmdline.share_device_with_container"
    )

    main(
        [
            "lava-dispatcher-host",
            "devices",
            "share",
            "foo/bar",
            "--serial-number=01234567890",
        ]
    )

    assert share_device_with_container.call_count == 1
    args = share_device_with_container.call_args[0][0]
    assert args.device == "foo/bar"
    assert args.serial_number == "01234567890"


def test_map_device(mocker):
    add_device_container_mapping = mocker.patch(
        "lava_dispatcher_host.cmdline.add_device_container_mapping"
    )
    main(
        [
            "lava-dispatcher-host",
            "devices",
            "map",
            "--serial-number=01234567890",
            "foobar",
            "docker",
        ]
    )
    add_device_container_mapping.assert_called_with(
        mocker.ANY, {"serial_number": "01234567890"}, "foobar", "docker"
    )


def test_unmap(mocker):
    remove_device_container_mappings = mocker.patch(
        "lava_dispatcher_host.cmdline.remove_device_container_mappings"
    )
    main(["lava-dispatcher-host", "devices", "unmap"])
    remove_device_container_mappings.assert_called_with(mocker.ANY)


def test_debug_log(mocker, tmp_path):
    mocker.patch("lava_dispatcher_host.cmdline.handle_rules_show")
    log = tmp_path / "log"
    main(["lava-dispatcher-host", "--debug-log", str(log), "rules", "show"])
    assert log.exists()
    assert "Called with args" in log.read_text()
