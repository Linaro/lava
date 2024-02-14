# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import logging
import random
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from lava_common.exceptions import InfrastructureError

if TYPE_CHECKING:
    from typing import Iterable

    from lava_dispatcher.action import Action


class DockerRun:
    def __init__(self, image: str):
        self.image = image
        self._local_image_enabled = False
        self._container_name: str | None = None
        self._network_name: str | None = None
        self._suffix = ""
        self._hostname: str | None = None
        self._workdir_path: str | None = None
        self._devices_paths: list[str] = []
        self._bind_mounts: list[tuple[str, str, bool]] = []
        self._environment_variables: list[tuple[str, str]] = []
        self._interactive_enabled = False
        self._tty_enabled = False
        self._init_enabled = True
        self._docker_options: list[str] = []
        self._docker_run_options: list[str] = []

    @classmethod
    def from_parameters(cls, params, job):
        image = params["image"]
        run = cls(image)
        suffix = "-lava-" + str(job.job_id)
        if "container_name" in params:
            run.set_container_name(params["container_name"] + suffix)
        run.set_suffix(suffix)
        run.set_network_name(params.get("network_from", None))
        if params.get("local"):
            run.enale_local_image()
        for device in params.get("devices", list()):
            run.add_device(device)
        return run

    def enale_local_image(self) -> None:
        self._local_image_enabled = True

    def disable_local_image(self) -> None:
        self._local_image_enabled = False

    @property
    def container_name(self) -> str | None:
        return self._container_name

    def set_container_name(self, name: str, random_suffix: bool = False):
        suffix = ""
        if random_suffix:
            CHARS = "01234567890abcdefghijklmnopqrtsuwxyz"
            suffix = "".join(random.SystemRandom().choice(CHARS) for i in range(10))
        self._container_name = name + suffix

    def set_network_name(self, network_name: str | None) -> None:
        self._network_name = network_name

    def set_suffix(self, new_suffix: str) -> None:
        self._suffix = new_suffix

    def set_hostname(self, new_hostname: str) -> None:
        self._hostname = new_hostname

    def set_workdir_path(self, new_workdir_path: str) -> None:
        self._workdir_path = new_workdir_path

    def enable_init(self) -> None:
        self._init_enabled = True

    def disable_init(self) -> None:
        self._init_enabled = False

    def add_device(self, device: str, skip_missing: bool = False) -> None:
        if not Path(device).exists() and skip_missing:
            return
        if ":" in device:
            return
        self._devices_paths.append(device)

    def add_docker_options(self, *options: str) -> None:
        self._docker_options.extend(options)

    def add_docker_run_options(self, *options: str) -> None:
        self._docker_run_options.extend(options)

    def add_device_docker_method_options(
        self, docker_method_conf: dict[str, Iterable[None | list[str] | str]]
    ) -> None:
        # Preprocess docker option list, to better support partial
        # overriding of them via device dict:
        # 1. Filter out None, to make it easier to template
        # YAML syntactic lists with Jinja2:
        # '- {{ some_opt_from_device_dict }}'
        # (if not default, will be set to None).
        # 2. Flatten sublists, `- ['--opt1', '--opt2']`.
        def preproc_opts(opts: Iterable[None | list[str] | str]) -> list[str]:
            res = []
            for o in opts:
                if o is None:
                    continue
                elif isinstance(o, list):
                    res.extend(o)
                else:
                    res.append(o)
            return res

        if "global_options" in docker_method_conf:
            self.add_docker_options(*preproc_opts(docker_method_conf["global_options"]))
        if "options" in docker_method_conf:
            self.add_docker_run_options(*preproc_opts(docker_method_conf["options"]))

    def enable_interactive(self) -> None:
        self._interactive_enabled = True

    def enable_tty(self) -> None:
        self._tty_enabled = True

    def add_bind_mount(
        self,
        source: Path | str,
        destination: Path | str | None = None,
        read_only: bool = False,
    ) -> None:
        if not destination:
            destination = source
        self._bind_mounts.append((str(source), str(destination), read_only))

    def add_environment_variable(self, variable: str, value: str) -> None:
        self._environment_variables.append((variable, value))

    def cmdline(self, *args: str) -> list[str]:
        cmd = ["docker"] + self._docker_options + ["run"] + self._docker_run_options
        cmd += self.interaction_options()
        cmd += self.start_options()
        cmd.append(self.image)
        cmd += args
        return cmd

    def interaction_options(self) -> list[str]:
        cmd = []
        if self._interactive_enabled:
            cmd.append("--interactive")
        if self._tty_enabled:
            cmd.append("--tty")
        return cmd

    def start_options(self) -> list[str]:
        cmd = ["--rm"]
        if self._init_enabled:
            cmd.append("--init")
        if self._container_name:
            cmd.append(f"--name={self._container_name}")
        if self._network_name:
            cmd.append(f"--network=container:{self._network_name}{self._suffix}")
        if self._hostname:
            cmd.append(f"--hostname={self._hostname}")
        if self._workdir_path:
            cmd.append(f"--workdir={self._workdir_path}")
        for dev in self._devices_paths:
            cmd.append(f"--device={dev}")
        for src, dest, read_only in self._bind_mounts:
            bind_mount_opt = f"--mount=type=bind,source={src},destination={dest}"
            if read_only:
                bind_mount_opt += ",readonly=true"
            cmd.append(bind_mount_opt)
        for variable, value in self._environment_variables:
            cmd.append(f"--env={variable}={value}")
        return cmd

    def run(
        self,
        *args: str,
        action: Action,
        capture: bool = False,
        error_msg: str | None = None,
    ) -> str | int | None:
        self.prepare(action)
        cmd = self.cmdline(*args)
        if capture:
            return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode(
                "utf-8", errors="replace"
            )
        else:
            return action.run_cmd(cmd, error_msg=error_msg)

    def prepare(self, action: Action) -> None:
        pull = not self._local_image_enabled
        if self._local_image_enabled:
            if action.run_cmd(
                [
                    "docker",
                    *self._docker_options,
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
            action.run_cmd(["docker", *self._docker_options, "pull", self.image])
        self._check_image_arch()

    def wait(self, shell=None) -> None:
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
                        *self._docker_options,
                        "inspect",
                        "--format=.",
                        self._container_name,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except subprocess.CalledProcessError:
                time.sleep(delay)
                delay = delay * 2  # exponential backoff

    def wait_file(self, filename: str, timeout: int | None = None) -> None:
        delay = 1
        start = time.monotonic()
        while True:
            try:
                subprocess.check_call(
                    [
                        "docker",
                        *self._docker_options,
                        "exec",
                        self._container_name,
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

    def destroy(self) -> None:
        if self._container_name:
            subprocess.call(
                ["docker", *self._docker_options, "rm", "-f", self._container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _check_image_arch(self) -> None:
        host = subprocess.check_output(["arch"], text=True).strip()
        try:
            container = subprocess.check_output(
                [
                    "docker",
                    *self._docker_options,
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
                f"Architecture mismatch: host is {host}, "
                f"container is {container}. This *might* work, but if it does, "
                "will probably be a lot slower than if the container "
                "image architecture matches the host."
            )


class DockerContainer(DockerRun):
    _started = False

    def run(self, args: list[str], action: Action) -> None:
        self.start(action)
        cmd = ["docker", *self._docker_options, "exec"]
        cmd += self.interaction_options()
        cmd.append(self._container_name)
        cmd += args
        action.run_cmd(cmd)

    def get_output(self, args: list[str], action: Action) -> str:
        self.start(action)
        cmd = ["docker", *self._docker_options, "exec"]
        cmd += self.interaction_options()
        cmd.append(self._container_name)
        cmd += args
        return action.parsed_command(cmd)

    def check_output(self, cmd: list[str]) -> str:
        return subprocess.check_output(cmd).decode("utf-8")

    def start(self, action: Action) -> None:
        if self._started:
            return

        cmd = [
            "docker",
            *self._docker_options,
            "run",
            *self._docker_run_options,
            "--detach",
        ]
        cmd += self.start_options()
        cmd.append(self.image)
        cmd += ["sleep", "infinity"]
        action.run_cmd(cmd)
        self.wait()
        self._started = True

    def stop(self, action: Action) -> None:
        action.run_cmd(["docker", *self._docker_options, "stop", self._container_name])
