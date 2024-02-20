# Copyright (C) 2016 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_common.utils import binary_version
from lava_dispatcher.action import Action, JobError, Pipeline
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.strings import substitute
from lava_dispatcher.utils.udev import WaitDeviceBoardID


class PyOCD(Boot):
    @classmethod
    def action(cls):
        return BootPyOCD()

    @classmethod
    def accepts(cls, device, parameters):
        if "pyocd" not in device["actions"]["boot"]["methods"]:
            return False, '"pyocd" was not in the device configuration boot methods'
        if parameters["method"] != "pyocd":
            return False, '"method" was not "pyocd"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class BootPyOCD(RetryAction):
    name = "boot-pyocd-image"
    description = "boot pyocd image with retry"
    summary = "boot pyocd image with retry"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(BootPyOCDRetry())


class BootPyOCDRetry(RetryAction):
    name = "boot-pyocd-image"
    description = "boot pyocd image using the command line interface"
    summary = "boot pyocd image"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        method_params = self.job.device["actions"]["boot"]["methods"]["pyocd"][
            "parameters"
        ]
        if self.job.device.hard_reset_command:
            self.pipeline.add_action(ResetDevice())
            self.pipeline.add_action(WaitDeviceBoardID(self.job.device.get("board_id")))
        if method_params.get("connect_before_flash", False):
            self.pipeline.add_action(ConnectDevice())
        self.pipeline.add_action(FlashPyOCDAction())
        if not method_params.get("connect_before_flash", False):
            self.pipeline.add_action(ConnectDevice())


class FlashPyOCDAction(Action):
    name = "flash-pyocd"
    description = "flash pyocd to boot the image"
    summary = "flash pyocd to boot the image"

    def __init__(self):
        super().__init__()
        self.base_command = []
        self.exec_list = []

    def validate(self):
        super().validate()
        boot = self.job.device["actions"]["boot"]["methods"]["pyocd"]
        pyocd_binary = boot["parameters"]["command"]
        binary = which(pyocd_binary)
        self.logger.info(binary_version(binary, "--version"))
        self.base_command = [pyocd_binary]
        self.base_command.extend(boot["parameters"].get("options", []))
        if self.job.device["board_id"] == "0000000000":
            self.errors = "[PYOCD] board_id unset"
        substitutions = {}
        # '--uid' should be used with 'pyocd flash' for connecting to
        # a specific board. 'pyocd flash --board' doesn't work for
        # selecting board, and the option has been removed since
        # version v0.32.0.
        # '--board' should be used for 'pyocd-flashtool' as '--uid'
        # isn't available for 'pyocd-flashtool'.
        # Different boards require (or work better) with a particular
        # version of pyocd. Due to this, we need to maintain support
        # for both 'pyocd flash' and 'pyocd-flashtool' for the foreseeable
        # future.
        connecting_option = "--uid"
        if pyocd_binary.startswith("pyocd-flashtool"):
            connecting_option = "--board"
        self.base_command.extend([connecting_option, self.job.device["board_id"]])
        for action in self.get_namespace_keys("download-action"):
            pyocd_full_command = []
            image_arg = self.get_namespace_data(
                action="download-action", label=action, key="image_arg"
            )
            action_arg = self.get_namespace_data(
                action="download-action", label=action, key="file"
            )
            if image_arg:
                if not isinstance(image_arg, str):
                    self.errors = "image_arg is not a string (try quoting it)"
                    continue
                substitutions["{%s}" % action] = action_arg
                pyocd_full_command.extend(self.base_command)
                pyocd_full_command.extend(substitute([image_arg], substitutions))
                self.exec_list.append(pyocd_full_command)
            else:
                pyocd_full_command.extend(self.base_command)
                pyocd_full_command.extend([action_arg])
                self.exec_list.append(pyocd_full_command)
        if not self.exec_list:
            self.errors = "No PyOCD command to execute"

        pre_os_command = self.job.device.pre_os_command
        if pre_os_command:
            self.exec_list.append(pre_os_command.split(" "))

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        for pyocd_command in self.exec_list:
            pyocd = " ".join(pyocd_command)
            self.logger.info("PyOCD command: %s", pyocd)
            if not self.run_command(pyocd.split(" "), allow_silent=True):
                raise JobError("%s command failed" % (pyocd.split(" ")))
        return connection
