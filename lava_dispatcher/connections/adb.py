# Copyright (C) 2018 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Action, JobError
from lava_dispatcher.shell import ShellCommand, ShellSession
from lava_dispatcher.utils.shell import which


class ConnectAdb(Action):
    """
    Class to make an adb shell connection to the device.
    """

    name = "connect-adb"
    summary = "run connection command"
    description = "connect via adb shell to the device"

    session_class = ShellSession
    shell_class = ShellCommand

    def validate(self):
        if "adb" not in self.job.device["actions"]["boot"]["methods"]:
            return
        if "adb_serial_number" not in self.job.device:
            self.errors = "device adb serial number missing"
        if "adb" not in self.job.device["actions"]["boot"]["connections"]:
            self.errors = "Device not configured to support adb connection."
        super().validate()
        which("adb")

    def run(self, connection, max_end_time):
        connection = self.get_namespace_data(
            action="shared", label="shared", key="connection", deepcopy=False
        )
        if connection:
            return connection
        adb_serial_number = self.job.device["adb_serial_number"]
        # start the adb daemon
        adb_cmd = ["adb", "start-server"]
        command_output = self.run_command(adb_cmd, allow_fail=True)
        if command_output and "successfully" in command_output.lower():
            self.logger.debug("adb daemon started: %s", command_output)
        # wait for adb device before connecting to adb shell
        adb_cmd = ["adb", "-s", adb_serial_number, "wait-for-device"]
        self.run_command(adb_cmd)
        self.logger.debug("%s: Waiting for device", adb_serial_number)

        cmd = f"adb -s {adb_serial_number} shell"
        self.logger.info("%s Connecting to device using '%s'", self.name, cmd)
        # ShellCommand executes the connection command
        shell = self.shell_class(
            "%s\n" % cmd,
            self.timeout,
            logger=self.logger,
            window=self.job.device.get_constant("spawn_maxread"),
        )
        if shell.exitstatus:
            raise JobError(
                "%s command exited %d: %s" % (cmd, shell.exitstatus, shell.readlines())
            )
        # ShellSession monitors the pexpect
        connection = self.session_class(self.job, shell)
        connection.connected = True
        connection = super().run(connection, max_end_time)
        connection.prompt_str = self.parameters["prompts"]
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection
