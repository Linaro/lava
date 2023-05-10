# Copyright (C) 2020 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
import contextlib
from pathlib import Path

from django.conf import settings
from jinja2 import FileSystemLoader


class File:
    KINDS = {
        "device": ([settings.DEVICES_PATH], "{name}.jinja2"),
        "device-type": (settings.DEVICE_TYPES_PATHS, "{name}.jinja2"),
        "dispatcher": [
            "/etc/lava-server/dispatcher.d/{name}/dispatcher.yaml",
            "/etc/lava-server/dispatcher.d/{name}.yaml",
        ],
        "env": [
            "/etc/lava-server/dispatcher.d/{name}/env.yaml",
            "/etc/lava-server/env.yaml",
        ],
        "env-dut": [
            "/etc/lava-server/dispatcher.d/{name}/env-dut.yaml",
            "/etc/lava-server/env-dut.yaml",
            # DEPRECATED since 2020.10
            "/etc/lava-server/env.dut.yaml",
        ],
        "health-check": ([settings.HEALTH_CHECKS_PATH], "{name}.yaml"),
    }
    LOADER_KINDS = ["device", "device-type"]
    LIST_KINDS = ["device", "device-type", "health-check"]

    def __init__(self, kind, name=None):
        if kind not in self.KINDS:
            raise NotImplementedError(f"Unknown kind {kind}")

        self.files = []
        if name is not None:
            if isinstance(self.KINDS[kind], tuple):
                f = self.KINDS[kind][1].format(name=name)
                for p in self.KINDS[kind][0]:
                    self.files.append(Path(p.format(name=name)) / f)
            else:
                for p in self.KINDS[kind]:
                    self.files.append(Path(p.format(name=name)))
        self.kind = kind
        self.name = name

    def exists(self):
        for f in self.files:
            if f.exists():
                return True
        return False

    def is_first(self):
        return self.files[0].exists()

    def list(self, pattern):
        if self.kind not in self.LIST_KINDS:
            raise NotImplementedError("Not available for this kind")
        ret = set()
        for p in self.KINDS[self.kind][0]:
            for filename in Path(p).glob(pattern):
                ret.add(filename.name)
        return sorted(ret)

    def loader(self):
        if self.kind not in self.LOADER_KINDS:
            raise NotImplementedError("Not available for this kind")

        if self.kind == "device":
            return FileSystemLoader(
                self.KINDS["device"][0] + self.KINDS["device-type"][0]
            )
        elif self.kind == "device-type":
            return FileSystemLoader(self.KINDS["device-type"][0])

    def read(self, raising=True):
        for f in self.files:
            with contextlib.suppress(OSError):
                return f.read_text(encoding="utf-8")
        if raising:
            raise FileNotFoundError(f"{self.name} does not exists")
        return ""

    def write(self, data):
        path = self.files[0]
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if data:
            path.write_text(data, encoding="utf-8")
        else:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
