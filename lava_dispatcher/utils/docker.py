# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import random
import subprocess
import time
from pathlib import Path
from typing import Optional

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
        self.__init = True
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
        for device in params.get("devices", list()):
            run.add_device(device)
        return run

    def local(self, local):
        self.__local__ = local

    def name(self, name, random_suffix=False):
        suffix = ""
        if random_suffix:
            CHARS = "01234567890abcdefghijklmnopqrtsuwxyz"
            suffix = "".join(random.SystemRandom().choice(CHARS) for i in range(10))
        self.__name__ = name + suffix

    def network(self, network):
        self.__network__ = network

    def suffix(self, suffix):
        self.__suffix__ = suffix

    def hostname(self, hostname):
        self.__hostname__ = hostname

    def workdir(self, workdir):
        self.__workdir__ = workdir

    def init(self, init):
        self.__init = init

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
        cmd = ["--rm"]
        if self.__init:
            cmd.append("--init")
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

    def run(self, *args, action, capture=False, error_msg=None):
        self.prepare(action)
        cmd = self.cmdline(*args)
        if capture:
            return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode(
                "utf-8", errors="replace"
            )
        else:
            return action.run_cmd(cmd, error_msg=error_msg)

    def prepare(self, action):
        pull = not self.__local__
        if self.__local__:
            if action.run_cmd(
                [
                    "docker",
                    *self.__docker_options__,
                    "image",
                    "inspect",
                    "--format",
                    f"Image {self.image} exists locally",
                    self.image,
                ],
                allow_fail=True,
            ):
                action.logger.warning(
                    "Unable to inspect docker image '%s'" % self.image
                )
                pull = True
        if pull:
            action.run_cmd(["docker", *self.__docker_options__, "pull", self.image])
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
                    [
                        "docker",
                        *self.__docker_options__,
                        "inspect",
                        "--format=.",
                        self.__name__,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except subprocess.CalledProcessError:
                time.sleep(delay)
                delay = delay * 2  # exponential backoff

    def wait_file(self, filename: str, timeout: Optional[int] = None) -> None:
        delay = 1
        start = time.monotonic()
        while True:
            try:
                subprocess.check_call(
                    [
                        "docker",
                        *self.__docker_options__,
                        "exec",
                        self.__name__,
                        "test",
                        "-e",
                        filename,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except subprocess.CalledProcessError:
                if timeout is not None and time.monotonic() - start > timeout:
                    raise
                time.sleep(delay)
                delay = delay * 2  # exponential backoff

    def destroy(self):
        if self.__name__:
            subprocess.call(
                ["docker", *self.__docker_options__, "rm", "-f", self.__name__],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def __check_image_arch__(self):
        host = subprocess.check_output(["arch"], text=True).strip()
        try:
            container = subprocess.check_output(
                [
                    "docker",
                    *self.__docker_options__,
                    "inspect",
                    "--format",
                    "{{.Architecture}}",
                    self.image,
                ],
                text=True,
            ).strip()
        except FileNotFoundError:
            raise InfrastructureError("'docker' command not available on the worker")
        # amd64 = x86_64
        if host == "amd64":
            host = "x86_64"
        if container == "amd64":
            container = "x86_64"
        if host == "arm64":
            host = "aarch64"
        if container == "arm64":
            container = "aarch64"
        if host != container:
            logger = logging.getLogger("dispatcher")
            logger.warning(
                f"Architecture mismatch: host is {host}, container is {container}. This *might* work, but if it does, will probably be a lot slower than if the container image architecture matches the host."
            )


class DockerContainer(DockerRun):
    __started__ = False

    def run(self, args, action):
        self.start(action)
        cmd = ["docker", *self.__docker_options__, "exec"]
        cmd += self.interaction_options()
        cmd.append(self.__name__)
        cmd += args
        action.run_cmd(cmd)

    def get_output(self, args, action):
        self.start(action)
        cmd = ["docker", *self.__docker_options__, "exec"]
        cmd += self.interaction_options()
        cmd.append(self.__name__)
        cmd += args
        return action.parsed_command(cmd)

    def check_output(self, cmd):
        return subprocess.check_output(cmd).decode("utf-8")

    def start(self, action):
        if self.__started__:
            return

        cmd = ["docker", *self.__docker_options__, "run", "--detach"]
        cmd += self.start_options()
        cmd.append(self.image)
        cmd += ["sleep", "infinity"]
        action.run_cmd(cmd)
        self.wait()
        self.__started__ = True

    def stop(self, action):
        action.run_cmd(["docker", *self.__docker_options__, "stop", self.__name__])
