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
from __future__ import annotations

import logging
import random
import subprocess
import time
from pathlib import Path
from string import ascii_lowercase, digits

from lava_common.exceptions import InfrastructureError

CONTAINER_NAME_RANDOM_SAMPLE = ascii_lowercase + digits


class DockerRun:
    def __init__(self, image):
        self.image = image
        self._local = False
        self._container_name = None
        self._network = None
        self._suffix = ""
        self._hostname = None
        self._workdir = None
        self._devices = []
        self._bind_mounts = []
        self._environment = []
        self._interactive = False
        self._tty = False
        self._docker_options = []
        self._docker_run_options = []
        self._enable_init = True

    @classmethod
    def from_parameters(cls, params, job) -> DockerRun:
        image = params["image"]
        run = cls(image)
        suffix = "-lava-" + str(job.job_id)
        if "container_name" in params:
            run.set_container_name(params["container_name"] + suffix)
        run.suffix = suffix
        run.network = params.get("network_from", None)
        run.local = params.get("local", False)
        return run

    @property
    def local(self):
        return self._local

    @local.setter
    def local(self, new_value):
        self._local = new_value

    def set_container_name(self, name, random_suffix=False):
        suffix = ""
        if random_suffix:
            suffix = "".join(
                (
                    random.SystemRandom().choice(CONTAINER_NAME_RANDOM_SAMPLE)
                    for i in range(10)
                )
            )
            self.suffix = suffix
        self._container_name = name + suffix

    @property
    def network(self):
        return self._network

    @network.setter
    def network(self, new_value):
        self._network = new_value

    @property
    def suffix(self):
        return self._suffix

    @suffix.setter
    def suffix(self, new_value):
        self._suffix = new_value

    @property
    def hostname(self):
        return self._hostname

    @hostname.setter
    def hostname(self, new_value):
        self._hostname = new_value

    @property
    def workdir(self):
        return self._workdir

    @workdir.setter
    def workdir(self, new_value):
        self._workdir = new_value

    def add_device(self, device, skip_missing=False):
        if not Path(device).exists() and skip_missing:
            return
        if ":" in device:
            return
        self._devices.append(device)

    def add_docker_options(self, *options):
        self._docker_options += options

    def add_docker_run_options(self, *options):
        self._docker_run_options += options

    def disable_init(self):
        self._enable_init = False

    def enable_interactive(self):
        self._interactive = True

    def enable_tty(self):
        self._tty = True

    def add_bind_mount(self, source, destination=None, read_only=False):
        if not destination:
            destination = source
        self._bind_mounts.append((source, destination, read_only))

    def add_environment_var(self, variable, value):
        self._environment.append((variable, value))

    def cmdline(self, *args):
        cmd = ["docker"] + self._docker_options + ["run"] + self._docker_run_options
        cmd += self.interaction_options()
        cmd += self.start_options()
        cmd.append(self.image)
        cmd += args
        return cmd

    def interaction_options(self):
        cmd = []
        if self._interactive:
            cmd.append("--interactive")
        if self._tty:
            cmd.append("--tty")
        return cmd

    def start_options(self):
        cmd = ["--rm"]
        if self._enable_init:
            cmd.append("--init")
        if container_name := self._container_name:
            cmd.append(f"--name={container_name}")
        if network_name := self.network:
            cmd.append(f"--network=container:{network_name}{self.suffix}")
        if hostname := self.hostname:
            cmd.append(f"--hostname={hostname}")
        if workdir := self._workdir:
            cmd.append(f"--workdir={workdir}")
        for dev in self._devices:
            cmd.append(f"--device={dev}")
        for src, dest, read_only in self._bind_mounts:
            opt = f"--mount=type=bind,source={src},destination={dest}"
            if read_only:
                opt += ",readonly=true"
            cmd.append(opt)
        for variable, value in self._environment:
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
        if self.local:
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
        self._check_image_arch()

    def wait(self, shell=None):
        delay = 1
        while True:
            try:
                # If possible, check that docker's shell command didn't exit
                # yet.
                if shell and not shell.isalive():
                    raise InfrastructureError("Docker container unexpectedly exited")
                subprocess.check_call(
                    ["docker", "inspect", "--format=.", self._container_name],
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
                    ["docker", "exec", self._container_name, "test", "-e", filename],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except subprocess.CalledProcessError:
                time.sleep(delay)
                delay = delay * 2  # exponential backoff

    def destroy(self):
        if self._container_name:
            subprocess.call(
                ["docker", "rm", "-f", self._container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _check_image_arch(self):
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
    def __init__(self, image):
        super().__init__(image)
        self._started = False

    def run(self, args, action=None):
        self.start(action)
        cmd = ["docker", *self._docker_options, "exec"]
        cmd += self.interaction_options()
        cmd.append(self._container_name)
        cmd += args
        self.run_cmd(cmd, action)

    def get_output(self, args, action=None):
        if action:
            runner = action.parsed_command
        else:
            runner = self.check_output
        self.start(action)
        cmd = ["docker", *self._docker_options, "exec"]
        cmd += self.interaction_options()
        cmd.append(self._container_name)
        cmd += args
        return runner(cmd)

    def check_output(self, cmd):
        return subprocess.check_output(cmd).decode("utf-8")

    def start(self, action=None):
        if self._started:
            return

        cmd = ["docker", "run", "--detach"]
        cmd += self.start_options()
        cmd.append(self.image)
        cmd += ["sleep", "infinity"]
        self.run_cmd(cmd, action)
        self.wait()
        self._started = True

    def stop(self, action=None):
        self.run_cmd(["docker", "stop", self._container_name])
