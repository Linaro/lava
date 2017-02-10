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


import os
from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    JobError,
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import (
    BootAction,
    AutoLoginAction,
    WaitUSBDeviceAction,
)
from lava_dispatcher.pipeline.actions.deploy.lxc import LxcAddDeviceAction
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.protocols.lxc import LxcProtocol
from lava_dispatcher.pipeline.shell import ExpectShellSession


class BootFastboot(Boot):
    """
    Expects fastboot bootloader, and boots.
    """
    compatibility = 1

    def __init__(self, parent, parameters):
        super(BootFastboot, self).__init__(parent)
        self.action = BootFastbootAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' in parameters:
            if parameters['method'] == 'fastboot':
                return True
        return False


class BootFastbootAction(BootAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the
    connection after boot.
    """
    def __init__(self):
        super(BootFastbootAction, self).__init__()
        self.name = "fastboot_boot"
        self.summary = "fastboot boot"
        self.description = "fastboot boot into the system"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.job.device.get('fastboot_via_uboot', False):
            self.internal_pipeline.add_action(FastbootRebootAction())
            self.internal_pipeline.add_action(WaitUSBDeviceAction(
                device_actions=['add']))
        else:
            self.internal_pipeline.add_action(FastbootBootAction())
            # Check if the device has a power command such as HiKey,
            # Dragonboard, etc. against device that doesn't like Nexus, etc.
            if self.job.device.power_command:
                self.internal_pipeline.add_action(WaitUSBDeviceAction(
                    device_actions=['add', 'remove']))
            else:
                self.internal_pipeline.add_action(WaitUSBDeviceAction(
                    device_actions=['add']))
        self.internal_pipeline.add_action(LxcAddDeviceAction())
        if self.job.device.power_command:
            self.internal_pipeline.add_action(AutoLoginAction())
            self.internal_pipeline.add_action(ExpectShellSession())
            self.internal_pipeline.add_action(ExportDeviceEnvironment())


class FastbootBootAction(Action):
    """
    This action calls fastboot to boot into the system.
    """

    def __init__(self):
        super(FastbootBootAction, self).__init__()
        self.name = "boot-fastboot"
        self.summary = "attempt to fastboot boot"
        self.description = "fastboot boot into system"

    def validate(self):
        super(FastbootBootAction, self).validate()
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, max_end_time, args=None):
        connection = super(FastbootBootAction, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            self.errors = "Unable to use fastboot"
            return connection
        self.logger.debug("[%s] lxc name: %s", self.parameters['namespace'],
                          lxc_name)
        serial_number = self.job.device['fastboot_serial_number']
        boot_img = self.get_namespace_data(action='download_action',
                                           label='boot', key='file')
        if not boot_img:
            raise JobError("Boot image not found, unable to boot")
        else:
            boot_img = os.path.join('/', os.path.basename(boot_img))
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'boot', boot_img]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'booting' not in command_output:
            raise JobError("Unable to boot with fastboot: %s" % command_output)
        else:
            status = [status.strip() for status in command_output.split(
                '\n') if 'finished' in status][0]
            self.results = {'status': status}
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        return connection


class FastbootRebootAction(Action):
    """
    This action calls fastboot to reboot into the system.
    """

    def __init__(self):
        super(FastbootRebootAction, self).__init__()
        self.name = "fastboot-reboot"
        self.summary = "attempt to fastboot reboot"
        self.description = "fastboot reboot into system"

    def validate(self):
        super(FastbootRebootAction, self).validate()
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, max_end_time, args=None):
        connection = super(FastbootRebootAction, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            self.errors = "Unable to use fastboot"
            return connection
        self.logger.debug("[%s] lxc name: %s", self.parameters['namespace'],
                          lxc_name)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'reboot']
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'rebooting' not in command_output:
            raise JobError("Unable to fastboot reboot: %s" % command_output)
        else:
            status = [status.strip() for status in command_output.split(
                '\n') if 'finished' in status][0]
            self.results = {'status': status}
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        return connection
