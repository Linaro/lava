# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_common.exceptions import ConfigurationError, InfrastructureError
from lava_dispatcher.action import Action


class CommandAction(Action):
    name = "user-command"
    description = "execute one of the commands listed by the admin"
    summary = "execute commands"
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError
    builtin_commands = [
        "pre_power_command",
        "pre_os_command",
        "hard_reset",
        "power_on",
        "power_off",
        "recovery_mode",
        "recovery_exit",
    ]

    def __init__(self):
        super().__init__()
        self.section = "command"
        self.cmd = None
        self.ran = False

    def validate(self):
        super().validate()
        cmd_name = self.parameters["name"]

        if cmd_name in self.builtin_commands:
            if cmd_name in self.job.device["commands"]:
                self.cmd = {"do": self.job.device["commands"][cmd_name]}
                return True
            else:
                self.errors = "Command '%s' not defined for this device" % cmd_name
                return False

        user_commands = self.job.device.get("commands", {}).get("users")
        if not user_commands:
            self.errors = "Device has no configured user commands"
            return False

        try:
            self.cmd = user_commands[cmd_name]
            if not isinstance(self.cmd["do"], str) or not isinstance(
                self.cmd.get("undo", ""), str
            ):
                raise ConfigurationError(
                    'User command "%s" is invalid: '
                    "'do' and 'undo' should be strings" % cmd_name
                )
            return True
        except KeyError:
            self.errors = "Unknown user command '%s'" % cmd_name
            return False

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        self.logger.info("Running user command '%s'", self.parameters["name"])
        self.ran = True
        cmd = self.cmd["do"]
        if not isinstance(cmd, list):
            cmd = [cmd]
        for c in cmd:
            self.run_cmd(c)
        return connection

    def cleanup(self, connection):
        if not self.ran:
            self.logger.debug("Skipping %s 'undo' as 'do' was not called", self.name)
            return

        if self.cmd is not None and "undo" in self.cmd:
            self.logger.info(
                "Running cleanup for user command '%s'", self.parameters["name"]
            )
            self.run_cmd(self.cmd["undo"])
