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

from lava_dispatcher.pipeline.action import Action, Timeout
from lava_dispatcher.pipeline.connection import Connection
from lava_dispatcher.pipeline.shell import ShellCommand


class ConnectToSerial(Action):

    def __init__(self):
        super(ConnectToSerial, self).__init__()
        self.name = "connect-to-serial"
        self.description = "connect to the serial port of the device"
        self.summary = "connecting to serial"
        self.timeout = Timeout(self.name)

    def validate(self):
        if 'connection_command' not in self.job.device.parameters:
            raise RuntimeError("%s does not have a connection_command parameter" % self.job.device.parameters['hostname'])

    def run(self, connection, args=None):
        telnet = ShellCommand(self.job.device.parameters['connection_command'], self.timeout)
        return Connection(self.job, telnet)
