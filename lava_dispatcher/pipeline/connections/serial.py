# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.action import (
    Action,
    JobError,
)
from lava_dispatcher.pipeline.shell import ShellCommand, ShellSession

# pylint: disable=too-many-public-methods


class ConnectDevice(Action):
    """
    General purpose class to use the device commands to
    make a serial connection to the device. e.g. using ser2net
    Inherit from this class and change the session_class and/or shell_class for different behaviour.
    """

    def __init__(self):
        super(ConnectDevice, self).__init__()
        self.name = "connect-device"
        self.summary = "run connection command"
        self.description = "use the configured command to connect serial to the device"
        self.session_class = ShellSession  # wraps the pexpect and provides prompt_str access
        self.shell_class = ShellCommand  # runs the command to initiate the connection

    def validate(self):
        super(ConnectDevice, self).validate()
        if 'connect' not in self.job.device['commands']:
            self.errors = "Unable to connect to device %s - missing connect command." % self.job.device.hostname
            return
        command = self.job.device['commands']['connect']
        exe = ''
        try:
            exe = command.split(' ')[0]
        except AttributeError:
            self.errors = "Unable to parse the connection command %s" % command
        self.errors = infrastructure_error(exe)

    def run(self, connection, max_end_time, args=None):
        connection_namespace = self.parameters.get('connection-namespace', None)
        parameters = None
        if connection_namespace:
            parameters = {"namespace": connection_namespace}
        connection = self.get_namespace_data(
            action='shared', label='shared', key='connection', deepcopy=False, parameters=parameters)
        if connection:
            self.logger.debug("Already connected")
            return connection
        elif connection_namespace:
            self.logger.warning("connection_namespace provided but no connection found. "
                                "Please ensure that this parameter is correctly set to existing namespace.")

        command = self.job.device['commands']['connect'][:]  # local copy to retain idempotency.
        self.logger.info("%s Connecting to device using '%s'", self.name, command)
        # ShellCommand executes the connection command
        shell = self.shell_class("%s\n" % command, self.timeout, logger=self.logger)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (command, shell.exitstatus, shell.readlines()))
        # ShellSession monitors the pexpect
        connection = self.session_class(self.job, shell)
        connection.connected = True
        connection = super(ConnectDevice, self).run(connection, max_end_time, args)
        if not connection.prompt_str:
            connection.prompt_str = [self.job.device.get_constant(
                'default-shell-prompt')]
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        return connection
