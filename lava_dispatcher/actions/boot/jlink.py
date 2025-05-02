# Copyright (C) 2019 Linaro Limited
# Copyright 2024 NXP
#
# Author: Andrei Gansari <andrei.gansari@linaro.org>
#         Andy Sabathier <andy.sabathier@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import re
import shlex
import subprocess
from typing import TYPE_CHECKING

from lava_dispatcher.action import Action, JobError, Pipeline
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.udev import WaitDeviceBoardID

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class BootJLinkRetry(RetryAction):
    name = "boot-jlink-image"
    description = "boot jlink image using the command line interface"
    summary = "boot jlink image"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.job.device.hard_reset_command:
            self.pipeline.add_action(ResetDevice(self.job))
            self.pipeline.add_action(
                WaitDeviceBoardID(self.job, self.job.device.get("board_id"))
            )
        self.pipeline.add_action(ConnectDevice(self.job))
        self.pipeline.add_action(FlashJLinkAction(self.job))


class FlashJLinkAction(Action):
    name = "flash-jlink"
    description = "flash jlink to boot the image"
    summary = "flash jlink to boot the image"

    def __init__(self, job: Job):
        super().__init__(job)
        self.base_command = []
        self.path = []

    def validate(self):
        super().validate()
        params = self.job.device["actions"]["boot"]["methods"]["jlink"]["parameters"]
        jlink_binary = params["command"]
        # check version of jlink
        self.version(jlink_binary)
        # prepare jlink command
        options = params.get("options", [])
        self.command_maker(jlink_binary, options, params)

    def version(self, binary):
        try:
            # check version of Jlink
            cmd_output = subprocess.run([binary, "-v"], capture_output=True, text=True)
            if not cmd_output.stdout:
                raise JobError("command JLinkExe -v doesn't return an output")
            # parse cmd_output and print in logger info
            temp = re.search("J-Link Commander (.+?) \\(Compiled", cmd_output.stdout)
            if temp:
                # print the version of jlink
                self.logger.info(f"Jlink version : {temp.group(1)}")
            else:
                # Does not produce an error in case of the jlink version display changes
                self.logger.info("Jlink version unknown")
        except FileNotFoundError:
            raise JobError("JLink is not installed")

    def command_maker(self, jlink_binary, options, params):
        ### create JlinkExe command and add it to a namespace ###
        self.base_command = [jlink_binary]
        processor_name = params.get("processor")
        if processor_name:
            self.base_command.append("-device")
            supported_core_types = params.get("supported_core_types")
            if supported_core_types:
                if isinstance(supported_core_types, list):
                    # If a specific core type is provided in parameters, modify the option accordingly
                    # Get coretype if exist else get supported_core_types[0]
                    coretype = self.parameters.get("coretype", supported_core_types[0])
                    if coretype not in supported_core_types:
                        self.errors = f"[coretype = {coretype}] Not supported by current device (supported_core_types = {supported_core_types})."
                    device_name = f"{processor_name}_{coretype}"
                    self.base_command.append(device_name)
                else:
                    self.errors = f"Invalid device-type definition, supported_core_types parameter needs to be a list."
            else:
                self.base_command.append(processor_name)
        else:
            self.errors = "Invalid device-type definition, missing processor parameter"

        for option in options:
            self.base_command.extend(shlex.split(option))
        self.base_command.extend(["-autoconnect", "1", "-NoGui", "1"])
        self.path = self.mkdtemp()
        # set a namespace for the jlink path script which is used to flash
        self.jlink_script = os.path.join(self.path, "cmd.jlink")
        self.state.jlink.script_path = self.jlink_script
        self.base_command.extend(["-CommanderScript", self.jlink_script])
        board_id = self.job.device["board_id"]
        if board_id == "0000000000":
            self.errors = "[JLink] board_id unset"
        self.base_command.extend(["-SelectEmuBySN", str(board_id)])
        # Set a namespace for the JlinkExe cmd
        self.state.jlink.cmd = self.base_command

    def create_jlink_script(self, path_jlink_script):
        # Create jlink script
        params = self.job.device["actions"]["boot"]["methods"]["jlink"]["parameters"]
        load_address = params["address"]
        lines = ["r"]  # Reset  the target
        lines.append("h")  # Halt the target
        lines.append("sleep 500")  # Sleep for 0.5s
        # Erase commands (default = erase)
        for cmd in params["erase_command"]:
            lines.append(cmd)
        if "commands" in self.parameters:
            pattern = r"\{(.*?)\}"
            jlink_cmds_script = self.parameters["commands"]
            for cmd in jlink_cmds_script:
                match = re.search(pattern, cmd)
                if match:
                    result = match.group(1)
                    binary_image = self.state.downloads[result].file
                    jlink_command = cmd.replace("{" + result + "}", binary_image)
                    lines.append(jlink_command)
                else:
                    lines.append(cmd)
        else:
            for download in self.state.downloads.values():
                binary_image = download.file
                if binary_image:
                    # Erase and Flash
                    lines.append(f"loadfile {binary_image} 0x{load_address:x}")
                    lines.append(f"verifybin {binary_image} 0x{load_address:x}")
        # Reset commands (default = erase)
        for cmd in params["reset_command"]:
            lines.append(cmd)  # Restart the CPU
        lines.append("qc")
        self.logger.info(lines)
        with open(path_jlink_script, "w") as f:
            f.write("\n".join(lines))

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        path_jlink_script = self.state.jlink.script_path
        jlink_cmd = self.state.jlink.cmd
        self.logger.info(jlink_cmd)
        self.create_jlink_script(path_jlink_script)
        # execute command
        result = self.parsed_command(jlink_cmd)
        flash_check = "Connecting to J-Link via USB...FAILED"
        if flash_check in result:
            raise JobError(flash_check)

        if "prompts" in self.parameters:
            prompt_str = self.parameters["prompts"]
            connection.prompt_str = prompt_str
            self.wait(connection)

        return connection
