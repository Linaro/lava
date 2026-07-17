# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.exceptions import ConfigurationError, InfrastructureError
from lava_dispatcher.action import Action

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


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
        "usbg_ms_commands_disable",
        "stop_test_services",
    ]

    def __init__(self, job: Job):
        super().__init__(job)
        self.section = "command"
        self.cmd = None
        self.ran = False

    def validate(self):
        super().validate()
        cmd_name = self.parameters["name"]

        if cmd_name in self.builtin_commands:
            if cmd_name == "usbg_ms_commands_disable":
                try:
                    cmd = self.job.device["actions"]["deploy"]["methods"]["usbg-ms"][
                        "disable"
                    ]
                    if isinstance(cmd, list):
                        cmd = " ".join(cmd)
                    self.cmd = {"do": cmd}
                except KeyError:
                    self.errors_add(
                        "Command 'usbg_ms_commands.disable' not defined for this device"
                    )
                return
            if cmd_name == "stop_test_services":
                if cmd_list := self.get_namespace_data(
                    action="lava-test-service", label="stop-services", key="cmd-list"
                ):
                    self.cmd = {"do": cmd_list}
                else:
                    self.errors_add(
                        "Command for 'stop_test_services' not found. "
                        "No 'test.services' action defined?"
                    )

                return
            if cmd_name in self.job.device["commands"]:
                self.cmd = {"do": self.job.device["commands"][cmd_name]}
                return

            self.errors_add("Command '%s' not defined for this device" % cmd_name)
            return

        user_commands = self.job.device.get("commands", {}).get("users")
        if not user_commands:
            self.errors_add("Device has no configured user commands")
            return
        try:
            self.cmd = user_commands[cmd_name]
        except KeyError:
            self.errors_add("Unknown user command '%s'" % cmd_name)
            return

        if not self.is_command(self.cmd.get("do")) or (
            "undo" in self.cmd and not self.is_command(self.cmd["undo"])
        ):
            raise ConfigurationError(
                'User command "%s" is invalid: "do" and "undo" should be '
                "non-empty strings or non-empty lists of non-empty strings" % cmd_name
            )

    @staticmethod
    def is_command(cmd) -> bool:
        # An empty command (or a list with an empty element) would silently run
        # nothing, so reject it here rather than at run time.
        if isinstance(cmd, str):
            return bool(cmd)
        if not isinstance(cmd, list):
            return False
        return bool(cmd) and all(isinstance(c, str) and c for c in cmd)

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
            cmd = self.cmd["undo"]
            if not isinstance(cmd, list):
                cmd = [cmd]
            for c in cmd:
                self.run_cmd(c)
