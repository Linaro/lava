# Copyright (C) 2020 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import contextlib
import jinja2
import pathlib

from django.conf import settings


class File:
    KINDS = {
        "device": [settings.DEVICES_PATH],
        "device-type": settings.DEVICE_TYPES_PATHS,
        "health-check": [settings.HEALTH_CHECKS_PATH],
    }

    def __init__(self, kind):
        if kind not in self.KINDS:
            raise NotImplementedError(f"Unknow kind {kind}")
        self.directories = list(map(pathlib.Path, self.KINDS[kind]))
        self.kind = kind

    def exists(self, name):
        for directory in self.directories:
            if (directory / name).exists():
                return True
        return False

    def list(self, pattern):
        ret = set()
        for directory in self.directories:
            for filename in directory.glob(pattern):
                ret.add(filename)
        return sorted(ret)

    def loader(self):
        if self.kind == "device":
            return jinja2.FileSystemLoader(
                self.KINDS["device"] + self.KINDS["device-type"]
            )
        elif self.kind == "device-type":
            return jinja2.FileSystemLoader(self.KINDS["device-type"])
        else:
            raise NotImplementedError(f"Unknow loader for {self.kind}")

    def read(self, name):
        for directory in self.directories:
            with contextlib.suppress(FileNotFoundError):
                return (directory / name).read_text(encoding="utf-8")
        raise FileNotFoundError(f"{name} does not exists")

    def write(self, name, data):
        (self.directories[0] / name).write_text(data, encoding="utf-8")
