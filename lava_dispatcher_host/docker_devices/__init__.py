# Copyright (C) 2021 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template

from lava_common.exceptions import InfrastructureError

try:
    from bcc import BPF, BPFAttachType  # type: ignore[import-not-found]
except ImportError:
    # This can happen on Debian 10 and that's ok. The code path that uses this
    # will only be used on Debian 11 +
    pass

logger = logging.getLogger(__name__)

# XXX bcc.BPF should provide these (from include/uapi/linux/bpf.h in the kernel
# tree)
BPF_F_ALLOW_OVERRIDE = 1 << 0
BPF_F_ALLOW_MULTI = 1 << 1
BPF_F_REPLACE = 1 << 2

TEMPLATE = """
int lava_docker_device_access_control(struct bpf_cgroup_dev_ctx *ctx) {
    bpf_trace_printk("Device access: major = %d, minor = %d", ctx->major, ctx->minor);
    {% for device in devices %}
    {% if device.minor is none %}
    if (ctx->major == {{ device.major}}) {
        return 1;
    }
    {% else %}
    if (ctx->major == {{ device.major}} && ctx->minor == {{ device.minor }}) {
        return 1;
    }
    {% endif %}
    {% endfor %}
    return 0;
}
"""


@dataclass(frozen=True)
class Device:
    major: int
    minor: int | None = None


def DeviceFilter(
    container: str,
    state_file: Path | None = None,
) -> DeviceFilterCommon:
    for klass in [DeviceFilterCGroupsV1, DeviceFilterCGroupsV2]:
        if klass.detect():
            return klass(container, state_file)
    raise InfrastructureError(
        "Neither cgroups v1 nor v2 detected; can't share device with docker container"
    )


class DeviceFilterCommon:
    def __init__(self, container: str, state_file: Path | None = None):
        self.__devices__: set[Device] = set()
        if state_file:
            self.load(state_file)
        self.container_id = subprocess.check_output(
            ["docker", "inspect", "--format={{.Id}}", container], text=True
        ).strip()

    @property
    def devices(self) -> list[Device]:
        return list(self.__devices__)

    def load(self, state_file: Path) -> None:
        pass

    def save(self, state_file: Path) -> None:
        pass

    def add(self, device: Device) -> None:
        self.__devices__.add(device)

    def apply(self) -> None:
        pass

    @classmethod
    def detect(cls) -> bool:
        return False


class DeviceFilterCGroupsV1(DeviceFilterCommon):
    @classmethod
    def detect(cls) -> bool:
        dirs = ["/sys/fs/cgroup/devices/docker", "/sys/fs/cgroup/devices/system.slice"]
        for d in dirs:
            if os.path.exists(d):
                return True
        return False

    def __get_devices_allow_file__(self) -> str:
        devices_allow_file = (
            f"/sys/fs/cgroup/devices/docker/{self.container_id}/devices.allow"
        )
        if not os.path.exists(devices_allow_file):
            devices_allow_file = f"/sys/fs/cgroup/devices/system.slice/docker-{self.container_id}.scope/devices.allow"
        return devices_allow_file

    def apply(self) -> None:
        with open(self.__get_devices_allow_file__(), "w") as allow:
            for device in self.devices:
                allow.write(f"a {device.major}:{device.minor} rwm\n")


class DeviceFilterCGroupsV2(DeviceFilterCommon):
    @classmethod
    def detect(cls) -> bool:
        return os.path.exists("/sys/fs/cgroup/system.slice")

    DEFAULT_DEVICES: list[Device] = [
        Device(1, 3),  # /dev/null
        Device(1, 5),  # /dev/zero
        Device(1, 7),  # /dev/full
        Device(1, 8),  # /dev/random
        Device(1, 9),  # /dev/urandom
        Device(5, 0),  # /dev/tty
        Device(5, 1),  # /dev/console
        Device(5, 2),  # /dev/pts/ptmx
        Device(10, 200),  # /dev/net/tun
        Device(136),  # /dev/pts/[0-9]*
    ]

    def __init__(self, container: str, state_file: Path | None = None):
        super().__init__(container, state_file)
        self.__cgroup__ = (
            f"/sys/fs/cgroup/system.slice/docker-{self.container_id}.scope"
        )
        if not os.path.exists(self.__cgroup__):
            self.__cgroup__ = f"/sys/fs/cgroup/docker/{self.container_id}"

    @property
    def devices(self) -> list[Device]:
        return self.DEFAULT_DEVICES + list(self.__devices__)

    def load(self, state_file: Path) -> None:
        if not state_file.exists():
            return
        with state_file.open() as f:
            for line in f.readlines():
                major, minor = line.split()
                self.add(Device(int(major), int(minor)))

    def save(self, state_file: Path) -> None:
        with state_file.open("w") as f:
            for device in self.__devices__:
                f.write(f"{device.major} {device.minor}\n")

    def apply(self) -> None:
        existing = self.__get_existing_functions__()

        bpf: BPF | None = None
        fd: int | None = None

        try:
            fd = os.open(self.__cgroup__, os.O_RDONLY)
            program = bytes(self.expand_template(), "utf-8")
            bpf = BPF(text=program)
            func = bpf.load_func("lava_docker_device_access_control", bpf.CGROUP_DEVICE)
            bpf.attach_func(func, fd, BPFAttachType.CGROUP_DEVICE, BPF_F_ALLOW_MULTI)

            for fid in existing:
                subprocess.check_call(
                    [
                        "/usr/sbin/bpftool",
                        "cgroup",
                        "detach",
                        self.__cgroup__,
                        "device",
                        "id",
                        str(fid),
                    ]
                )

        except Exception as exc:
            logger.error(f"Failed to apply BPF for {self.__cgroup__}: {exc}")
        finally:
            if bpf is not None:
                try:
                    bpf.close()
                except Exception as exc:
                    logger.error(f"Failed to close BPF: {exc}")

            if fd is not None:
                try:
                    os.close(fd)
                except Exception as exc:
                    logger.error(f"Failed to close file descriptor: {exc}")

    def __get_existing_functions__(self) -> list[int]:
        cmd: list[str] = [
            "/usr/sbin/bpftool",
            "cgroup",
            "list",
            self.__cgroup__,
            "--json",
        ]
        data = subprocess.run(
            cmd, text=True, check=False, stdout=subprocess.PIPE
        ).stdout
        result: list[int] = []
        try:
            programs = json.loads(data)
        except Exception:
            programs = []
        _attach_types = ["device", "cgroup_device"]
        if isinstance(programs, list):
            for program in programs:
                if isinstance(program, dict):
                    if program.get("attach_type") in _attach_types:
                        result.append(int(program["id"]))
        return result

    def expand_template(self) -> str:
        template = Template(TEMPLATE)
        return template.render(devices=self.devices)
