# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import pathlib
import shlex

from lava_common.constants import LAVA_DOWNLOADS
from lava_common.exceptions import LAVATimeoutError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.overlay import CreateOverlay
from lava_dispatcher.actions.test.multinode import MultinodeMixin
from lava_dispatcher.actions.test.shell import TestShellAction
from lava_dispatcher.logical import LavaTest
from lava_dispatcher.power import ReadFeedback
from lava_dispatcher.shell import ShellCommand, ShellSession
from lava_dispatcher.utils.docker import DockerRun
from lava_dispatcher.utils.udev import get_udev_devices
from lava_dispatcher_host.action import DeviceContainerMappingMixin


class DockerTest(LavaTest):
    """
    DockerTest Strategy object
    """

    priority = 10

    @classmethod
    def action(cls, parameters):
        return DockerTestAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "definition" in parameters or "definitions" in parameters:
            if "docker" in parameters:
                return True, "accepted"
        return False, "docker or definition(s) not in parameters"

    @classmethod
    def needs_deployment_data(cls, parameters):
        return False

    @classmethod
    def needs_overlay(cls, parameters):
        return True

    @classmethod
    def has_shell(cls, parameters):
        return True


class GetBoardId:
    @property
    def device_info(self):
        return self.job.device.get("device_info")

    def get_board_id(self):
        device_info = self.device_info
        if not device_info:
            return None
        return device_info[0].get("board_id")


class DockerTestAction(Action, GetBoardId):
    name = "lava-docker-test"
    description = "Runs tests in a docker container"
    summary = "Runs tests in a docker container, with the DUT available via adb/fastboot over USB"
    timeout_exception = LAVATimeoutError

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(DockerTestSetEnvironment())
        self.pipeline.add_action(CreateOverlay())
        if "role" in parameters:
            self.pipeline.add_action(MultinodeDockerTestShell())
        else:
            self.pipeline.add_action(DockerTestShell())
        self.pipeline.add_action(ReadFeedback())


class DockerTestSetEnvironment(Action, GetBoardId):
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

        power_commands = ["hard_reset", "power_on", "power_off"]
        for c in power_commands:
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

        docker_method_conf = (
            self.job.device["actions"]
            .get("test", {})
            .get("methods", {})
            .get("docker", {})
        )

        # Preprocess docker option list, to better support partial
        # overriding of them via device dict:
        # 1. Filter out None, to make it easier to template
        # YAML syntactic lists with Jinja2:
        # '- {{ some_opt_from_device_dict }}'
        # (if not default, will be set to None).
        # 2. Flatten sublists, `- ['--opt1', '--opt2']`.
        def preproc_opts(opts):
            res = []
            for o in opts:
                if o is None:
                    continue
                elif isinstance(o, list):
                    res += o
                else:
                    res.append(o)
            return res

        if "global_options" in docker_method_conf:
            docker.add_docker_options(
                *preproc_opts(docker_method_conf["global_options"])
            )
        if "options" in docker_method_conf:
            docker.add_docker_run_options(*preproc_opts(docker_method_conf["options"]))

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

        shell_connection = ShellSession(self.job, shell)
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
        for dev in devices:
            if not os.path.islink(dev):
                self.trigger_share_device_with_container(dev)

        for dev in devices:
            docker.wait_file(dev)

        try:
            super().run(shell_connection, max_end_time)
        finally:
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
