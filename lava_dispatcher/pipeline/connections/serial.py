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

import signal
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.action import (
    Action,
    JobError,
    TestError,
)
from lava_dispatcher.pipeline.shell import ShellCommand, ShellSession

# pylint: disable=too-many-public-methods


class ConnectDevice(Action):
    """
    General purpose class to use the device commands to
    make a serial connection to the device. e.g. using ser2net
    """
    def __init__(self):
        super(ConnectDevice, self).__init__()
        self.name = "connect-device"
        self.summary = "run connection command"
        self.description = "use the configured command to connect serial to the device"

    def validate(self):
        super(ConnectDevice, self).validate()
        if 'connect' not in self.job.device['commands']:
            self.errors = "Unable to connect to device %s - missing connect command." % self.job.device.hostname
            return
        if 'test_image_prompts' not in self.job.device:
            self.errors = "Unable to identify test image prompts from device configuration."
        command = self.job.device['commands']['connect']
        exe = ''
        try:
            exe = command.split(' ')[0]
        except AttributeError:
            self.errors = "Unable to parse the connection command %s" % command
        self.errors = infrastructure_error(exe)
        # FIXME: this improves speed but relies on using ser2net
        # self.job.device['test_image_prompts'].append('ser2net port')

    def run(self, connection, args=None):
        if connection:
            self.logger.debug("Already connected")
            connection.prompt_str = self.job.device['test_image_prompts']
            return connection
        command = self.job.device['commands']['connect'][:]  # local copy to retain idempotency.
        self.logger.info("%s Connecting to device using '%s'", self.name, command)
        signal.alarm(0)  # clear the timeouts used without connections.
        # ShellCommand executes the connection command
        shell = ShellCommand("%s\n" % command, self.timeout)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (command, shell.exitstatus, shell.readlines()))
        # ShellSession monitors the pexpect
        connection = ShellSession(self.job, shell)
        connection.connected = True
        connection = super(ConnectDevice, self).run(connection, args)
        # append ser2net port to the prompt_str
        # FIXME: this improves speed but relies on using ser2net
        connection.prompt_str = self.job.device['test_image_prompts'].append('ser2net port')
        return connection
        # # if the board is running, wait for a prompt - if not, skip.
        # if self.job.device.power_state is 'off':
        #     return connection
        # try:
        #     self.logger.debug("power_state is on")
        #     connection.sendline('echo echo')
        #     self.wait(connection)
        # except TestError:
        #     self.errors = "%s wait expired" % self.name
        # self.logger.debug("matched %s", connection.match)
        # return connection
