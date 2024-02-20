# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_common.yaml import yaml_safe_dump
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment, RetryAction
from lava_dispatcher.utils.strings import substitute


class FlasherRetryAction(RetryAction):
    name = "deploy-flasher-retry"
    description = "deploy flasher with retry"
    summary = "deploy custom flasher"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(FlasherAction())


class FlasherAction(Action):
    name = "deploy-flasher"
    description = "deploy flasher"
    summary = "deploy custom flasher"

    def __init__(self):
        super().__init__()
        self.commands = []
        self.path = None

    def validate(self):
        super().validate()
        method = self.job.device["actions"]["deploy"]["methods"]["flasher"]
        self.commands = method.get("commands")
        if not isinstance(self.commands, list):
            self.errors = "'commands' should be a list"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)

        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())

        # Download the images
        self.path = self.mkdtemp()
        for image in parameters["images"].keys():
            self.pipeline.add_action(
                DownloaderAction(image, self.path, params=parameters["images"][image])
            )

        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment())

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        # Substitute in the device commands
        substitutions = {}
        for key in self.parameters["images"].keys():
            filename = self.get_namespace_data(
                action="download-action", label=key, key="file"
            )
            filename = filename[len(self.path) + 1 :]
            substitutions["{%s}" % key.upper()] = filename

        # Add power commands
        substitutions["{HARD_RESET_COMMAND}"] = str(self.job.device.hard_reset_command)
        substitutions["{SOFT_REBOOT_COMMAND}"] = str(
            self.job.device.soft_reboot_command
        )
        substitutions["{PRE_OS_COMMAND}"] = str(self.job.device.pre_os_command)
        if self.job.device.pre_os_command is None:
            substitutions["{PRE_OS_COMMAND}"] = ""
        substitutions["{PRE_POWER_COMMAND}"] = str(self.job.device.pre_power_command)
        if self.job.device.pre_power_command is None:
            substitutions["{PRE_POWER_COMMAND}"] = ""
        substitutions["{POWER_ON_COMMAND}"] = str(self.job.device.power_command)
        substitutions["{POWER_OFF_COMMAND}"] = str(
            self.job.device.get("commands", {}).get("power_off", "")
        )

        # Add some device configuration
        substitutions["{DEVICE_INFO}"] = yaml_safe_dump(
            self.job.device.get("device_info", [])
        )
        substitutions["{STATIC_INFO}"] = yaml_safe_dump(
            self.job.device.get("static_info", [])
        )

        # Run the commands
        for cmd in self.commands:
            cmds = substitute([cmd], substitutions)
            self.run_cmd(cmds[0], error_msg="Unable to flash the device", cwd=self.path)

        return connection


class Flasher(Deployment):
    name = "flasher"

    @classmethod
    def action(cls):
        return FlasherRetryAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "flasher" not in device["actions"]["deploy"]["methods"]:
            return False, "'flasher' not in the device configuration deploy methods"
        if parameters["to"] != "flasher":
            return False, '"to" parameter is not "flasher"'
        return True, "accepted"
