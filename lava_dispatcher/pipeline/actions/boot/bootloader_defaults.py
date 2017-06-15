# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Birch <dean.birch@linaro.org>
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

from lava_dispatcher.pipeline.action import (
    Action,
    InfrastructureError,
    Timeout)
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.utils.constants import (
    LINE_SEPARATOR,
    BOOTLOADER_DEFAULT_CMD_TIMEOUT
)


class BootloaderCommandsAction(Action):
    """
    Send the boot commands to the bootloader
    """
    def __init__(self):
        super(BootloaderCommandsAction, self).__init__()
        self.name = "bootloader-commands"
        self.description = "send commands to bootloader"
        self.summary = "interactive bootloader"
        self.params = None
        self.timeout = Timeout(self.name, BOOTLOADER_DEFAULT_CMD_TIMEOUT)
        self.method = ""

    def validate(self):
        super(BootloaderCommandsAction, self).validate()
        self.method = self.parameters['method']
        self.params = self.job.device['actions']['boot']['methods'][self.method]['parameters']

    def line_separator(self):
        return LINE_SEPARATOR

    def run(self, connection, max_end_time, args=None):
        if not connection:
            self.errors = "%s started without a connection already in use" % self.name
        connection = super(BootloaderCommandsAction, self).run(connection, max_end_time, args)
        connection.raw_connection.linesep = self.line_separator()
        connection.prompt_str = self.params['bootloader_prompt']
        self.logger.debug("Changing prompt to start interaction: %s", connection.prompt_str)
        self.wait(connection)
        i = 1
        commands = self.get_namespace_data(action='bootloader-overlay', label=self.method, key='commands')

        for line in commands:
            connection.sendline(line, delay=self.character_delay)
            if i != (len(commands)):
                self.wait(connection)
                i += 1

        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        # allow for auto_login
        if self.parameters.get('prompts', None):
            connection.prompt_str = [
                self.params.get('boot_message',
                                self.job.device.get_constant('boot-message')),
                self.job.device.get_constant('cpu-reset-message')
            ]
            self.logger.debug("Changing prompt to boot_message %s",
                              connection.prompt_str)
            index = self.wait(connection)
            if connection.prompt_str[index] == self.job.device.get_constant('cpu-reset-message'):
                self.logger.error("Bootloader reset detected: Bootloader "
                                  "failed to load the required file into "
                                  "memory correctly so the bootloader reset "
                                  "the CPU.")
                raise InfrastructureError("Bootloader reset detected")
        return connection


class BootloaderDefaultsRetry(BootAction):
    pass
