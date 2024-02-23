# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import re
import subprocess  # nosec - internal

from lava_common.exceptions import InfrastructureError
from lava_common.schemas import docker_image_format_pattern
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.utils.shell import which


class DockerAction(Action):
    name = "deploy-docker"
    description = "deploy docker images"
    summary = "deploy docker"

    def __init__(self):
        super().__init__()
        self.remote = []

    def validate(self):
        super().validate()
        which("docker")

        options = self.job.device["actions"]["deploy"]["methods"]["docker"]["options"]
        if options["remote"]:
            self.remote = ["--host"] + [options["remote"]]

        # Print docker version
        try:
            out = subprocess.check_output(  # nosec - internal
                ["docker"] + self.remote + ["version", "-f", "{{.Server.Version}}"]
            )
            out = out.decode("utf-8", errors="replace").strip("\n")
            self.logger.debug("docker server, installed at version: %s", out)
            out = subprocess.check_output(  # nosec - internal
                ["docker", "version", "-f", "{{.Client.Version}}"]
            )
            out = out.decode("utf-8", errors="replace").strip("\n")
            self.logger.debug("docker client, installed at version: %s", out)
        except subprocess.CalledProcessError as exc:
            raise InfrastructureError("Unable to call '%s': %s" % (exc.cmd, exc.output))
        except OSError:
            raise InfrastructureError("Command 'docker' does not exist")

        # "image" can be a dict or a string
        image = self.parameters["image"]
        if isinstance(image, str):
            self.image_name = image
            self.local = False
        else:
            self.image_name = image["name"]
            self.local = image.get("local", False)

        # check docker image name
        # The string should be safe for command line inclusion
        if re.compile(docker_image_format_pattern).match(self.image_name) is None:
            self.errors = "image name '%s' is invalid" % self.image_name
        self.set_namespace_data(
            action=self.name, label="image", key="name", value=self.image_name
        )

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment())
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())

    def run(self, connection, max_end_time):
        # Pull the image
        pull = not self.local
        if self.local:
            cmd = (
                ["docker"]
                + self.remote
                + [
                    "image",
                    "inspect",
                    "--format",
                    f"Image {self.image_name} exists locally",
                    self.image_name,
                ]
            )
            if self.run_cmd(cmd, allow_fail=True):
                self.logger.warning(
                    "Unable to inspect docker image '%s'", self.image_name
                )
                pull = True
        if pull:
            self.run_cmd(
                ["docker"] + self.remote + ["pull", self.image_name],
                error_msg="Unable to pull docker image '%s'" % self.image_name,
            )

        return super().run(connection, max_end_time)


class Docker(Deployment):
    name = "docker"

    @classmethod
    def action(cls):
        return DockerAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "docker" not in device["actions"]["deploy"]["methods"]:
            return False, "'docker' not in the device configuration deploy methods"
        if parameters["to"] != "docker":
            return False, '"to" parameter is not "docker"'
        if "image" not in parameters:
            return False, '"image" is not in the deployment parameters'
        return True, "accepted"
