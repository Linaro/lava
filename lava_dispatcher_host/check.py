# Copyright (C) 2026 Linaro Limited
#
# Author: Fathi Boudra <fathi.boudra@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
"""On-host diagnostic: check if the host can compile the BPF device filter
and share a device with a container"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from lava_common.exceptions import InfrastructureError
from lava_dispatcher_host.docker_devices import (
    HEADERS_GUIDANCE,
    TEMPLATE,
    Device,
    DeviceFilterCGroupsV1,
    DeviceFilterCGroupsV2,
)

DEFAULT_IMAGE = "debian:trixie-slim"
# pid suffix and pid-scoped label so two concurrent checks never touch
# each other's container
CHECK_CONTAINER = f"lava-dispatcher-host-check-{os.getpid()}"
CHECK_LABEL = f"lava-dispatcher-host-check-{os.getpid()}=1"


def check_prerequisites() -> None:
    try:
        import bcc  # type: ignore[import-not-found]  # noqa: F401 pylint: disable=unused-import
    except ImportError:
        raise InfrastructureError(
            "the bcc python module is missing, install the bcc python bindings"
        )
    # docker_devices runs /usr/sbin/bpftool, so probe that exact path
    if not shutil.which("/usr/sbin/bpftool"):
        raise InfrastructureError(
            "bpftool is missing at /usr/sbin/bpftool, install bpftool"
        )
    if not shutil.which("docker"):
        raise InfrastructureError("docker is missing, install the docker engine")


def detect_cgroups() -> str:
    # same V1-then-V2 probe order as the DeviceFilter factory in docker_devices
    if DeviceFilterCGroupsV1.detect():
        return "v1"
    if DeviceFilterCGroupsV2.detect():
        return "v2"
    raise InfrastructureError("Neither cgroups v1 nor v2 detected on this host")


def check_kernel_headers() -> None:
    if os.environ.get("BCC_KERNEL_SOURCE"):
        return
    if Path("/sys/kernel/kheaders.tar.xz").exists():
        return
    if Path(f"/lib/modules/{platform.uname().release}/build").exists():
        return
    raise InfrastructureError(HEADERS_GUIDANCE)


def compile_filter() -> None:
    from jinja2 import Environment as JinjaEnv

    program = (
        JinjaEnv()
        .from_string(TEMPLATE)
        .render(devices=DeviceFilterCGroupsV2.DEFAULT_DEVICES)
    )
    from bcc import BPF

    try:
        bpf = BPF(text=bytes(program, "utf-8"))
        try:
            bpf.load_func("lava_docker_device_access_control", bpf.CGROUP_DEVICE)
        finally:
            bpf.close()
    except Exception as e:
        raise InfrastructureError(
            "the BPF device filter failed to compile, most likely because "
            + HEADERS_GUIDANCE
            + f" (original error: {e})"
        ) from e


def run(
    cmd: list[str], check_rc: bool = True, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check_rc,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def stat_of(path: str) -> os.stat_result:
    # patching os.stat through this module would patch it process-wide and
    # break unrelated machinery
    return os.stat(path)


def apply_and_verify(device_filter: DeviceFilterCGroupsV2, what: str) -> None:
    # apply() swallows errors, so compare the bpftool program ids before
    # and after: a new id means the attach happened
    before = device_filter.__get_existing_functions__()
    device_filter.apply()
    new_ids = [
        fid for fid in device_filter.__get_existing_functions__() if fid not in before
    ]
    if not new_ids:
        raise InfrastructureError(
            f"BPF program not attached to the container cgroup ({what})"
        )
    print(f"BPF program attached (id {new_ids[0]}): OK")


def create_probe_node(name: str, major: int, minor: int, kind: str) -> None:
    # separate call: a swallowed mknod failure would be blamed on the filter
    result = run(
        [
            "docker",
            "exec",
            name,
            "mknod",
            "/tmp/lava-check",
            kind,
            str(major),
            str(minor),
        ],
        check_rc=False,
    )
    if result.returncode != 0:
        raise InfrastructureError(
            f"mknod failed in the container: {(result.stderr or '').strip()}"
        )


def probe_device_access(name: str) -> bool:
    # count=0: the filter decides at open(), so no data is read; reading
    # a character device (a tty, say) would block forever
    result = run(
        [
            "docker",
            "exec",
            name,
            "dd",
            "if=/tmp/lava-check",
            "of=/dev/null",
            "bs=512",
            "count=0",
        ],
        check_rc=False,
    )
    return result.returncode == 0


def check_container(image: str, device: str | None) -> None:
    # remove leftovers of any crashed check; the label marks them as ours,
    # so a user container is never removed (if a user container took the
    # name, docker run then fails with a clear error). -a catches stopped
    # leftovers from a crashed docker daemon.
    leftover = run(
        [
            "docker",
            "ps",
            "-a",
            "-q",
            "--filter",
            f"label={CHECK_LABEL}",
        ],
        check_rc=False,
    )
    for cid in leftover.stdout.split():
        run(["docker", "rm", "-f", cid], check_rc=False)
    try:
        run(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                CHECK_CONTAINER,
                "--label",
                CHECK_LABEL,
                image,
                # self-exit budget: if this process is killed, --rm cleans
                # the container up once the sleep ends. Well above the
                # docker run timeout below because each apply() recompiles
                # the BPF program with clang.
                "sleep",
                "900",
            ],
            # first run pulls the image, which can take a while
            timeout=300,
        )
    except subprocess.CalledProcessError as e:
        raise InfrastructureError(f"docker run failed: {e.stderr or e}")
    except subprocess.TimeoutExpired:
        # if the container did start before the timeout, the label cleanup
        # at the start of the next check (or its sleep 900 + --rm) removes it
        raise InfrastructureError("docker run timed out (image pull?)")
    try:
        tmp_dir = tempfile.mkdtemp(prefix="lava-dispatcher-host-check-")
        loop_node = None
        try:
            if device:
                st = stat_of(device)
                if not (stat.S_ISCHR(st.st_mode) or stat.S_ISBLK(st.st_mode)):
                    raise InfrastructureError(
                        f"{device} is not a device node (character or block)"
                    )
            else:
                img = os.path.join(tmp_dir, "lava-check.img")
                run(["truncate", "-s", "1M", img])
                loop_node = run(
                    ["/usr/sbin/losetup", "-f", "--show", img]
                ).stdout.strip()
                st = stat_of(loop_node)
            major, minor = os.major(st.st_rdev), os.minor(st.st_rdev)
            kind = "b" if stat.S_ISBLK(st.st_mode) else "c"
            if Device(major, minor) in DeviceFilterCGroupsV2.DEFAULT_DEVICES:
                # docker allows these in every container: the first probe
                # would succeed, so the denied -> allowed step cannot be
                # shown
                raise InfrastructureError(
                    f"{device} is in docker's default device allowlist, "
                    "pick another device"
                )
            # mknod before the filter: the cgroup device program blocks
            # mknod too, so an empty initial filter would deny the probe node
            create_probe_node(CHECK_CONTAINER, major, minor, kind)
            device_filter = DeviceFilterCGroupsV2(CHECK_CONTAINER)
            apply_and_verify(device_filter, "initial filter")
            if probe_device_access(CHECK_CONTAINER):
                raise InfrastructureError(
                    "container is not device-restricted, cannot tell "
                    "whether the filter grants access"
                )
            device_filter.add(Device(major, minor))
            apply_and_verify(device_filter, f"device {major}:{minor}")
            if not probe_device_access(CHECK_CONTAINER):
                # --rm removes dead containers, so a failing inspect means it died
                if run(
                    ["docker", "inspect", CHECK_CONTAINER], check_rc=False
                ).returncode:
                    raise InfrastructureError(
                        "the check container died during the check"
                    )
                raise InfrastructureError(
                    "device access not granted after applying the filter"
                )
            print(f"Device {major}:{minor} went from denied to allowed: OK")
        finally:
            if loop_node:
                run(["/usr/sbin/losetup", "-d", loop_node], check_rc=False)
            shutil.rmtree(tmp_dir, ignore_errors=True)
    finally:
        # cleanup must not mask the real error; if the daemon is wedged,
        # --rm + sleep 900 still retires the container
        try:
            run(
                ["docker", "rm", "-f", CHECK_CONTAINER],
                check_rc=False,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            pass


def run_check(image: str = DEFAULT_IMAGE, device: str | None = None) -> None:
    if os.geteuid():
        raise InfrastructureError("run as root")
    if detect_cgroups() != "v2":
        # cgroups v1 hosts run on EOL distributions (Debian 10): the check
        # only exercises the BPF path, which v1 does not have
        raise InfrastructureError(
            "cgroups v1 is not supported, run this on a cgroups v2 host"
        )
    print("Cgroups v2: OK")
    check_prerequisites()
    print("Prerequisites (docker, bpftool, bcc): OK")
    check_kernel_headers()
    print("Kernel headers: OK")
    compile_filter()
    print("BPF device filter compiles: OK")
    check_container(image, device)
