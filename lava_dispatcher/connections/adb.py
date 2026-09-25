# Copyright (C) 2018 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from lava_dispatcher.action import Action
from lava_dispatcher.shell import ShellSession
from lava_dispatcher.utils.shell import which


class ConnectAdb(Action):
    """
    Class to make an adb shell connection to the device.
    """

    name = "connect-adb"
    summary = "run connection command"
    description = "connect via adb shell to the device"

    session_class = ShellSession

    def validate(self) -> None:
        if "adb" not in self.job.device["actions"]["boot"]["methods"]:
            return
        if "adb_serial_number" not in self.job.device:
            self.errors_add("device adb serial number missing")
        if "adb" not in self.job.device["actions"]["boot"]["connections"]:
            self.errors_add("Device not configured to support adb connection.")
        super().validate()
        which("adb")

    def run(
        self, connection: ShellSession | None, max_end_time: float | None
    ) -> ShellSession | None:
        existing_adb_connection: ShellSession | None = self.get_namespace_data(
            action="shared", label="shared", key="connection", deepcopy=False
        )
        if existing_adb_connection is not None:
            return existing_adb_connection
        adb_serial_number = self.job.device["adb_serial_number"]
        # start the adb daemon
        adb_cmd: list[str] = ["adb", "start-server"]
        command_output = self.run_command(adb_cmd, allow_fail=True)
        if isinstance(command_output, str) and "successfully" in command_output.lower():
            self.logger.debug("adb daemon started: %s", command_output)
        # wait for adb device before connecting to adb shell
        adb_cmd = ["adb", "-s", adb_serial_number, "wait-for-device"]
        self.run_command(adb_cmd)
        self.logger.debug("%s: Waiting for device", adb_serial_number)

        cmd = f"adb -s {adb_serial_number} shell"
        self.logger.info("%s Connecting to device using '%s'", self.name, cmd)
        # ShellSession executes the connection command and monitors the pexpect
        new_adb_connection = ShellSession(
            "%s\n" % cmd,
            self.timeout,
            logger=self.logger,
            window=self.job.device.get_constant("spawn_maxread"),
        )
        new_adb_connection.connected = True
        existing_adb_connection = super().run(new_adb_connection, max_end_time)
        if existing_adb_connection is not None:
            existing_adb_connection.prompt_str = self.parameters["prompts"]
        self.set_namespace_data(
            action="shared",
            label="shared",
            key="connection",
            value=existing_adb_connection,
        )
        return existing_adb_connection
