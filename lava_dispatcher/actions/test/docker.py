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
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os
import shlex
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.deploy.overlay import CreateOverlay
from lava_dispatcher.actions.test import TestAction
from lava_dispatcher.actions.test.shell import TestShellAction
from lava_dispatcher.logical import LavaTest
from lava_dispatcher.power import ReadFeedback
from lava_dispatcher.shell import ShellCommand, ShellSession
from lava_dispatcher_host import add_device_container_mapping


class DockerTest(LavaTest):
    """
    DockerTest Strategy object
    """

    priority = 10

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = DockerTestAction()
        self.action.job = self.job
        self.action.section = self.action_type
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if "definition" in parameters or "definitions" in parameters:
            if "docker" in parameters:
                return True, "accepted"
        return False, "docker or definition(s) not in parameters"

    @classmethod
    def needs_deployment_data(cls):
        return False

    @classmethod
    def needs_overlay(cls):
        return False

    @classmethod
    def has_shell(cls):
        return True


class DockerTestAction(TestAction):
    name = "lava-docker-test"
    description = "Runs tests in a docker container"
    summary = "Runs tests in a docker container, with the DUT available via adb/fastboot over USB"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(DockerTestSetEnvironment())
        self.pipeline.add_action(CreateOverlay())
        self.pipeline.add_action(DockerTestShell())
        self.pipeline.add_action(ReadFeedback())


class GetBoardId:
    def get_board_id(self):
        device_info = self.job.device.get("device_info")
        if not device_info:
            return None
        return device_info[0].get("board_id")


class DockerTestSetEnvironment(TestAction, GetBoardId):
    name = "lava-docker-test-set-environment"
    description = "Adds necessary environments variables for docker-test-shell"
    summary = description

    def run(self, connection, max_end_time):
        environment = self.job.parameters.get("environment", {})
        environment["ANDROID_SERIAL"] = self.get_board_id()

        connections = self.job.device.get("commands", {}).get("connections", {})
        for name, command in connections.items():
            connect = command.get("connect")
            tags = command.get("tags", [])
            if connect:
                k = "LAVA_CONNECTION_COMMAND_%s" % name.upper()
                environment[k] = connect
                if "primary" in tags:
                    environment["LAVA_CONNECTION_COMMAND"] = connect

        self.job.parameters["environment"] = environment
        connection = super().run(connection, max_end_time)
        return connection


class DockerTestShell(TestShellAction, GetBoardId):
    name = "lava-docker-test-shell"
    description = "Runs lava-test-shell in a docker container"
    summary = "Runs lava-test-shell in a docker container"

    def run(self, connection, max_end_time):
        # obtain lava overlay
        # start container
        # create USB device mapping to container
        # connect to container, and run lava-test-shell over it
        location = self.get_namespace_data(
            action="test", label="shared", key="location"
        )
        overlay = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        ).strip("/")

        image = self.parameters["docker"]["image"]
        container = "lava-docker-test-shell-%s-%s" % (self.job.job_id, self.level)

        board_id = self.get_board_id()
        add_device_container_mapping(
            job_id=self.job.job_id,
            device_info={"board_id": board_id},
            container=container,
            container_type="docker",
            logging_info=self.get_logging_info(),
        )

        mount_overlay = "--mount=type=bind,source=%s,destination=/%s" % (
            os.path.join(location, overlay),
            overlay,
        )

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            mount_overlay,
            "--interactive",
            "--hostname=lava",
            "--name=%s" % container,
            "--env=PS1=docker-test-shell:$ ",
            image,
            "bash",
            "--norc",
            "-i",
        ]

        cmd = " ".join([shlex.quote(s) for s in docker_cmd])
        self.logger.debug("Starting docker test shell container: %s" % cmd)
        shell = ShellCommand(cmd, self.timeout, logger=self.logger)

        shell_connection = ShellSession(self.job, shell)
        shell_connection.prompt_str = "docker-test-shell:"

        self.__set_connection__(shell_connection)
        super().run(shell_connection, max_end_time)

        # return the original connection untouched
        self.__set_connection__(connection)
        return connection

    def __set_connection__(self, c):
        self.set_namespace_data(
            action="shared",
            label="shared",
            key="connection",
            value=c,
            parameters=self.parameters,
        )
