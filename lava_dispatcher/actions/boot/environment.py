# Copyright (C) 2015-2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Action


class ExportDeviceEnvironment(Action):
    """
    Exports environment variables found in common data on to the device.
    """

    name = "export-device-env"
    description = "Exports environment variables to the device"
    summary = "Exports environment variables action"

    def __init__(self):
        super().__init__()
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
                "echo export %s=\\'%s\\' >> %s" % (key, environment[key], shell_file)
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
            connection.sendline(". %s" % shell_file, delay=self.character_delay)
            connection.wait()

        # Export data generated during run of the Pipeline like NFS settings
        for key in self.job.device["dynamic_data"]:
            connection.sendline(
                "export %s='%s'" % (key, self.job.device["dynamic_data"][key]),
                delay=self.character_delay,
            )
            connection.wait()

        return connection
