# Copyright (C) 2019 Linaro Limited
#
# Author: Andrei Gansari <andrei.gansari@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import re
import shlex
import subprocess

from lava_dispatcher.action import Action, JobError, Pipeline
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.udev import WaitDeviceBoardID


class JLink(Boot):
    @classmethod
    def action(cls):
        return BootJLinkRetry()

    @classmethod
    def accepts(cls, device, parameters):
        if "jlink" not in device["actions"]["boot"]["methods"]:
            return False, '"jlink" was not in the device configuration boot methods'
        if parameters["method"] != "jlink":
            return False, '"method" was not "jlink"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class BootJLinkRetry(RetryAction):
    name = "boot-jlink-image"
    description = "boot jlink image using the command line interface"
    summary = "boot jlink image"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.job.device.hard_reset_command:
            self.pipeline.add_action(ResetDevice())
            self.pipeline.add_action(WaitDeviceBoardID(self.job.device.get("board_id")))
        self.pipeline.add_action(ConnectDevice())
        self.pipeline.add_action(FlashJLinkAction())


class FlashJLinkAction(Action):
    name = "flash-jlink"
    description = "flash jlink to boot the image"
    summary = "flash jlink to boot the image"

    def __init__(self):
        super().__init__()
        self.base_command = []
        self.exec_list = []
        self.fname = []
        self.path = []

    def version(self, binary, command):
        """
        Returns a string with the version of the JLink binary, board's hardware
        and firmware.
        """
        # if binary is not absolute, fail.
        msg = "Unable to retrieve version of %s" % binary
        try:
            with open(self.fname, "w") as f:
                f.write("f\nexit")
            cmd_output = subprocess.check_output(command)
            if not cmd_output:
                raise JobError(cmd_output)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise JobError(msg)

        output_str = cmd_output.decode("utf-8")
        host_ver = "none"
        fw_ver = "none"
        hw_ver = "none"
        temp = re.search("J-Link Commander (.+?) \\(Compiled", output_str)
        if temp:
            host_ver = temp.group(1)

        temp = re.search("Firmware: (.+?) compiled", output_str)
        if temp:
            fw_ver = temp.group(1)

        temp = re.search("Hardware version: (.+?)\n", output_str)
        if temp:
            hw_ver = temp.group(1)

        return "%s, SEGGER J-Link Commander %s, Firmware %s, Hardware %s" % (
            binary,
            host_ver,
            fw_ver,
            hw_ver,
        )

    def validate(self):
        super().validate()
        boot = self.job.device["actions"]["boot"]["methods"]["jlink"]
        jlink_binary = boot["parameters"]["command"]
        load_address = boot["parameters"]["address"]
        self.base_command = [jlink_binary]
        for option in boot["parameters"].get("options", []):
            self.base_command.extend(shlex.split(option))

        self.base_command.extend(["-autoconnect", "1"])
        self.path = self.mkdtemp()
        self.fname = os.path.join(self.path, "cmd.jlink")
        self.base_command.append("-CommanderScript")
        self.base_command.append(self.fname)
        board_id = [self.job.device["board_id"]]
        if board_id == "0000000000":
            self.errors = "[JLink] board_id unset"
        # select the board with the correct serial number
        self.base_command.append("-SelectEmuBySN")
        self.base_command.extend(board_id)
        self.logger.info(self.version(jlink_binary, self.base_command))
        substitutions = {}
        for action in self.get_namespace_keys("download-action"):
            jlink_full_command = []
            image_arg = self.get_namespace_data(
                action="download-action", label=action, key="image_arg"
            )
            action_arg = self.get_namespace_data(
                action="download-action", label=action, key="file"
            )
            binary_image = action_arg

            jlink_full_command.extend(self.base_command)

            lines = ["r"]  # Reset and halt the target
            lines.append("h")  # Reset and halt the target
            lines.append("erase")  # Erase all flash sectors
            lines.append("sleep 500")

            lines.append(f"loadfile {binary_image} 0x{load_address:x}")
            lines.append(f"verifybin {binary_image} 0x{load_address:x}")
            lines.append("r")  # Restart the CPU
            lines.append("qc")  # Close the connection and quit

            self.logger.info("JLink command file: \n" + "\n".join(lines))

            with open(self.fname, "w") as f:
                f.writelines(line + "\n" for line in lines)

            self.exec_list.append(jlink_full_command)
        if not self.exec_list:
            self.errors = "No JLinkExe command to execute"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        for jlink_command in self.exec_list:
            self.run_cmd(jlink_command, error_msg="Unable to flash with JLink")
        return connection
