# Copyright (C) 2019 Linaro Limited
#
# Author: Vincent Wan <vincent.wan@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from lava_common.utils import binary_version
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.strings import substitute
from lava_dispatcher.utils.udev import WaitDeviceBoardID


class OpenOCD(Boot):
    @classmethod
    def action(cls):
        return BootOpenOCDRetry()

    @classmethod
    def accepts(cls, device, parameters):
        if "openocd" not in device["actions"]["boot"]["methods"]:
            return False, '"openocd" was not in the device configuration boot methods'
        if parameters["method"] != "openocd":
            return False, '"method" was not "openocd"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class BootOpenOCDRetry(RetryAction):
    name = "boot-openocd-image"
    description = "boot openocd image using the command line interface"
    summary = "boot openocd image"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.job.device.hard_reset_command:
            self.pipeline.add_action(ResetDevice())
            self.pipeline.add_action(WaitDeviceBoardID(self.job.device.get("board_id")))
        self.pipeline.add_action(ConnectDevice())
        self.pipeline.add_action(FlashOpenOCDAction())


class FlashOpenOCDAction(Action):
    name = "flash-openocd"
    description = "use openocd to flash the image"
    summary = "use openocd to flash the image"

    def __init__(self):
        super().__init__()
        self.base_command = []
        self.exec_list = []

    def validate(self):
        super().validate()
        boot = self.job.device["actions"]["boot"]["methods"]["openocd"]
        openocd_binary = boot["parameters"]["command"]
        binary = which(openocd_binary)
        self.logger.info(
            binary_version(binary, "--version", "Open On-Chip Debugger (.*)")
        )
        self.base_command = [openocd_binary]
        job_cfg_file = ""
        self.logger.info("Board ID: %s", self.job.device["board_id"])

        # Build the substitutions dictionary and set cfg script based on
        # job definition
        substitutions = {}
        for action in self.get_namespace_keys("download-action"):
            filename = self.get_namespace_data(
                action="download-action", label=action, key="file"
            )
            if filename is None:
                self.logger.warning(
                    "Empty value for action='download-action' label='%s' key='file'",
                    action,
                )
                continue
            if action == "openocd_script":
                # if a url for openocd_script is specified in the job
                # definition, use that instead of the default for the device
                # type.
                job_cfg_file = filename
                self.base_command.extend(["-f", job_cfg_file])
            else:
                substitutions["{%s}" % action.upper()] = filename

        if job_cfg_file == "":
            for item in boot["parameters"]["options"].get("file", []):
                self.base_command.extend(["-f", item])

        if "board_selection_cmd" in boot:
            # Add an extra tcl script to select the board to be used
            temp_dir = self.mkdtemp()
            board_selection_cfg = os.path.join(temp_dir, "board_selection.cfg")
            board_select_cmd = boot["board_selection_cmd"]
            with open(board_selection_cfg, "w") as f:
                f.write(board_select_cmd)
            self.base_command.extend(["-f", board_selection_cfg])

        debug = boot["parameters"]["options"]["debug"]
        self.base_command.extend(["-d" + str(debug)])
        for item in boot["parameters"]["options"].get("search", []):
            self.base_command.extend(["-s", item])
        for item in boot["parameters"]["options"].get("command", []):
            self.base_command.extend(["-c", item])

        if self.job.device["board_id"] == "00000000":
            self.errors = "[FLASH_OPENOCD] board_id unset"

        self.base_command = substitute(self.base_command, substitutions)
        self.exec_list.append(self.base_command)
        if not self.exec_list:
            self.errors = "No OpenOCD command to execute"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        for openocd_command in self.exec_list:
            self.run_cmd(openocd_command)
        return connection
