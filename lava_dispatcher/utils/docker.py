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

import logging
from pathlib import Path
import subprocess


class DockerRun:
    def __init__(self, image):
        self.image = image
        self.__name__ = None
        self.__hostname__ = None
        self.__workdir__ = None
        self.__devices__ = []
        self.__bind_mounts__ = []
        self.__environment__ = []
        self.__interactive__ = False
        self.__tty__ = False

    def name(self, name):
        self.__name__ = name

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

    def tty(self):
        self.__tty__ = True

    def bind_mount(self, source, destination=None, read_only=False):
        if not destination:
            destination = source
        self.__bind_mounts__.append((source, destination, read_only))

    def environment(self, variable, value):
        self.__environment__.append((variable, value))

    def cmdline(self, *args):
        cmd = ["docker", "run", "--rm"]
        if self.__interactive__:
            cmd.append("--interactive")
        if self.__tty__:
            cmd.append("--tty")
        if self.__name__:
            cmd.append(f"--name={self.__name__}")
        if self.__hostname__:
            cmd.append(f"--hostname={self.__hostname__}")
        if self.__workdir__:
            cmd.append(f"--workdir={self.__workdir__}")
        for dev in self.__devices__:
            cmd.append(f"--device={dev}")
        for src, dest, read_only in self.__bind_mounts__:
            opt = f"--mount=type=bind,source={src},destination={dest}"
            if read_only:
                opt += ",readonly=true"
            cmd.append(opt)
        for variable, value in self.__environment__:
            cmd.append(f"--env={variable}={value}")
        cmd.append(self.image)
        cmd += args
        return cmd

    def run(self, *args, action=None):
        cmd = self.cmdline(*args)
        self.__check_image_arch__()
        if action:
            run_cmd = action.run_cmd
        else:
            run_cmd = subprocess.check_call
        run_cmd(["docker", "pull", self.image])
        run_cmd(cmd)

    def __check_image_arch__(self):
        host = subprocess.check_output(["arch"], text=True).strip()
        container = subprocess.check_output(
            ["docker", "run", "--rm", self.image, "arch"], text=True
        ).strip()
        if host != container:
            logger = logging.getLogger("dispatcher")
            logger.warning(
                f"Architecture mismatch: host is {host}, container is {container}. This *might* work, but if it does, will probably be a lot slower than if the container image architecture matches the host."
            )
