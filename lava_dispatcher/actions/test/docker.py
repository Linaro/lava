# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import pathlib
import shlex

from lava_common.constants import LAVA_DOWNLOADS
from lava_common.device_mappings import remove_device_container_mappings
from lava_common.exceptions import LAVATimeoutError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.overlay import CreateOverlay
from lava_dispatcher.actions.test.multinode import MultinodeMixin
from lava_dispatcher.actions.test.shell import TestShellAction
from lava_dispatcher.power import ReadFeedback
from lava_dispatcher.shell import ShellCommand, ShellSession
from lava_dispatcher.utils.containers import DeviceContainerMappingMixin
from lava_dispatcher.utils.docker import DockerRun
from lava_dispatcher.utils.udev import get_udev_devices


class GetBoardId(Action):
    @property
    def device_info(self):
        return self.job.device.get("device_info")

    def get_board_id(self):
        device_info = self.device_info
        if not device_info:
            return None
        return device_info[0].get("board_id")


class DockerTestAction(GetBoardId):
    name = "lava-docker-test"
    description = "Runs tests in a docker container"
    summary = "Runs tests in a docker container, with the DUT available via adb/fastboot over USB"
    timeout_exception = LAVATimeoutError

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(DockerTestSetEnvironment(self.job))
        self.pipeline.add_action(CreateOverlay(self.job))
        if "role" in parameters:
            self.pipeline.add_action(MultinodeDockerTestShell(self.job))
        else:
            self.pipeline.add_action(DockerTestShell(self.job))
        self.pipeline.add_action(ReadFeedback(self.job))


class DockerTestSetEnvironment(GetBoardId):
    name = "lava-docker-test-set-environment"
    description = "Adds necessary environments variables for docker-test-shell"
    summary = description
    timeout_exception = LAVATimeoutError

    def run(self, connection, max_end_time):
        environment = self.job.parameters.get("environment", {})
        environment["ANDROID_SERIAL"] = self.get_board_id()
        environment["LAVA_BOARD_ID"] = self.get_board_id()

        connections = self.job.device.get("commands", {}).get("connections", {})
        for name, command in connections.items():
            connect = command.get("connect")
            tags = command.get("tags", [])
            if connect:
                k = "LAVA_CONNECTION_COMMAND_%s" % name.upper()
                environment[k] = connect
                if "primary" in tags:
                    environment["LAVA_CONNECTION_COMMAND"] = connect

        commands = ["connect", "hard_reset", "power_on", "power_off"]
        for c in commands:
            cmd = self.job.device.get("commands", {}).get(c)
            if cmd:
                if not isinstance(cmd, list):
                    cmd = [cmd]
                cmd = " && ".join(cmd)
                environment["LAVA_" + c.upper() + "_COMMAND"] = cmd

        self.job.parameters["environment"] = environment
        connection = super().run(connection, max_end_time)
        return connection


class DockerTestShell(TestShellAction, GetBoardId, DeviceContainerMappingMixin):
    name = "lava-docker-test-shell"
    description = "Runs lava-test-shell in a docker container"
    summary = "Runs lava-test-shell in a docker container"

    def validate(self):
        super().validate()

        self.test_docker_bind_mounts = self.job.parameters["dispatcher"].get(
            "test_docker_bind_mounts", []
        )
        for bind_mount in self.test_docker_bind_mounts:
            item_num = len(bind_mount)
            if (
                item_num not in (2, 3)
                or (item_num == 3 and bind_mount[2] != "rw")
                or not all(isinstance(item, str) for item in bind_mount)
            ):
                self.errors = (
                    "Invalid bind mount specification in dispatcher configuration: "
                    f"{bind_mount}; "
                    'Use [source,destination], or [source,destination,"rw"]'
                )
                return

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

        container = "lava-docker-test-shell-%s-%s" % (self.job.job_id, self.level)
        prefix = self.job.parameters.get("dispatcher", {}).get("prefix", "")
        if prefix:
            container = "lava-docker-test-shell-%s-%s-%s" % (
                prefix,
                self.job.job_id,
                self.level,
            )

        docker = DockerRun.from_parameters(self.parameters["docker"], self.job)
        docker.prepare(action=self)
        docker.bind_mount(os.path.join(location, overlay), "/" + overlay)

        docker_test_method_conf = (
            self.job.device["actions"]
            .get("test", {})
            .get("methods", {})
            .get("docker", {})
        )
        docker.add_device_docker_method_options(docker_test_method_conf)

        namespace = self.parameters.get(
            "downloads-namespace", self.parameters.get("namespace")
        )
        if namespace:
            downloads_dir = pathlib.Path(self.job.tmp_dir) / "downloads" / namespace
            if downloads_dir.exists():
                docker.bind_mount(downloads_dir, LAVA_DOWNLOADS)

        for bind_mount in self.test_docker_bind_mounts:
            read_only = True if len(bind_mount) == 2 else False
            docker.bind_mount(bind_mount[0], bind_mount[1], read_only)

        docker.interactive()
        docker.tty()
        docker.name(container)
        docker.environment("PS1", "docker-test-shell:$ ")

        docker_cmd = docker.cmdline("bash", "--norc", "-i")

        cmd = " ".join([shlex.quote(s) for s in docker_cmd])
        self.logger.debug("Starting docker test shell container: %s" % cmd)
        shell = ShellCommand(cmd, self.timeout, logger=self.logger)

        shell_connection = ShellSession(shell)
        shell_connection.prompt_str = "docker-test-shell:"
        self.parameters["connection-namespace"] = "docker-test-shell"
        self.set_namespace_data(
            action="shared",
            label="shared",
            key="connection",
            value=shell_connection,
            parameters={"namespace": "docker-test-shell"},
        )

        self.add_device_container_mappings(container, "docker")

        devices = get_udev_devices(
            device_info=self.device_info, logger=self.logger, required=False
        )

        docker.wait(shell)

        # share all the devices as there isn't a 1:1 relationship between
        # the trigger and actual sharing of the devices
        shared_devices: list[str] = []
        for dev in devices:
            if not os.path.islink(dev):
                self.trigger_share_device_with_container(dev)
                shared_devices.append(dev)
            else:
                self.logger.debug(
                    f"Device {dev} is a symlink, skipping sharing with container"
                )

        for dev in shared_devices:
            docker.wait_file(dev)
            self.logger.info(
                f"Shared device {dev} to docker container {docker.__name__}"
            )

        try:
            super().run(shell_connection, max_end_time)
        finally:
            remove_device_container_mappings(prefix + self.job.job_id)
            self.logger.debug("Removed device container mappings")
            # finish the container
            shell_connection.finalise()
            docker.destroy()

        # return the original connection untouched
        self.data.pop("docker-test-shell")
        return connection


class MultinodeDockerTestShell(MultinodeMixin, DockerTestShell):
    name = "lava-multinode-docker-test-shell"
    description = "Runs multinode lava-test-shell in a docker container"
    summary = "Runs multinode lava-test-shell in a docker container"
