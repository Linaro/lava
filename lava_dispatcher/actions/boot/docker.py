# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import pathlib

from lava_common.constants import LAVA_DOWNLOADS
from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import BootHasMixin
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.shell import ExpectShellSession, ShellCommand, ShellSession
from lava_dispatcher.utils.network import dispatcher_ip


class BootDocker(Boot):
    @classmethod
    def action(cls):
        return BootDockerAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "docker" not in device["actions"]["boot"]["methods"]:
            return False, '"docker" was not in the device configuration boot methods'
        if parameters["method"] != "docker":
            return False, '"method" was not "docker"'
        if "command" not in parameters:
            return False, '"command" was not in boot parameters'
        return True, "accepted"


class BootDockerAction(BootHasMixin, RetryAction):
    name = "boot-docker"
    description = "boot docker image"
    summary = "boot docker image"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(CallDockerAction())
        if self.has_prompts(parameters):
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                self.pipeline.add_action(ExportDeviceEnvironment())


class CallDockerAction(Action):
    name = "docker-run"
    description = "call docker run on the image"
    summary = "call docker run"

    def __init__(self):
        super().__init__()
        self.cleanup_required = False
        self.remote = ""
        self.extra_options = ""
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
            self.remote = " --host %s" % options["remote"]
        if options["cpus"]:
            self.extra_options += " --cpus %s" % options["cpus"]
        if options["memory"]:
            self.extra_options += " --memory %s" % options["memory"]
        if options["privileged"]:
            self.extra_options += " --privileged"
        for cap in options["capabilities"]:
            self.extra_options += " --cap-add %s" % cap
        for device in options["devices"]:
            self.extra_options += " --device %s" % device
        for network in options["networks"]:
            self.extra_options += " --network %s" % network
        for volume in options["volumes"]:
            self.extra_options += " --volume %s" % volume
        for extra_argument in options["extra_arguments"]:
            self.extra_options += " " + extra_argument

    def run(self, connection, max_end_time):
        location = self.get_namespace_data(
            action="test", label="shared", key="location"
        )
        docker_image = self.get_namespace_data(
            action="deploy-docker", label="image", key="name"
        )

        # Build the command line
        # The docker image is safe to be included in the command line
        cmd = "docker" + self.remote + " run --rm --interactive --tty --hostname lava"
        cmd += " --name %s" % self.container
        if self.test_needs_overlay(self.parameters):
            overlay = self.get_namespace_data(
                action="test", label="results", key="lava_test_results_dir"
            )
            if not self.remote:
                cmd += " --volume %s:%s" % (
                    os.path.join(location, overlay.strip("/")),
                    overlay,
                )
            else:
                cmd += (
                    ' --mount type=volume,volume-driver=local,dst=%s,volume-opt=type=nfs,volume-opt=device=:%s,"volume-opt=o=addr=%s"'
                    % (
                        overlay,
                        os.path.join(location, overlay.strip("/")),
                        dispatcher_ip(self.job.parameters["dispatcher"]),
                    )
                )

        namespace = self.parameters.get(
            "downloads-namespace", self.parameters.get("namespace")
        )
        if namespace:
            downloads_dir = pathlib.Path(self.job.tmp_dir) / "downloads" / namespace
            if downloads_dir.exists():
                self.extra_options += " --volume %s:%s" % (
                    downloads_dir,
                    LAVA_DOWNLOADS,
                )

        cmd += self.extra_options
        cmd += " %s %s" % (docker_image, self.parameters["command"])

        self.logger.debug("Boot command: %s", cmd)
        shell = ShellCommand(cmd, self.timeout, logger=self.logger)
        self.cleanup_required = True

        shell_connection = ShellSession(self.job, shell)
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
                "docker %s stop %s" % (self.remote, self.container), allow_fail=True
            )
            self.cleanup_required = False
