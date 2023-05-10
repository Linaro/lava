# Copyright (C) 2021 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jinja2 import Template

from lava_common.exceptions import InfrastructureError

try:
    from bcc import BPFAttachType

    from .bcc import BPF
except ImportError:
    # This can happen on Debian 10 and that's ok. The code path that uses this
    # will only be used on Debian 11 +
    pass

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
    major: str
    minor: str = None


def DeviceFilter(*args, **kwargs):
    for klass in [DeviceFilterCGroupsV1, DeviceFilterCGroupsV2]:
        if klass.detect():
            return klass(*args, **kwargs)
    raise InfrastructureError(
        "Neither cgroups v1 nor v2 detected; can't share device with docker container"
    )


class DeviceFilterCommon:
    def __init__(self, container, state_file: Optional[Path] = None):
        self.__devices__ = set()
        if state_file:
            self.load(state_file)
        self.container_id = subprocess.check_output(
            ["docker", "inspect", "--format={{.Id}}", container], text=True
        ).strip()

    @property
    def devices(self):
        return list(self.__devices__)

    def load(self, state: Path):
        pass

    def save(self, state: Path):
        pass

    def add(self, device: Device):
        self.__devices__.add(device)

    def apply(self):
        pass

    @classmethod
    def detect(cls):
        return False


class DeviceFilterCGroupsV1(DeviceFilterCommon):
    @classmethod
    def detect(cls):
        dirs = [
            "/sys/fs/cgroup/devices/docker",
            "/sys/fs/cgroup/devices/system.slice",
        ]
        for d in dirs:
            if os.path.exists(d):
                return True
        return False

    def __get_devices_allow_file__(self):
        devices_allow_file = (
            f"/sys/fs/cgroup/devices/docker/{self.container_id}/devices.allow"
        )
        if not os.path.exists(devices_allow_file):
            devices_allow_file = f"/sys/fs/cgroup/devices/system.slice/docker-{self.container_id}.scope/devices.allow"
        return devices_allow_file

    def apply(self):
        with open(self.__get_devices_allow_file__(), "w") as allow:
            for device in self.devices:
                allow.write("a %d:%d rwm\n" % (device.major, device.minor))


class DeviceFilterCGroupsV2(DeviceFilterCommon):
    @classmethod
    def detect(cls):
        return os.path.exists("/sys/fs/cgroup/system.slice")

    DEFAULT_DEVICES = [
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

    def __init__(self, container: str, state_file: Optional[Path] = None):
        super().__init__(container, state_file)
        self.__cgroup__ = (
            f"/sys/fs/cgroup/system.slice/docker-{self.container_id}.scope"
        )
        if not os.path.exists(self.__cgroup__):
            self.__cgroup__ = f"/sys/fs/cgroup/docker/{self.container_id}"

    @property
    def devices(self):
        return self.DEFAULT_DEVICES + list(self.__devices__)

    def load(self, state_file: Path):
        if not state_file.exists():
            return
        with state_file.open() as f:
            for line in f.readlines():
                major, minor = line.split()
                self.add(Device(int(major), int(minor)))

    def save(self, state_file):
        with state_file.open("w") as f:
            for device in self.__devices__:
                f.write(f"{device.major} {device.minor}\n")

    def apply(self):
        existing = self.__get_existing_functions__()

        fd = os.open(self.__cgroup__, os.O_RDONLY)
        program = bytes(self.expand_template(), "utf-8")
        bpf = BPF(text=program)
        func = bpf.load_func("lava_docker_device_access_control", bpf.CGROUP_DEVICE)
        bpf.attach_func(func, fd, BPFAttachType.CGROUP_DEVICE, BPF_F_ALLOW_MULTI)
        bpf.close()
        os.close(fd)

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

    def __get_existing_functions__(self):
        cmd = ["/usr/sbin/bpftool", "cgroup", "list", self.__cgroup__, "--json"]
        data = subprocess.run(cmd, text=True, stdout=subprocess.PIPE).stdout
        result = []
        programs = []
        with contextlib.suppress(Exception):
            programs = json.loads(data)
        _attach_types = ["device", "cgroup_device"]
        if isinstance(programs, list):
            for program in programs:
                if isinstance(program, dict):
                    if program.get("attach_type") in _attach_types:
                        result.append(int(program["id"]))
        return result

    def expand_template(self):
        template = Template(TEMPLATE)
        return template.render(devices=self.devices)
