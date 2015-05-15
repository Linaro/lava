# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os

from lava_dispatcher.pipeline.action import Action


class ExportDeviceEnvironment(Action):
    """
    Exports environment variables found in common data on to the device.
    """

    def __init__(self):
        super(ExportDeviceEnvironment, self).__init__()
        self.name = "export-device-env"
        self.summary = "Exports environment variables action"
        self.description = "Exports environment variables to the device"
        self.env = []

    def validate(self):
        shell_file = self.get_common_data('environment', 'shell_file')
        environment = self.get_common_data('environment', 'env_dict')
        if not environment:
            return
        # Append export commands to the shell init file.
        # Retain quotes into the final shell.
        for key in environment:
            self.env.append("echo export %s=\\'%s\\' >> %s" % (
                key, environment[key], shell_file))

    def run(self, connection, args=None):

        if not connection:
            return

        connection = super(ExportDeviceEnvironment, self).run(connection, args)

        shell_file = self.get_common_data('environment', 'shell_file')

        for line in self.env:
            connection.sendline(line)
        connection.sendline('. %s' % shell_file)

        return connection
