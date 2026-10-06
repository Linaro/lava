# Copyright (C) 2021 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lava_common.exceptions import InfrastructureError

logger = logging.getLogger(__name__)

BPFTOOL = "/usr/sbin/bpftool"
# Built at package build time (src/bpf/) and loaded as-is: the daemon needs
# neither kernel headers nor clang, and loads no modules at runtime.
BPF_OBJECT = "/usr/share/lava-dispatcher-host/bpf/lava_device_filter.bpf.o"
BPF_PROGRAM = "lava_docker_device_access_control"
BPF_MAP = "allowed_devices"
PIN_BASE = "/sys/fs/bpf/lava"
# Per-container apply locks live here, not under PIN_BASE: bpffs holds no
# regular files.
LOCK_DIR = "/run/lock"
# Wildcard minor for "major only" entries (e.g. 136:* for /dev/pts/N).
# dev_t minors are 20 bits wide, so this can never collide with a real one.
ANY_MINOR = 0xFFFFFFFF


@dataclass(frozen=True)
class Device:
    major: int
    minor: int | None = None


def DeviceFilter(*args, **kwargs):
    for klass in [DeviceFilterCGroupsV1, DeviceFilterCGroupsV2]:
        if klass.detect():
            return klass(*args, **kwargs)
    raise InfrastructureError(
        "Neither cgroups v1 nor v2 detected; can't share device with docker container"
    )


class DeviceFilterCommon:
    def __init__(self, container, state_file: Path | None = None):
        self.__devices__: set[Device] = set()
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
        dirs = ["/sys/fs/cgroup/devices/docker", "/sys/fs/cgroup/devices/system.slice"]
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

    def __init__(self, container: str, state_file: Path | None = None):
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
                self.add(Device(int(major), None if minor == "*" else int(minor)))

    def save(self, state_file):
        with state_file.open("w") as f:
            for device in self.__devices__:
                # "*" is a wildcard minor, the same case as the ANY_MINOR key
                minor = "*" if device.minor is None else device.minor
                f.write(f"{device.major} {minor}\n")

    def apply(self):
        # Serialize applies per container: the leading rmtree would
        # otherwise drop a concurrent apply's pins.
        with open(
            os.path.join(LOCK_DIR, f"lava-dispatcher-host-{self.container_id}.lock"),
            "w",
        ) as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.__apply__()

    def __apply__(self):
        existing = self.__get_existing_functions__()
        pin_dir = os.path.join(PIN_BASE, self.container_id[:12])
        prog_pin = os.path.join(pin_dir, "prog")
        maps_pin = os.path.join(pin_dir, "maps")
        attached = False

        try:
            # One program instance (with its own map) per container. The old
            # program stays attached until the new one is in place: with
            # cgroups v2, no device program means unrestricted access.
            shutil.rmtree(pin_dir, ignore_errors=True)
            os.makedirs(prog_pin)
            subprocess.check_call(
                [BPFTOOL, "prog", "loadall", BPF_OBJECT, prog_pin, "pinmaps", maps_pin]
            )
            map_pin = os.path.join(maps_pin, BPF_MAP)
            for device in self.devices:
                minor = ANY_MINOR if device.minor is None else device.minor
                key = [f"0x{b:02x}" for b in struct.pack("@II", device.major, minor)]
                subprocess.check_call(
                    [
                        BPFTOOL,
                        "map",
                        "update",
                        "pinned",
                        map_pin,
                        "key",
                        *key,
                        "value",
                        "0x01",
                        "0x00",
                        "0x00",
                        "0x00",
                    ]
                )
            subprocess.check_call(
                [
                    BPFTOOL,
                    "cgroup",
                    "attach",
                    self.__cgroup__,
                    "device",
                    "pinned",
                    os.path.join(prog_pin, BPF_PROGRAM),
                    "multi",
                ]
            )
            attached = True
            for fid in existing:
                subprocess.check_call(
                    [
                        BPFTOOL,
                        "cgroup",
                        "detach",
                        self.__cgroup__,
                        "device",
                        "id",
                        str(fid),
                    ]
                )
            # The cgroup holds its own reference to the program, so the pin
            # is only needed between loadall and attach. Leaving it behind
            # leaks a program and a map per container.
            shutil.rmtree(pin_dir, ignore_errors=True)

        except Exception as exc:
            logger.error(f"Failed to apply BPF for {self.__cgroup__}: {exc}")
            # Unpin either way: an attached program is held by the cgroup,
            # and this drops the half-loaded instance.
            shutil.rmtree(pin_dir, ignore_errors=True)
            if not attached:
                logger.error(
                    "Device sharing needs the pre-compiled BPF object "
                    f"{BPF_OBJECT} and a kernel with BTF "
                    "(CONFIG_DEBUG_INFO_BTF=y, stock Debian 11+)."
                )

    def __get_existing_functions__(self):
        cmd = [BPFTOOL, "cgroup", "list", self.__cgroup__, "--json"]
        data = subprocess.run(
            cmd, text=True, check=False, stdout=subprocess.PIPE
        ).stdout
        result = []
        programs = []
        with contextlib.suppress(Exception):
            programs = json.loads(data)
        _attach_types = ["device", "cgroup_device"]
        if isinstance(programs, list):
            for program in programs:
                if isinstance(program, dict):
                    attach_type = program.get("attach_type")
                    if attach_type in _attach_types and program.get("id") is not None:
                        result.append(int(program["id"]))
        return result
