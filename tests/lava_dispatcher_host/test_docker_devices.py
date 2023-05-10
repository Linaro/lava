# Copyright (C) 2021 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

import subprocess

import pytest

from lava_dispatcher_host.docker_devices import Device, DeviceFilter

try:
    import bcc

    has_bcc = True
except ImportError:
    has_bcc = False


container = subprocess.call(["systemd-detect-virt", "--container", "--quiet"]) == 0


@pytest.fixture(autouse=True)
def check_output(mocker):
    return mocker.patch("subprocess.check_output")


@pytest.fixture(autouse=True)
def run(mocker):
    return mocker.patch("subprocess.run")


@pytest.fixture(autouse=True)
def check_call(mocker):
    return mocker.patch("subprocess.check_call")


@pytest.fixture
def fd():
    return 17


@pytest.fixture
def os_close(mocker):
    return mocker.patch("os.close")


@pytest.fixture(autouse=True)
def os_open(mocker, fd):
    return mocker.patch("os.open", return_value=fd)


class TestDeviceFilterCGroupsV1:
    @pytest.fixture
    def devices_allow(self, mocker, tmp_path):
        f = tmp_path / "devices.allow"
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV1.__get_devices_allow_file__",
            return_value=str(f),
        )
        return f

    @pytest.fixture(autouse=True)
    def cgroupsv1(self, mocker):
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV1.detect",
            return_value=True,
        )
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.detect",
            return_value=False,
        )
        mocker.patch

    def test_share_device(self, devices_allow):
        f = DeviceFilter("foo")
        f.add(Device(10, 232))
        f.apply()
        assert "a 10:232 rwm\n" in devices_allow.read_text()


class TestDeviceFilterCGroupsV2:
    @pytest.fixture(autouse=True)
    def cgroupsv2(self, mocker):
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV1.detect",
            return_value=False,
        )
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.detect",
            return_value=True,
        )

    def test_basics(self):
        f = DeviceFilter("foo")
        dev_null = Device(1, 3)
        assert dev_null in f.devices

    def test_device_unique(self):
        f = DeviceFilter("foo")
        l = len(f.devices)
        f.add(Device(10, 232))
        f.add(Device(10, 232))
        assert len(f.devices) == (l + 1)

    def test_read_state(self, tmp_path):
        state = tmp_path / "state"
        state.write_text("10 232\n10 235")
        f = DeviceFilter("foo", state)
        assert Device(10, 232) in f.devices
        assert Device(10, 235) in f.devices

    def test_missing_state(self, tmp_path):
        DeviceFilter("foo", tmp_path / "does-not-exist")

    def test_save_state(self, tmp_path):
        state = tmp_path / "state"
        f = DeviceFilter("foobar")
        f.add(Device(10, 232))
        f.save(state)
        assert state.read_text().strip() == "10 232"

    def test_save_load_roundtrip(self, tmp_path):
        state = tmp_path / "state"
        f1 = DeviceFilter("foobar", state)
        f1.add(Device(10, 232))
        f1.save(state)
        f2 = DeviceFilter("foobar", state)
        assert f1.devices == f2.devices
        f2.add(Device(189, 1))
        f2.save(state)
        f3 = DeviceFilter("foobar", state)
        assert f1.devices != f3.devices
        assert f2.devices == f3.devices

    def test_get_existing_functions_device(self, run):
        run.return_value.stdout = """[
            {"id":93,"attach_type":"device","attach_flags":"","name":""},
            {"id":94,"attach_type":"egress","attach_flags":"","name":""}
        ]"""
        f = DeviceFilter("foo")
        assert f.__get_existing_functions__() == [93]

    def test_get_existing_functions_cgroup_device(self, run):
        run.return_value.stdout = """[
            {"id":93,"attach_type":"cgroup_device","attach_flags":"","name":""},
            {"id":94,"attach_type":"egress","attach_flags":"","name":""}
        ]"""
        f = DeviceFilter("foo")
        assert f.__get_existing_functions__() == [93]

    def test_get_existing_functions_invalid_input(self, run):
        run.return_value.stdout = ""
        assert DeviceFilter("foobar").__get_existing_functions__() == []
        run.return_value.stdout = "blah\n"
        assert DeviceFilter("foobar").__get_existing_functions__() == []

    @pytest.mark.skipif(not has_bcc, reason="bcc not available")
    @pytest.mark.skipif(container, reason="this test won't work on containers")
    def test_apply(self, mocker, check_call, fd, os_close):
        load_func = mocker.patch("bcc.BPF.load_func")
        attach_func = mocker.patch("bcc.BPF.attach_func")
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.__get_existing_functions__",
            return_value=[99],
        )
        f = DeviceFilter("foobar")
        f.add(Device(10, 232))
        f.apply()
        load_func.assert_called()
        attach_func.assert_called()
        detach = check_call.call_args[0][0]
        assert detach == [
            "/usr/sbin/bpftool",
            "cgroup",
            "detach",
            f.__cgroup__,
            "device",
            "id",
            "99",
        ]
        os_close.assert_called_with(fd)

    def test_template(self):
        device_filter = DeviceFilter("foobar")
        device_filter.add(Device(11, 22))
        program = device_filter.expand_template()
        dev_null = "ctx->major == 1 && ctx->minor == 3"
        assert dev_null in program
        dev_something = "ctx->major == 11 && ctx->minor == 22"
        assert dev_something in program
