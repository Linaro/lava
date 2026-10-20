# Copyright (C) 2026 Linaro Limited
#
# Author: Fathi Boudra <fathi.boudra@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import itertools
import os
import stat
import subprocess
import sys

import pytest

import lava_dispatcher_host.docker_devices
from lava_common.exceptions import InfrastructureError
from lava_dispatcher_host import check
from lava_dispatcher_host.docker_devices import Device


def test_prerequisites_missing_bcc(mocker):
    mocker.patch.dict(sys.modules, {"bcc": None})
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_prerequisites()
    assert "bcc python bindings" in str(excinfo.value)


def test_prerequisites_missing_bpftool(mocker):
    mocker.patch.dict(sys.modules, {"bcc": mocker.MagicMock()})
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_prerequisites()
    assert "bpftool" in str(excinfo.value)


def test_prerequisites_missing_docker(mocker):
    mocker.patch.dict(sys.modules, {"bcc": mocker.MagicMock()})
    mocker.patch(
        "shutil.which",
        side_effect=lambda c: None if c == "docker" else "/usr/bin/" + c,
    )
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_prerequisites()
    assert "docker" in str(excinfo.value)


def test_detect_cgroups_none(mocker):
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV1.detect",
        return_value=False,
    )
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.detect",
        return_value=False,
    )
    with pytest.raises(InfrastructureError) as excinfo:
        check.detect_cgroups()
    assert "Neither cgroups v1 nor v2" in str(excinfo.value)


def test_detect_cgroups_v1(mocker):
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV1.detect",
        return_value=True,
    )
    assert check.detect_cgroups() == "v1"


def test_detect_cgroups_v2(mocker):
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV1.detect",
        return_value=False,
    )
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.detect",
        return_value=True,
    )
    assert check.detect_cgroups() == "v2"


def test_kernel_headers_missing(mocker):
    mocker.patch("lava_dispatcher_host.check.Path.exists", return_value=False)
    mocker.patch.dict(os.environ, {}, clear=True)
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_kernel_headers()
    assert "kheaders" in str(excinfo.value)


def test_kernel_headers_via_kheaders(mocker):
    mocker.patch("lava_dispatcher_host.check.Path.exists", return_value=True)
    check.check_kernel_headers()


def test_kernel_headers_via_env(mocker):
    mocker.patch("lava_dispatcher_host.check.Path.exists", return_value=False)
    mocker.patch.dict(os.environ, {"BCC_KERNEL_SOURCE": "/src/linux"})
    check.check_kernel_headers()


def test_compile_filter_failure(mocker):
    fake_bcc = mocker.MagicMock()
    fake_bcc.BPF.side_effect = Exception("clang failed")
    mocker.patch.dict(sys.modules, {"bcc": fake_bcc})
    with pytest.raises(InfrastructureError) as excinfo:
        check.compile_filter()
    assert "kernel headers" in str(excinfo.value)


def test_compile_filter_success(mocker):
    fake_bcc = mocker.MagicMock()
    bpf_instance = mocker.MagicMock()
    fake_bcc.BPF.return_value = bpf_instance
    mocker.patch.dict(sys.modules, {"bcc": fake_bcc})
    check.compile_filter()
    bpf_instance.load_func.assert_called_once_with(
        "lava_docker_device_access_control", bpf_instance.CGROUP_DEVICE
    )
    bpf_instance.close.assert_called_once()
    program = fake_bcc.BPF.call_args[1]["text"].decode()
    assert "lava_docker_device_access_control" in program
    assert "ctx->major == 1 && ctx->minor == 3" in program


@pytest.fixture
def v2_host(mocker):
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV1.detect",
        return_value=False,
    )
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.detect",
        return_value=True,
    )
    mocker.patch("subprocess.check_output")
    mocker.patch("lava_dispatcher_host.check.detect_cgroups", return_value="v2")
    # real apply_and_verify runs against these; cycle so both applies pass
    # unless a test re-patches with its own side_effect
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2"
        ".__get_existing_functions__",
        side_effect=itertools.cycle([[], [1]]),
    )
    mocker.patch("lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.apply")
    run = mocker.patch("lava_dispatcher_host.check.run")
    exec_returncodes(mocker, run, [1, 0])
    st = mocker.MagicMock()
    st.st_rdev = os.makedev(7, 7)
    st.st_mode = stat.S_IFBLK  # the default loop device is a block device
    mocker.patch("lava_dispatcher_host.check.stat_of", return_value=st)
    return run


def test_container_run_args(v2_host):
    check.check_container("busybox:latest", None)
    cmds = [c[0][0] for c in v2_host.call_args_list]
    assert [
        "docker",
        "run",
        "--rm",
        "-d",
        "--name",
        check.CHECK_CONTAINER,
        "--label",
        check.CHECK_LABEL,
        "busybox:latest",
        "sleep",
        "900",
    ] in cmds
    ps = [c for c in cmds if c[:2] == ["docker", "ps"]][0]
    assert f"label={check.CHECK_LABEL}" in ps
    # the label is pid-scoped: it must never match another check's container
    assert check.CHECK_LABEL != "lava-dispatcher-host-check=1"


def test_attach_verified_on_v2(v2_host, mocker):
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2"
        ".__get_existing_functions__",
        side_effect=[[], [42], [], [43]],
    )
    apply = mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.apply"
    )
    check.check_container("busybox:latest", None)
    apply.assert_called()
    # apply_and_verify must run for both applies, not just the first
    assert apply.call_count == 2


def test_attach_missing_reports(v2_host, mocker):
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2"
        ".__get_existing_functions__",
        side_effect=[[5], [5]],
    )
    mocker.patch("lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.apply")
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", None)
    assert "BPF program not attached" in str(excinfo.value)


def test_second_attach_failure_reports(mocker):
    # apply() swallows errors; if the *second* attach fails, the user must
    # not be told "device access not granted": the filter is not at fault.
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV1.detect",
        return_value=False,
    )
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.detect",
        return_value=True,
    )
    mocker.patch("subprocess.check_output")
    mocker.patch("lava_dispatcher_host.check.detect_cgroups", return_value="v2")
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2"
        ".__get_existing_functions__",
        side_effect=[[], [1], [1], [1]],
    )
    mocker.patch("lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.apply")
    run = mocker.patch("lava_dispatcher_host.check.run")
    exec_returncodes(mocker, run, [1, 0])
    st = mocker.MagicMock()
    st.st_rdev = os.makedev(7, 7)
    st.st_mode = stat.S_IFBLK
    mocker.patch("lava_dispatcher_host.check.stat_of", return_value=st)
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", None)
    assert "not attached" in str(excinfo.value)
    assert "device 7:7" in str(excinfo.value)


def test_cleanup_on_failure(v2_host, mocker):
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2"
        ".__get_existing_functions__",
        side_effect=Exception("boom"),
    )
    with pytest.raises(Exception):
        check.check_container("busybox:latest", None)
    assert [
        "docker",
        "rm",
        "-f",
        check.CHECK_CONTAINER,
    ] in [c[0][0] for c in v2_host.call_args_list]


def test_docker_run_failure(mocker):
    def boom(cmd, check_rc=True, timeout=60):
        if cmd[1] == "run":
            raise subprocess.CalledProcessError(1, cmd)
        result = mocker.MagicMock()
        result.returncode = 1
        result.stdout = ""
        return result

    mocker.patch("lava_dispatcher_host.check.run", side_effect=boom)
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", None)
    assert str(excinfo.value).startswith("docker run failed")


def test_docker_run_timeout(mocker):
    def boom(cmd, check_rc=True, timeout=60):
        if cmd[1] == "run":
            raise subprocess.TimeoutExpired(cmd, 300)
        result = mocker.MagicMock()
        result.returncode = 1
        result.stdout = ""
        return result

    mocker.patch("lava_dispatcher_host.check.run", side_effect=boom)
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", None)
    assert "timed out" in str(excinfo.value)


def exec_returncodes(mocker, run, returncodes):
    """Make the dd probe calls return the given returncodes in order."""
    codes = iter(returncodes)

    def side_effect(cmd, check_rc=True, timeout=60):
        result = mocker.MagicMock()
        result.returncode = 0
        result.stdout = "/dev/loop7\n"
        result.stderr = ""
        if cmd[:2] == ["docker", "exec"] and cmd[3] == "dd":
            result.returncode = next(codes)
        return result

    run.side_effect = side_effect
    return run


def test_functional_denied_then_allowed(v2_host, mocker):
    exec_returncodes(mocker, v2_host, [1, 0])
    add = mocker.spy(lava_dispatcher_host.docker_devices.DeviceFilterCommon, "add")
    check.check_container("busybox:latest", None)
    add.assert_called_once_with(mocker.ANY, Device(7, 7))
    execs = [
        c[0][0] for c in v2_host.call_args_list if c[0][0][:2] == ["docker", "exec"]
    ]
    # a loop device is block type: mknod must use 'b', not 'c'
    assert [
        "docker",
        "exec",
        check.CHECK_CONTAINER,
        "mknod",
        "/tmp/lava-check",
        "b",
        "7",
        "7",
    ] in execs
    assert len([c for c in execs if c[3] == "dd"]) == 2


def test_probe_node_created_before_filter(v2_host, mocker):
    # the cgroup device BPF program blocks mknod too: applying the empty
    # initial filter first means the probe node can never be created
    events = []
    real_run = v2_host.side_effect

    def run(cmd, check_rc=True, timeout=60):
        if cmd[:2] == ["docker", "exec"] and cmd[3] == "mknod":
            events.append("mknod")
        return real_run(cmd, check_rc=check_rc, timeout=timeout)

    v2_host.side_effect = run
    mocker.patch(
        "lava_dispatcher_host.docker_devices.DeviceFilterCGroupsV2.apply",
        side_effect=lambda *a: events.append("apply"),
    )
    check.check_container("busybox:latest", None)
    assert events.index("mknod") < events.index("apply")


def test_not_device_restricted(v2_host, mocker):
    exec_returncodes(mocker, v2_host, [0])
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", None)
    assert "not device-restricted" in str(excinfo.value)


def test_filter_not_granting_access(v2_host, mocker):
    exec_returncodes(mocker, v2_host, [1, 1])
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", None)
    assert "device access not granted" in str(excinfo.value)


def test_container_died(v2_host, mocker):
    def side_effect(cmd, check_rc=True, timeout=60):
        result = mocker.MagicMock()
        result.returncode = 0
        result.stdout = "/dev/loop7\n"
        result.stderr = ""
        if cmd[:2] == ["docker", "exec"] and cmd[3] == "dd":
            result.returncode = 1
        if cmd[:2] == ["docker", "inspect"]:
            result.returncode = 1  # --rm removed the dead container
        return result

    v2_host.side_effect = side_effect
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", None)
    assert "died" in str(excinfo.value)


def test_loop_device_setup(v2_host, mocker):
    run = exec_returncodes(mocker, v2_host, [1, 0])
    check.check_container("busybox:latest", None)
    cmds = [c[0][0] for c in run.call_args_list]
    truncates = [c for c in cmds if c[0] == "truncate"]
    assert len(truncates) == 1
    assert truncates[0][:3] == ["truncate", "-s", "1M"]
    # losetup lives in /usr/sbin, off a plain user PATH: pinned like bpftool
    assert any(c[:2] == ["/usr/sbin/losetup", "-f"] for c in cmds)
    assert ["/usr/sbin/losetup", "-d", "/dev/loop7"] in cmds


def test_explicit_device_skips_losetup(v2_host, mocker):
    run = exec_returncodes(mocker, v2_host, [1, 0])
    st = mocker.MagicMock()
    st.st_rdev = os.makedev(188, 0)
    st.st_mode = stat.S_IFCHR  # ttyUSB0 is a character device
    mocker.patch("lava_dispatcher_host.check.stat_of", return_value=st)
    check.check_container("busybox:latest", "/dev/ttyUSB0")
    cmds = [c[0][0] for c in run.call_args_list]
    assert not any(c[0] in ("truncate", "losetup") for c in cmds)
    assert [
        "docker",
        "exec",
        check.CHECK_CONTAINER,
        "mknod",
        "/tmp/lava-check",
        "c",
        "188",
        "0",
    ] in cmds


def test_device_not_a_device(v2_host, mocker):
    # a typo'd --device path must fail with "not a device node", not 0:0
    st = mocker.MagicMock()
    st.st_rdev = 0
    st.st_mode = stat.S_IFREG
    mocker.patch("lava_dispatcher_host.check.stat_of", return_value=st)
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", "/dev/ttyUS80")
    assert "not a device node" in str(excinfo.value)


def test_default_allowlisted_device_rejected(v2_host, mocker):
    # docker allows these in every container: the first probe would
    # succeed, so the denied -> allowed step cannot be shown
    st = mocker.MagicMock()
    st.st_rdev = os.makedev(1, 3)  # /dev/null
    st.st_mode = stat.S_IFCHR
    mocker.patch("lava_dispatcher_host.check.stat_of", return_value=st)
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", "/dev/null")
    assert "default device allowlist" in str(excinfo.value)


def _mock_run_check(mocker, mode):
    mocker.patch("os.geteuid", return_value=0)
    mocker.patch("lava_dispatcher_host.check.detect_cgroups", return_value=mode)
    prereq = mocker.patch("lava_dispatcher_host.check.check_prerequisites")
    headers = mocker.patch("lava_dispatcher_host.check.check_kernel_headers")
    compile_ = mocker.patch("lava_dispatcher_host.check.compile_filter")
    container = mocker.patch("lava_dispatcher_host.check.check_container")
    return prereq, headers, compile_, container


def test_run_check_rejects_v1(mocker):
    _mock_run_check(mocker, "v1")
    with pytest.raises(InfrastructureError) as excinfo:
        check.run_check("img", None)
    assert "cgroups v1 is not supported" in str(excinfo.value)


def test_run_check_v2_runs_all_steps(mocker):
    prereq, headers, compile_, container = _mock_run_check(mocker, "v2")
    check.run_check("img", None)
    prereq.assert_called_once_with()
    headers.assert_called_once_with()
    compile_.assert_called_once_with()
    container.assert_called_once_with("img", None)


def test_run_check_requires_root(mocker):
    mocker.patch("os.geteuid", return_value=1000)
    with pytest.raises(InfrastructureError) as excinfo:
        check.run_check()
    assert "run as root" in str(excinfo.value)


def test_mknod_failure_reports(mocker, v2_host):
    # a container that cannot mknod must be told so, not blamed on the filter
    def side_effect(cmd, check_rc=True, timeout=60):
        result = mocker.MagicMock()
        result.returncode = 0
        result.stdout = "/dev/loop7\n"
        result.stderr = ""
        if cmd[3:4] == ["mknod"]:
            result.returncode = 1
            result.stderr = "mknod: /tmp/lava-check: Operation not permitted\n"
        return result

    v2_host.side_effect = side_effect
    with pytest.raises(InfrastructureError) as excinfo:
        check.check_container("busybox:latest", None)
    assert "mknod failed" in str(excinfo.value)
    assert "Operation not permitted" in str(excinfo.value)
