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
import random
import subprocess
import time

from lava_common.exceptions import InfrastructureError


class DockerRun:
    def __init__(self, image):
        self.image = image
        self.__local__ = False
        self.__name__ = None
        self.__network__ = None
        self.__suffix__ = ""
        self.__hostname__ = None
        self.__workdir__ = None
        self.__devices__ = []
        self.__bind_mounts__ = []
        self.__environment__ = []
        self.__interactive__ = False
        self.__tty__ = False
        self.__docker_options__ = []
        self.__docker_run_options__ = []

    @classmethod
    def from_parameters(cls, params, job):
        image = params["image"]
        run = cls(image)
        suffix = "-lava-" + str(job.job_id)
        if "container_name" in params:
            run.name(params["container_name"] + suffix)
        run.suffix(suffix)
        run.network(params.get("network_from", None))
        run.local(params.get("local", False))
        return run

    def local(self, local):
        self.__local__ = local

    def name(self, name, random_suffix=False):
        suffix = ""
        if random_suffix:
            CHARS = "01234567890abcdefghijklmnopqrtsuwxyz"
            suffix = "".join((random.SystemRandom().choice(CHARS) for i in range(10)))
        self.__name__ = name + suffix

    def network(self, network):
        self.__network__ = network

    def suffix(self, suffix):
        self.__suffix__ = suffix

    def hostname(self, hostname):
        self.__hostname__ = hostname

    def workdir(self, workdir):
        self.__workdir__ = workdir

    def add_device(self, device, skip_missing=False):
        if not Path(device).exists() and skip_missing:
            return
        if ":" in device:
            return
        self.__devices__.append(device)

    def add_docker_options(self, *options):
        self.__docker_options__ += options

    def add_docker_run_options(self, *options):
        self.__docker_run_options__ += options

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
        cmd = (
            ["docker"] + self.__docker_options__ + ["run"] + self.__docker_run_options__
        )
        cmd += self.interaction_options()
        cmd += self.start_options()
        cmd.append(self.image)
        cmd += args
        return cmd

    def interaction_options(self):
        cmd = []
        if self.__interactive__:
            cmd.append("--interactive")
        if self.__tty__:
            cmd.append("--tty")
        return cmd

    def start_options(self):
        cmd = ["--rm", "--init"]
        if self.__name__:
            cmd.append(f"--name={self.__name__}")
        if self.__network__:
            cmd.append(f"--network=container:{self.__network__}{self.__suffix__}")
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
        return cmd

    def run(self, *args, action=None):
        self.prepare(action)
        cmd = self.cmdline(*args)
        self.run_cmd(cmd, action=action)

    def run_cmd(self, cmd, action=None):
        if action:
            runner = action.run_cmd
        else:
            runner = subprocess.check_call
        logger = logging.getLogger("dispatcher")
        logger.debug("cmd: %s", cmd)
        runner(cmd)

    def prepare(self, action=None):
        if self.__local__:
            self.run_cmd(
                [
                    "docker",
                    "image",
                    "inspect",
                    f"--format=Image {self.image} exists locally",
                    self.image,
                ],
                action=action,
            )
        else:
            self.run_cmd(["docker", "pull", self.image], action=action)
        self.__check_image_arch__()

    def wait(self, shell=None):
        delay = 1
        while True:
            try:
                # If possible, check that docker's shell command didn't exit
                # yet.
                if shell and not shell.isalive():
                    raise InfrastructureError("Docker container unexpectedly exited")
                subprocess.check_call(
                    ["docker", "inspect", "--format=.", self.__name__],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except subprocess.CalledProcessError:
                time.sleep(delay)
                delay = delay * 2  # exponential backoff

    def wait_file(self, filename):
        delay = 1
        while True:
            try:
                subprocess.check_call(
                    ["docker", "exec", self.__name__, "test", "-e", filename],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except subprocess.CalledProcessError:
                time.sleep(delay)
                delay = delay * 2  # exponential backoff

    def destroy(self):
        if self.__name__:
            subprocess.call(
                ["docker", "rm", "-f", self.__name__],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def __check_image_arch__(self):
        host = subprocess.check_output(["arch"], text=True).strip()
        container = subprocess.check_output(
            ["docker", "inspect", "--format", "{{.Architecture}}", self.image],
            text=True,
        ).strip()
        # amd64 = x86_64
        if host == "amd64":
            host = "x86_64"
        if container == "amd64":
            container = "x86_64"
        if host != container:
            logger = logging.getLogger("dispatcher")
            logger.warning(
                f"Architecture mismatch: host is {host}, container is {container}. This *might* work, but if it does, will probably be a lot slower than if the container image architecture matches the host."
            )


class DockerContainer(DockerRun):
    __started__ = False

    def run(self, args, action=None):
        self.start(action)
        cmd = ["docker", *self.__docker_options__, "exec"]
        cmd += self.interaction_options()
        cmd.append(self.__name__)
        cmd += args
        self.run_cmd(cmd, action)

    def get_output(self, args, action=None):
        if action:
            runner = action.parsed_command
        else:
            runner = self.check_output
        self.start(action)
        cmd = ["docker", *self.__docker_options__, "exec"]
        cmd += self.interaction_options()
        cmd.append(self.__name__)
        cmd += args
        return runner(cmd)

    def check_output(self, cmd):
        return subprocess.check_output(cmd).decode("utf-8")

    def start(self, action=None):
        if self.__started__:
            return

        cmd = ["docker", "run", "--detach"]
        cmd += self.start_options()
        cmd.append(self.image)
        cmd += ["sleep", "infinity"]
        self.run_cmd(cmd, action)
        self.wait()
        self.__started__ = True

    def stop(self, action=None):
        # Not calling run_cmd on purpose, to hide this from the logs
        subprocess.check_call(
            ["docker", "stop", self.__name__],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
