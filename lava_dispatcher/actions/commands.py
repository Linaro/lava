# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import re
from shlex import join as shlex_join
from shlex import split as shlex_split
from typing import TYPE_CHECKING

from lava_common.exceptions import ConfigurationError, InfrastructureError, JobError
from lava_common.schemas.command import CREATE_SECRET_NAME
from lava_dispatcher.action import Action

if TYPE_CHECKING:
    from lava_dispatcher.job import Job
    from lava_dispatcher.shell import ShellSession


class CommandAction(Action):
    name = "user-command"
    description = "execute one of the commands listed by the admin"
    summary = "execute commands"
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError
    builtin_commands: list[str] = [
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
        self.cmd: dict[str, str | list[str] | list[list[str]]] = {}
        self.ran = False

    def validate(self) -> None:
        super().validate()
        cmd_name = self.parameters["name"]
        # builtin branches return early, so check the name before any of them
        secret_name = self.parameters.get("create_secret", "")
        if secret_name:
            if not re.fullmatch(CREATE_SECRET_NAME, secret_name):
                raise JobError(
                    "create_secret '%s' must be a valid environment variable "
                    "name, not start with LAVA_ and not be PATH" % secret_name
                )

        if cmd_name in self.builtin_commands:
            if cmd_name == "usbg_ms_commands_disable":
                try:
                    cmd: str | list[str] = self.job.device["actions"]["deploy"][
                        "methods"
                    ]["usbg-ms"]["disable"]
                    if isinstance(cmd, list):
                        # flatten to a single command: run() re-splits this with
                        # shlex.split, so quote-join keeps the argv identical
                        cmd = shlex_join(cmd)
                    self.cmd = {"do": cmd}
                    self._check_create_secret()
                except KeyError:
                    self.errors_add(
                        "Command 'usbg_ms_commands.disable' not defined for this device"
                    )
                return
            if cmd_name == "stop_test_services":
                cmd_list: list[list[str]] | None = self.get_namespace_data(
                    action="lava-test-service", label="stop-services", key="cmd-list"
                )
                if cmd_list:
                    self.cmd = {"do": cmd_list}
                    self._check_create_secret()
                else:
                    self.errors_add(
                        "Command for 'stop_test_services' not found. "
                        "No 'test.services' action defined?"
                    )
                return
            if cmd_name in self.job.device["commands"]:
                self.cmd = {"do": self.job.device["commands"][cmd_name]}
                self._check_create_secret()
                return

            self.errors_add("Command '%s' not defined for this device" % cmd_name)
            return

        user_commands: (
            dict[str, dict[str, str | list[str] | list[list[str]]]] | None
        ) = self.job.device.get("commands", {}).get("users")
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

        self._check_create_secret()

    def _check_create_secret(self) -> None:
        # `do` is resolved per branch above, so this runs on every branch
        if self.parameters.get("create_secret") and isinstance(
            self.cmd.get("do"), list
        ):
            raise JobError("create_secret cannot be used with a list of commands")

    @staticmethod
    def is_command(cmd: str | list[str] | list[list[str]] | None) -> bool:
        # An empty command (or a list with an empty element) would silently run
        # nothing, so reject it here rather than at run time.
        if isinstance(cmd, str):
            return bool(cmd)
        if not isinstance(cmd, list):
            return False
        return bool(cmd) and all(isinstance(c, str) and c for c in cmd)

    def run(
        self, connection: ShellSession | None, max_end_time: float | None
    ) -> ShellSession | None:
        connection = super().run(connection, max_end_time)
        secret_name = self.parameters.get("create_secret", "")

        self.logger.info("Running user command '%s'", self.parameters["name"])
        self.ran = True
        cmd = self.cmd["do"]
        if not isinstance(cmd, list):
            cmd = [cmd]
        for c in cmd:
            if secret_name:
                if isinstance(c, str):
                    c = shlex_split(c)
                # parsed_command returns output, but expects a list
                out = self.parsed_command(
                    c, show_output=False, redact_output=True
                ).strip()
                if out:
                    if "\n" in out:
                        raise JobError("create_secret output must be a single line")
                    self.logger.debug(
                        "Creating secret %s (%d bytes)", secret_name, len(out)
                    )
                    # also masks the value in the logs
                    self.job.secrets.add(secret_name, out)
                    # we add job secrets to env in lava-run, also add newly created ones
                    # shortcut: validation only blocks LAVA_*/PATH; a secret
                    # named HOME or IFS still clobbers the job env
                    os.environ[secret_name] = out
                else:
                    self.logger.debug(
                        "create_secret %s: command produced no output, no secret created",
                        secret_name,
                    )
            else:
                self.run_cmd(c)
        return connection

    def cleanup(
        self,
        connection: ShellSession | None,
        max_end_time: float | None = None,
    ) -> None:
        if not self.ran:
            self.logger.debug("Skipping %s 'undo' as 'do' was not called", self.name)
            return

        if "undo" in self.cmd:
            self.logger.info(
                "Running cleanup for user command '%s'", self.parameters["name"]
            )
            cmd = self.cmd["undo"]
            if not isinstance(cmd, list):
                cmd = [cmd]
            for c in cmd:
                self.run_cmd(c)
