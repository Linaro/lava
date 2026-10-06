# Copyright (C) 2021 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

import fcntl
from subprocess import CalledProcessError

import pytest

from lava_dispatcher_host.docker_devices import (
    ANY_MINOR,
    BPF_MAP,
    BPF_OBJECT,
    BPF_PROGRAM,
    BPFTOOL,
    PIN_BASE,
    Device,
    DeviceFilter,
)


@pytest.fixture(autouse=True)
def check_output(mocker):
    return mocker.patch("subprocess.check_output")


@pytest.fixture(autouse=True)
def run(mocker):
    return mocker.patch("subprocess.run")


@pytest.fixture(autouse=True)
def check_call(mocker):
    return mocker.patch("subprocess.check_call")


@pytest.fixture(autouse=True)
def pin_dirs(mocker):
    # apply() creates pin directories under /sys/fs/bpf: never touch the
    # real filesystem in unit tests.
    return mocker.patch("os.makedirs")


@pytest.fixture(autouse=True)
def fs_writes(mocker):
    return mocker.patch("shutil.rmtree")


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

    def test_save_load_wildcard_minor(self, tmp_path):
        # Device(136) means any minor; load() would choke on a literal "None"
        state = tmp_path / "state"
        f1 = DeviceFilter("foobar", state)
        f1.add(Device(136, None))
        f1.save(state)
        assert state.read_text().strip() == "136 *"
        f2 = DeviceFilter("foobar", state)
        assert Device(136, None) in f2.devices

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
        # an entry with no id is skipped: nothing to detach
        run.return_value.stdout = '[{"attach_type": "device"}]'
        assert DeviceFilter("foobar").__get_existing_functions__() == []

    def test_apply_locks_the_container(
        self, mocker, check_call, check_output, fs_writes, pin_dirs
    ):
        # A second apply would rmtree the first one's pins mid-flight,
        # so apply() must hold an exclusive lock.
        check_output.return_value = "deadbeefcafe1234567890\n"
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.__get_existing_functions__",
            return_value=[],
        )
        flock = mocker.patch("lava_dispatcher_host.docker_devices.fcntl.flock")
        f = DeviceFilter("foobar")
        f.apply()
        assert flock.call_args[0][1] == fcntl.LOCK_EX

    def test_apply(self, mocker, check_call, check_output, fs_writes, pin_dirs):
        check_output.return_value = "deadbeefcafe1234567890\n"
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.__get_existing_functions__",
            return_value=[99],
        )
        f = DeviceFilter("foobar")
        f.add(Device(10, 232))
        f.apply()
        calls = [c[0][0] for c in check_call.call_args_list]
        pin = f"{PIN_BASE}/{f.container_id[:12]}"
        # bpftool mounts bpffs but does not create the pin directory, so
        # apply() has to. Without it, loadall fails and no device is shared.
        assert [c[0][0] for c in pin_dirs.call_args_list] == [f"{pin}/prog"]
        assert [
            BPFTOOL,
            "prog",
            "loadall",
            BPF_OBJECT,
            f"{pin}/prog",
            "pinmaps",
            f"{pin}/maps",
        ] in calls
        # key is struct.pack("@II", major, minor) in native byte order
        assert [
            BPFTOOL,
            "map",
            "update",
            "pinned",
            f"{pin}/maps/{BPF_MAP}",
            "key",
            "0x0a",
            "0x00",
            "0x00",
            "0x00",
            "0xe8",
            "0x00",
            "0x00",
            "0x00",
            "value",
            "0x01",
            "0x00",
            "0x00",
            "0x00",
        ] in calls
        attach_index = calls.index(
            [
                BPFTOOL,
                "cgroup",
                "attach",
                f.__cgroup__,
                "device",
                "pinned",
                f"{pin}/prog/{BPF_PROGRAM}",
                "multi",
            ]
        )
        # the old program is detached only after the new one is attached
        detach_index = calls.index(
            [BPFTOOL, "cgroup", "detach", f.__cgroup__, "device", "id", "99"]
        )
        assert attach_index < detach_index
        # apply() unpins twice: once to clear an old pin dir, once after
        # attach. The cgroup holds the program, so a leftover pin would
        # leak it once the container is gone.
        assert [c[0][0] for c in fs_writes.call_args_list] == [pin, pin]

    def test_apply_failure_keeps_the_old_program_attached(
        self, mocker, check_call, check_output, fs_writes
    ):
        check_output.return_value = "deadbeefcafe1234567890\n"
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.__get_existing_functions__",
            return_value=[99],
        )
        # loadall succeeds, the map update fails (e.g. the hash is full)
        check_call.side_effect = [None, CalledProcessError(1, BPFTOOL)]
        f = DeviceFilter("foobar")
        f.add(Device(10, 232))
        f.apply()
        calls = [c[0][0] for c in check_call.call_args_list]
        # nothing else ran, so the old program stays attached: a cgroup
        # with no device program has unrestricted access
        assert len(calls) == 2
        assert not any("detach" in c for c in calls)
        # the half-loaded instance was unpinned
        pin = f"{PIN_BASE}/{f.container_id[:12]}"
        assert [c[0][0] for c in fs_writes.call_args_list] == [pin, pin]

    def test_apply_wildcard_minor(self, mocker, check_call, check_output):
        check_output.return_value = "deadbeefcafe1234567890\n"
        mocker.patch(
            "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.__get_existing_functions__",
            return_value=[],
        )
        f = DeviceFilter("foobar")
        f.add(Device(136, None))
        f.apply()
        calls = [c[0][0] for c in check_call.call_args_list]
        pin = f"{PIN_BASE}/{f.container_id[:12]}"
        assert [
            BPFTOOL,
            "map",
            "update",
            "pinned",
            f"{pin}/maps/{BPF_MAP}",
            "key",
            "0x88",
            "0x00",
            "0x00",
            "0x00",
            "0xff",
            "0xff",
            "0xff",
            "0xff",
            "value",
            "0x01",
            "0x00",
            "0x00",
            "0x00",
        ] in calls
