# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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
)
from lava_dispatcher.pipeline.shell import ShellCommand, ShellSession

# pylint: disable=too-many-public-methods


class ConnectAdb(Action):
    """
    Class to use the device commands to make a adb shell connection to the
    device.
    """
    def __init__(self):
        super(ConnectAdb, self).__init__()
        self.name = "connect-adb"
        self.summary = "run connection command"
        self.description = "use the configured command to connect adb to the device"

    def validate(self):
        super(ConnectAdb, self).validate()
        if 'connect' not in self.job.device['commands']:
            self.errors = "Unable to connect to device %s - missing connect command." % self.job.device.hostname
            return
        if 'prompts' not in self.parameters:
            self.errors = "Unable to identify test image prompts from parameters."
        command = self.job.device['commands']['connect']
        exe = ''
        try:
            exe = command.split(' ')[0]
        except AttributeError:
            self.errors = "Unable to parse the connection command %s" % command
        self.errors = infrastructure_error(exe)

    def run(self, connection, args=None):
        if connection:
            self.logger.debug("Already connected")
            connection.prompt_str = self.parameters['prompts']
            return connection
        command = self.job.device['commands']['connect'][:]  # local copy to retain idempotency.
        self.logger.info("%s Connecting to device using '%s'", self.name, command)
        signal.alarm(0)  # clear the timeouts used without connections.
        # ShellCommand executes the connection command
        shell = ShellCommand("%s\n" % command, self.timeout, logger=self.logger)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (command, shell.exitstatus, shell.readlines()))
        # ShellSession monitors the pexpect
        connection = ShellSession(self.job, shell)
        connection.connected = True
        connection = super(ConnectAdb, self).run(connection, args)
        connection.prompt_str = self.parameters['prompts']
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return connection


class WaitForAdbDevice(Action):
    """
    Waits for device that gets connected using adb.
    """

    def __init__(self):
        super(WaitForAdbDevice, self).__init__()
        self.name = "wait-for-adb-device"
        self.summary = "Waits for adb device"
        self.description = "Waits for availability of adb device"
        self.prompts = []

    def validate(self):
        super(WaitForAdbDevice, self).validate()
        if 'serial_number' not in self.job.device:
            self.errors = "device serial number missing"
            if self.job.device['serial_number'] == '0000000000':
                self.errors = "device serial number unset"

    def run(self, connection, args=None):
        connection = super(WaitForAdbDevice, self).run(connection, args)
        serial_number = self.job.device['serial_number']
        adb_cmd = ['adb', '-s', serial_number, 'wait-for-device']
        self.run_command(adb_cmd)
        self.logger.debug("%s: Waiting for device", serial_number)
        return connection


class WaitForFastbootDevice(Action):
    """
    Waits for device that gets connected using fastboot.
    """

    def __init__(self):
        super(WaitForFastbootDevice, self).__init__()
        self.name = "wait-for-fastboot-device"
        self.summary = "Waits for fastboot device"
        self.description = "Waits for availability of fastboot device"
        self.prompts = []

    def validate(self):
        super(WaitForAdbDevice, self).validate()
        if 'serial_number' not in self.job.device:
            self.errors = "device serial number missing"
            if self.job.device['serial_number'] == '0000000000':
                self.errors = "device serial number unset"

    def run(self, connection, args=None):
        connection = super(WaitForFastbootDevice, self).run(connection, args)
        serial_number = self.job.device['serial_number']
        fastboot_cmd = ['fastboot', '-s', serial_number, 'wait-for-device']
        self.run_command(fastboot_cmd)
        self.logger.debug("%s: Waiting for device", serial_number)
        return connection
