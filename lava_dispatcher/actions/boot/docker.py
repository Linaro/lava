# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os

from lava_common.exceptions import JobError
from lava_dispatcher.action import Pipeline, Action
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.actions.boot import BootAction
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.shell import ExpectShellSession, ShellCommand, ShellSession


class BootDocker(Boot):
    compatibility = 4

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = BootDockerAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if "docker" not in device["actions"]["boot"]["methods"]:
            return False, '"docker" was not in the device configuration boot methods'
        if parameters["method"] != "docker":
            return False, '"method" was not "docker"'
        if "command" not in parameters:
            return False, '"command" was not in boot parameters'
        return True, "accepted"


class BootDockerAction(BootAction):

    name = "boot-docker"
    description = "boot docker image"
    summary = "boot docker image"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        self.internal_pipeline.add_action(BootDockerRetry())
        if self.has_prompts(parameters):
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())


class BootDockerRetry(RetryAction):

    name = "boot-docker-retry"
    description = "boot docker image with retry"
    summary = "boot docker image"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        self.internal_pipeline.add_action(CallDockerAction())


class CallDockerAction(Action):

    name = "docker-run"
    description = "call docker run on the image"
    summary = "call docker run"

    def __init__(self):
        super().__init__()
        self.cleanup_required = False
        self.extra_options = ""
        self.container = ""

    def validate(self):
        super().validate()
        self.container = "lava-%s-%s" % (self.job.job_id, self.level)

        options = self.job.device["actions"]["boot"]["methods"]["docker"]["options"]

        docker_image = self.get_namespace_data(
            action="deploy-docker", label="image", key="name"
        )
        if docker_image is None:
            raise JobError("Missing deploy action before boot")

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
        for volume in options["volumes"]:
            self.extra_options += " --volume %s" % volume

    def run(self, connection, max_end_time):
        location = self.get_namespace_data(
            action="test", label="shared", key="location"
        )
        docker_image = self.get_namespace_data(
            action="deploy-docker", label="image", key="name"
        )

        # Build the command line
        # The docker image is safe to be included in the command line
        cmd = "docker run --rm --interactive --tty --hostname lava"
        cmd += " --name %s" % self.container
        if self.test_needs_overlay(self.parameters):
            overlay = self.get_namespace_data(
                action="test", label="results", key="lava_test_results_dir"
            )
            cmd += " --volume %s:%s" % (
                os.path.join(location, overlay.strip("/")),
                overlay,
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
            self.run_cmd(["docker", "stop", self.container], allow_fail=True)
            self.cleanup_required = False
