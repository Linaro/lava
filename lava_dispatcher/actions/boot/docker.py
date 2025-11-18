# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import pathlib
from typing import TYPE_CHECKING

from lava_common.constants import LAVA_DOWNLOADS
from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import BootHasMixin
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.shell import ExpectShellSession, ShellCommand, ShellSession
from lava_dispatcher.utils.network import dispatcher_ip

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class BootDockerAction(BootHasMixin, RetryAction):
    name = "boot-docker"
    description = "boot docker image"
    summary = "boot docker image"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(CallDockerAction(self.job))
        if self.has_prompts(parameters):
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession(self.job))
                self.pipeline.add_action(ExportDeviceEnvironment(self.job))


class CallDockerAction(Action):
    name = "docker-run"
    description = "call docker run on the image"
    summary = "call docker run"

    def __init__(self, job: Job):
        super().__init__(job)
        self.cleanup_required = False
        self.remote: list[str] = []
        self.extra_options: list[str] = []
        self.container = ""

    def validate(self):
        super().validate()
        self.container = "lava-%s-%s" % (self.job.job_id, self.level)
        prefix = self.job.parameters.get("dispatcher", {}).get("prefix", "")
        if prefix:
            self.container = "lava-%s-%s-%s" % (prefix, self.job.job_id, self.level)

        options = self.job.device["actions"]["boot"]["methods"]["docker"]["options"]

        docker_image = self.get_namespace_data(
            action="deploy-docker", label="image", key="name"
        )
        if docker_image is None:
            raise JobError("Missing deploy action before boot")

        if options["remote"]:
            self.remote = ["--host", options["remote"]]
        if options["cpus"]:
            self.extra_options.extend(("--cpus", options["cpus"]))
        if options["memory"]:
            self.extra_options.extend(("--memory", options["memory"]))
        if options["privileged"]:
            self.extra_options.append("--privileged")
        for cap in options["capabilities"]:
            self.extra_options.extend(("--cap-add", cap))
        for device in options["devices"]:
            self.extra_options.extend(("--device", os.path.realpath(device)))
        for network in options["networks"]:
            self.extra_options.extend(("--network", network))
        for volume in options["volumes"]:
            self.extra_options.extend(("--volume", volume))

        self.extra_options.extend(options["extra_arguments"])

    def run(self, connection, max_end_time):
        location = self.get_namespace_data(
            action="test", label="shared", key="location"
        )
        docker_image = self.get_namespace_data(
            action="deploy-docker", label="image", key="name"
        )

        # Build the command line
        # The docker image is safe to be included in the command line
        cmd_args: list[str] = [
            *self.remote,
            "run",
            "--rm",
            "--interactive",
            "--tty",
            "--hostname",
            "lava",
            "--name",
            self.container,
        ]
        if self.test_needs_overlay(self.parameters):
            overlay = self.get_namespace_data(
                action="test", label="results", key="lava_test_results_dir"
            )
            if not self.remote:
                cmd_args.append("--volume")
                cmd_args.append(
                    f"{os.path.join(location, overlay.strip('/'))}:{overlay}"
                )
            else:
                cmd_args.append("--mount")
                cmd_args.append(
                    f"type=volume,volume-driver=local,dst={overlay},volume-opt=type=nfs,"
                    f"volume-opt=device=:{os.path.join(location, overlay.strip('/'))},"
                    f"volume-opt=o=addr={dispatcher_ip(self.job.parameters['dispatcher'])}"
                )

        namespace = self.parameters.get(
            "downloads-namespace", self.parameters.get("namespace")
        )
        if namespace:
            downloads_dir = pathlib.Path(self.job.tmp_dir) / "downloads" / namespace
            if downloads_dir.exists():
                self.extra_options.extend(
                    ("--volume", f"{downloads_dir}:{LAVA_DOWNLOADS}")
                )

        cmd_args.extend(self.extra_options)
        cmd_args.append(docker_image)
        cmd_args.append(self.parameters["command"])

        self.logger.debug("Boot command: %s", cmd_args)
        shell = ShellCommand(
            "docker", args=cmd_args, lava_timeout=self.timeout, logger=self.logger
        )
        self.cleanup_required = True

        shell_connection = ShellSession(shell)
        shell_connection = super().run(shell_connection, max_end_time)

        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=shell_connection
        )
        return shell_connection

    def cleanup(self, connection):
        super().cleanup(connection)
        if self.cleanup_required:
            self.logger.debug("Stopping container %s", self.container)
            self.run_cmd(
                ["docker", *self.remote, "stop", self.container], allow_fail=True
            )
            self.cleanup_required = False
