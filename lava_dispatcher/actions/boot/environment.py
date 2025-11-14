# Copyright (C) 2015-2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_dispatcher.action import Action

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class ExportDeviceEnvironment(Action):
    """
    Exports environment variables found in common data on to the device.
    """

    name = "export-device-env"
    description = "Exports environment variables to the device"
    summary = "Exports environment variables action"

    def __init__(self, job: Job):
        super().__init__(job)
        self.env = []

    def validate(self):
        super().validate()
        shell_file = self.get_namespace_data(
            action="deploy-device-env", label="environment", key="shell_file"
        )
        environment = self.get_namespace_data(
            action="deploy-device-env", label="environment", key="env_dict"
        )
        if not environment:
            return
        # Append export commands to the shell init file.
        # Retain quotes into the final shell.
        for key in environment:
            self.env.append(
                f"echo export {key}=\\'{environment[key]}\\' >> {shell_file}"
            )

    def run(self, connection, max_end_time):
        if not connection:
            return

        connection = super().run(connection, max_end_time)

        shell_file = self.get_namespace_data(
            action="deploy-device-env", label="environment", key="shell_file"
        )

        for line in self.env:
            connection.sendline(line, delay=self.character_delay)
            connection.wait()

        if shell_file:
            connection.sendline(f". {shell_file}", delay=self.character_delay)
            connection.wait()

        # Export data generated during run of the Pipeline like NFS settings
        for key in self.job.device["dynamic_data"]:
            connection.sendline(
                f"export {key}='{self.job.device['dynamic_data'][key]}'",
                delay=self.character_delay,
            )
            connection.wait()

        return connection
