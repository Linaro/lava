# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

from pathlib import Path


class DockerRun:
    def __init__(self, image):
        self.image = image
        self.__hostname__ = None
        self.__workdir__ = None
        self.__devices__ = []
        self.__bind_mounts__ = []
        self.__interactive__ = False

    def hostname(self, hostname):
        self.__hostname__ = hostname

    def workdir(self, workdir):
        self.__workdir__ = workdir

    def add_device(self, device, skip_missing=False):
        if not Path(device).exists() and skip_missing:
            return
        self.__devices__.append(device)

    def interactive(self):
        self.__interactive__ = True

    def bind_mount(self, source, destination=None, read_only=False):
        if not destination:
            destination = source
        self.__bind_mounts__.append((source, destination, read_only))

    def cmdline(self):
        cmd = ["docker", "run", "--rm"]
        if self.__interactive__:
            cmd.append("--interactive")
            cmd.append("--tty")
        if self.__hostname__:
            cmd.append(f"--hostname={self.__hostname__}")
        if self.__workdir__:
            cmd.append(f"--workdir={self.__workdir__}")
        for dev in self.__devices__:
            cmd.append(f"--device={dev}")
        for src, dest, read_only in self.__bind_mounts__:
            opt = f"--mount=type=bind,source={src},destination={dest}"
            if read_only:
                opt += ",read_only=true"
            cmd.append(opt)
        cmd.append(self.image)
        return cmd
