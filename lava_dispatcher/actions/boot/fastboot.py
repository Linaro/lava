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
from lava_dispatcher.action import (
    Action,
    InfrastructureError,
    JobError,
    LAVABug,
    Pipeline,
)
from lava_dispatcher.logical import Boot
from lava_dispatcher.actions.boot import (
    BootAction,
    AutoLoginAction,
    OverlayUnpack,
)
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.constants import LAVA_LXC_HOME
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.protocols.lxc import LxcProtocol
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.actions.boot.u_boot import UBootEnterFastbootAction


def _fastboot_sequence_map(sequence):
    """Maps fastboot sequence with corresponding class."""
    sequence_map = {'boot': (FastbootBootAction, None),
                    'reboot': (FastbootRebootAction, None),
                    'no-flash-boot': (FastbootBootAction, None),
                    'auto-login': (AutoLoginAction, None),
                    'overlay-unpack': (OverlayUnpack, None),
                    'shell-session': (ExpectShellSession, None),
                    'export-env': (ExportDeviceEnvironment, None), }
    return sequence_map.get(sequence, (None, None))


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
                return True, 'accepted'
        return False, 'boot "method" was not "fastboot"'


class BootFastbootAction(BootAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the
    connection after boot.
    """
    def __init__(self):
        super(BootFastbootAction, self).__init__()
        self.name = "fastboot-boot"
        self.summary = "fastboot boot"
        self.description = "fastboot boot into the system"

    def validate(self):
        super(BootFastbootAction, self).validate()
        sequences = self.job.device['actions']['boot']['methods'].get(
            'fastboot', [])
        for sequence in sequences:
            if not _fastboot_sequence_map(sequence):
                self.errors = "Unknown boot sequence '%s'" % sequence

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job,
                                          parameters=parameters)
        # Always ensure the device is in fastboot mode before trying to boot.
        # Check if the device has a power command such as HiKey, Dragonboard,
        # etc. against device that doesn't like Nexus, etc.
        if self.job.device.get('fastboot_via_uboot', False):
            self.internal_pipeline.add_action(ConnectDevice())
            self.internal_pipeline.add_action(UBootEnterFastbootAction())
        elif self.job.device.power_command:
            self.force_prompt = True
            self.internal_pipeline.add_action(ConnectDevice())
            self.internal_pipeline.add_action(ResetDevice())
        else:
            self.internal_pipeline.add_action(EnterFastbootAction())

        # Based on the boot sequence defined in the device configuration, add
        # the required pipeline actions.
        sequences = self.job.device['actions']['boot']['methods'].get(
            'fastboot', [])
        for sequence in sequences:
            mapped = _fastboot_sequence_map(sequence)
            if mapped[1]:
                self.internal_pipeline.add_action(
                    mapped[0](device_actions=mapped[1]))
            elif mapped[0]:
                self.internal_pipeline.add_action(mapped[0]())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if 'transfer_overlay' in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())


class WaitFastBootInterrupt(Action):
    """
    Interrupts fastboot to access the next bootloader
    Relies on fastboot-flash-action setting the prompt and string
    from the deployment parameters.
    """

    def __init__(self, type):
        super(WaitFastBootInterrupt, self).__init__()
        self.name = 'wait-fastboot-interrupt'
        self.summary = "watch output and try to interrupt fastboot"
        self.description = "Check for prompt and pass the interrupt string to exit fastboot."
        self.type = type
        self.prompt = None
        self.string = None

    def validate(self):
        super(WaitFastBootInterrupt, self).validate()
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device['fastboot_serial_number'] == '0000000000':
            self.errors = "device fastboot serial number unset"
        if 'fastboot_options' not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device['fastboot_options'], list):
            self.errors = "device fastboot options is not a list"
        device_methods = self.job.device['actions']['deploy']['methods']
        if isinstance(device_methods.get('fastboot'), dict):
            self.prompt = device_methods['fastboot'].get('interrupt_prompt')
            self.string = device_methods['fastboot'].get('interrupt_string')
        if not self.prompt or not self.string:
            self.errors = "Missing interrupt configuration for device."

    def run(self, connection, max_end_time, args=None):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super(WaitFastBootInterrupt, self).run(connection, max_end_time, args)
        # device is to be put into a reset state, either by issuing 'reboot' or power-cycle
        connection.prompt_str = self.prompt
        self.logger.debug("Changing prompt to '%s'", connection.prompt_str)
        self.wait(connection)
        self.logger.debug("Sending '%s' to interrupt fastboot.", self.string)
        connection.sendline(self.string)
        return connection


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
        elif self.job.device['fastboot_serial_number'] == '0000000000':
            self.errors = "device fastboot serial number unset"
        if 'fastboot_options' not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device['fastboot_options'], list):
            self.errors = "device fastboot options is not a list"

    def run(self, connection, max_end_time, args=None):
        connection = super(FastbootBootAction, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            raise JobError("Unable to use fastboot")
        self.logger.debug("[%s] lxc name: %s", self.parameters['namespace'],
                          lxc_name)
        serial_number = self.job.device['fastboot_serial_number']
        boot_img = self.get_namespace_data(action='download-action',
                                           label='boot', key='file')
        if not boot_img:
            raise JobError("Boot image not found, unable to boot")
        else:
            boot_img = os.path.join(LAVA_LXC_HOME, os.path.basename(boot_img))
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'boot',
                        boot_img] + self.job.device['fastboot_options']
        command_output = self.run_command(fastboot_cmd, allow_fail=True)
        if command_output and 'booting' not in command_output:
            raise JobError("Unable to boot with fastboot: %s" % command_output)
        else:
            status = [status.strip() for status in command_output.split(
                '\n') if 'finished' in status][0]
            self.results = {'status': status}
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        lxc_active = any([pc for pc in self.job.protocols if pc.name == LxcProtocol.name])
        if self.job.device.pre_os_command and not lxc_active:
            self.logger.info("Running pre OS command.")
            command = self.job.device.pre_os_command
            if not self.run_command(command.split(' '), allow_silent=True):
                raise InfrastructureError("%s failed" % command)
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
        elif self.job.device['fastboot_serial_number'] == '0000000000':
            self.errors = "device fastboot serial number unset"
        if 'fastboot_options' not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device['fastboot_options'], list):
            self.errors = "device fastboot options is not a list"

    def run(self, connection, max_end_time, args=None):
        connection = super(FastbootRebootAction, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            raise JobError("Unable to use fastboot")
        self.logger.debug("[%s] lxc name: %s", self.parameters['namespace'],
                          lxc_name)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_opts = self.job.device['fastboot_options']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot', '-s',
                        serial_number, 'reboot'] + fastboot_opts
        command_output = self.run_command(fastboot_cmd, allow_fail=True)
        if command_output and 'rebooting' not in command_output:
            raise JobError("Unable to fastboot reboot: %s" % command_output)
        else:
            status = [status.strip() for status in command_output.split(
                '\n') if 'finished' in status][0]
            self.results = {'status': status}
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        return connection


class EnterFastbootAction(Action):
    """
    Enters fastboot bootloader.
    """

    def __init__(self):
        super(EnterFastbootAction, self).__init__()
        self.name = "enter-fastboot-action"
        self.description = "enter fastboot bootloader"
        self.summary = "enter fastboot"

    def validate(self):
        super(EnterFastbootAction, self).validate()
        if 'adb_serial_number' not in self.job.device:
            self.errors = "device adb serial number missing"
        elif self.job.device['adb_serial_number'] == '0000000000':
            self.errors = "device adb serial number unset"
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device['fastboot_serial_number'] == '0000000000':
            self.errors = "device fastboot serial number unset"
        if 'fastboot_options' not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device['fastboot_options'], list):
            self.errors = "device fastboot options is not a list"

    def run(self, connection, max_end_time, args=None):
        connection = super(EnterFastbootAction, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            raise JobError("Unable to use fastboot")

        self.logger.debug("[%s] lxc name: %s", self.parameters['namespace'], lxc_name)
        fastboot_serial_number = self.job.device['fastboot_serial_number']

        # Try to enter fastboot mode with adb.
        adb_serial_number = self.job.device['adb_serial_number']
        # start the adb daemon
        adb_cmd = ['lxc-attach', '-n', lxc_name, '--', 'adb', 'start-server']
        command_output = self.run_command(adb_cmd, allow_fail=True)
        if command_output and 'successfully' in command_output:
            self.logger.debug("adb daemon started: %s", command_output)
        adb_cmd = ['lxc-attach', '-n', lxc_name, '--', 'adb', '-s',
                   adb_serial_number, 'devices']
        command_output = self.run_command(adb_cmd, allow_fail=True)
        if command_output and adb_serial_number in command_output:
            self.logger.debug("Device is in adb: %s", command_output)
            adb_cmd = ['lxc-attach', '-n', lxc_name, '--', 'adb',
                       '-s', adb_serial_number, 'reboot-bootloader']
            self.run_command(adb_cmd)
            return connection

        # Enter fastboot mode with fastboot.
        fastboot_opts = self.job.device['fastboot_options']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot', '-s',
                        fastboot_serial_number, 'devices'] + fastboot_opts
        command_output = self.run_command(fastboot_cmd)
        if command_output and fastboot_serial_number in command_output:
            self.logger.debug("Device is in fastboot: %s", command_output)
            fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                            '-s', fastboot_serial_number,
                            'reboot-bootloader'] + fastboot_opts
            command_output = self.run_command(fastboot_cmd)
            if command_output and 'OKAY' not in command_output:
                raise InfrastructureError("Unable to enter fastboot: %s" %
                                          command_output)
            else:
                status = [status.strip() for status in command_output.split(
                    '\n') if 'finished' in status][0]
                self.results = {'status': status}
        return connection
