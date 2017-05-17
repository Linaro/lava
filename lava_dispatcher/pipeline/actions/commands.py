# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
    ConfigurationError,
)


class CommandAction(Action):

    compatibility = 1

    def __init__(self):
        super(CommandAction, self).__init__()
        self.name = 'user-command'
        self.description = "execute one of the commands listed by the admin"
        self.summary = "execute commands"
        self.section = "command"
        self.cmd = None
        self.ran = False

    def validate(self):
        super(CommandAction, self).validate()
        cmd_name = self.parameters['name']
        try:
            user_commands = self.job.device['commands']['users']
        except KeyError:
            raise ConfigurationError("Unable to get device.commands.users dictionary")

        try:
            self.cmd = user_commands[cmd_name]
            if not isinstance(self.cmd['do'], str) or \
               not isinstance(self.cmd.get('undo', ""), str):
                raise ConfigurationError("User command \"%s\" is invalid: "
                                         "'do' and 'undo' should be strings" % cmd_name)
            return True
        except KeyError:
            self.errors = "Unknown user command '%s'" % cmd_name
            return False

    def run(self, connection, max_end_time, args=None):
        connection = super(CommandAction, self).run(connection, max_end_time, args)

        self.logger.debug("Running user command '%s'", self.parameters['name'])
        self.ran = True
        self.run_command(self.cmd['do'].split(' '), allow_silent=True)
        return connection

    def cleanup(self, connection):
        if not self.ran:
            self.logger.debug("Skipping %s 'undo' as 'do' was not called", self.name)
            return

        if self.cmd is not None and 'undo' in self.cmd:
            self.logger.debug("Running cleanup for user command '%s'", self.parameters['name'])
            if not isinstance(self.cmd['undo'], str):
                self.logger.error("Unable to run cleanup: 'undo' is not a string")
            else:
                self.run_command(self.cmd['undo'].split(' '), allow_silent=True)
