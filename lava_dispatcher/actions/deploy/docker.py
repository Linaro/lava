# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lava_common.schemas import docker_image_format_pattern
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.utils.docker import DockerContainer
from lava_dispatcher.utils.shell import which

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class DockerAction(Action):
    name = "deploy-docker"
    description = "deploy docker images"
    summary = "deploy docker"

    def __init__(self, job: Job):
        super().__init__(job)
        # Dummy value
        self.docker_container = DockerContainer("")

    def validate(self):
        super().validate()
        which("docker")

        # "image" can be a dict or a string
        image = self.parameters["image"]
        if isinstance(image, str):
            self.docker_container = DockerContainer(image)
        else:
            self.docker_container = DockerContainer.from_parameters(image, self.job)

        options = self.job.device["actions"]["deploy"]["methods"]["docker"]["options"]
        if options["remote"]:
            self.docker_container.add_docker_options("--host", options["remote"])

        # Print docker version
        out = self.parsed_command(
            [
                *self.docker_container.docker_cmdline("version"),
                "-f",
                r"{{.Server.Version}}",
            ],
        ).strip("\n")
        self.logger.debug("docker server, installed at version: %s", out)
        out = self.parsed_command(  # nosec - internal
            ["docker", "version", "-f", "{{.Client.Version}}"]
        ).strip("\n")
        self.logger.debug("docker client, installed at version: %s", out)

        # check docker image name
        # The string should be safe for command line inclusion
        if re.compile(docker_image_format_pattern).match(self.image_name) is None:
            self.errors = "image name '%s' is invalid" % self.image_name
        self.set_namespace_data(
            action="deploy-docker", label="image", key="name", value=self.image_name
        )

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment(self.job))
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction(self.job))

    def run(self, connection, max_end_time):
        # Pull the image
        self.docker_container.prepare(self)

        return super().run(connection, max_end_time)
