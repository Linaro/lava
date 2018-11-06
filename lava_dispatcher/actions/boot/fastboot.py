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
from lava_dispatcher.action import Action, Pipeline
from lava_common.exceptions import InfrastructureError, JobError, LAVABug
from lava_dispatcher.logical import Boot
from lava_dispatcher.actions.boot import (
    BootAction,
    AutoLoginAction,
    OverlayUnpack,
    AdbOverlayUnpack,
)
from lava_dispatcher.power import ResetDevice, PreOs
from lava_common.constants import LAVA_LXC_HOME
from lava_dispatcher.utils.lxc import is_lxc_requested, lxc_cmd_prefix
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.connections.adb import ConnectAdb
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
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
        super().__init__(parent)
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


class BootFastbootCommands(Action):

    name = "fastboot-boot-commands"
    description = "Run custom fastboot commands before boot"
    summary = "Run fastboot boot commands"

    def run(self, connection, max_end_time):
        serial_number = self.job.device['fastboot_serial_number']
        self.logger.info("Running custom fastboot boot commands....")
        for command in self.parameters.get("commands"):
            pre_cmd = (
                lxc_cmd_prefix(self.job)
                + ["fastboot", "-s", serial_number, command]
                + self.job.device["fastboot_options"]
            )
            self.run_command(pre_cmd)


class BootFastbootAction(BootAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the
    connection after boot.
    """

    name = "fastboot-boot"
    description = "fastboot boot into the system"
    summary = "fastboot boot"

    def validate(self):
        super().validate()
        sequences = self.job.device['actions']['boot']['methods'].get(
            'fastboot', [])
        if sequences is not None:
            for sequence in sequences:
                if not _fastboot_sequence_map(sequence):
                    self.errors = "Unknown boot sequence '%s'" % sequence
        else:
            self.errors = "fastboot_sequence undefined"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job,
                                          parameters=parameters)

        if parameters.get("commands"):
            self.internal_pipeline.add_action(BootFastbootCommands())

        # Always ensure the device is in fastboot mode before trying to boot.
        # Check if the device has a power command such as HiKey, Dragonboard,
        # etc. against device that doesn't like Nexus, etc.
        if self.job.device.get('fastboot_via_uboot', False):
            self.internal_pipeline.add_action(ConnectDevice())
            self.internal_pipeline.add_action(UBootEnterFastbootAction())
        elif self.job.device.hard_reset_command:
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
        if self.job.device.hard_reset_command:
            if not is_lxc_requested(self.job):
                self.internal_pipeline.add_action(PreOs())
            if self.has_prompts(parameters):
                self.internal_pipeline.add_action(AutoLoginAction())
                if self.test_has_shell(parameters):
                    self.internal_pipeline.add_action(ExpectShellSession())
                    if 'transfer_overlay' in parameters:
                        self.internal_pipeline.add_action(OverlayUnpack())
                    self.internal_pipeline.add_action(ExportDeviceEnvironment())
        else:
            if not is_lxc_requested(self.job):
                self.internal_pipeline.add_action(ConnectAdb())
                self.internal_pipeline.add_action(AdbOverlayUnpack())


class WaitFastBootInterrupt(Action):
    """
    Interrupts fastboot to access the next bootloader
    Relies on fastboot-flash-action setting the prompt and string
    from the deployment parameters.
    """

    name = 'wait-fastboot-interrupt'
    description = "Check for prompt and pass the interrupt string to exit fastboot."
    summary = "watch output and try to interrupt fastboot"

    def __init__(self, itype):
        super().__init__()
        self.type = itype
        self.prompt = None
        self.string = None

    def validate(self):
        super().validate()
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

    def run(self, connection, max_end_time):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super().run(connection, max_end_time)
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

    name = "boot-fastboot"
    description = "fastboot boot into system"
    summary = "attempt to fastboot boot"

    def validate(self):
        super().validate()
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device['fastboot_serial_number'] == '0000000000':
            self.errors = "device fastboot serial number unset"
        if 'fastboot_options' not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device['fastboot_options'], list):
            self.errors = "device fastboot options is not a list"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        lxc_name = is_lxc_requested(self.job)
        serial_number = self.job.device['fastboot_serial_number']
        boot_img = self.get_namespace_data(action='download-action',
                                           label='boot', key='file')
        if not boot_img:
            raise JobError("Boot image not found, unable to boot")
        else:
            if lxc_name:
                boot_img = os.path.join(LAVA_LXC_HOME,
                                        os.path.basename(boot_img))
        fastboot_cmd = lxc_cmd_prefix(self.job) + [
            'fastboot', '-s', serial_number, 'boot', boot_img
        ] + self.job.device['fastboot_options']
        command_output = self.run_command(fastboot_cmd, allow_fail=True)
        if command_output and 'booting' not in command_output:
            raise JobError("Unable to boot with fastboot: %s" % command_output)
        else:
            status = [status.strip() for status in command_output.split(
                '\n') if 'finished' in status][0]
            self.results = {'status': status}
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        return connection


class FastbootRebootAction(Action):
    """
    This action calls fastboot to reboot into the system.
    """

    name = "fastboot-reboot"
    description = "fastboot reboot into system"
    summary = "attempt to fastboot reboot"

    def validate(self):
        super().validate()
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device['fastboot_serial_number'] == '0000000000':
            self.errors = "device fastboot serial number unset"
        if 'fastboot_options' not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device['fastboot_options'], list):
            self.errors = "device fastboot options is not a list"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_opts = self.job.device['fastboot_options']
        fastboot_cmd = lxc_cmd_prefix(self.job) + ['fastboot', '-s', serial_number,
                                                   'reboot'] + fastboot_opts
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

    name = "enter-fastboot-action"
    description = "enter fastboot bootloader"
    summary = "enter fastboot"

    def validate(self):
        super().validate()
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

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        cmd_prefix = lxc_cmd_prefix(self.job)
        # Try to enter fastboot mode with adb.
        adb_serial_number = self.job.device['adb_serial_number']
        # start the adb daemon
        adb_cmd = cmd_prefix + ['adb', 'start-server']
        command_output = self.run_command(adb_cmd, allow_fail=True)
        if command_output and 'successfully' in command_output:
            self.logger.debug("adb daemon started: %s", command_output)
        adb_cmd = cmd_prefix + ['adb', '-s', adb_serial_number, 'devices']
        command_output = self.run_command(adb_cmd, allow_fail=True)
        if command_output and adb_serial_number in command_output:
            self.logger.debug("Device is in adb: %s", command_output)
            adb_cmd = cmd_prefix + ['adb', '-s', adb_serial_number,
                                    'reboot-bootloader']
            self.run_command(adb_cmd)
            return connection

        # Enter fastboot mode with fastboot.
        fastboot_serial_number = self.job.device['fastboot_serial_number']
        fastboot_opts = self.job.device['fastboot_options']
        fastboot_cmd = cmd_prefix + ['fastboot', '-s', fastboot_serial_number,
                                     'devices'] + fastboot_opts
        command_output = self.run_command(fastboot_cmd)
        if command_output and fastboot_serial_number in command_output:
            self.logger.debug("Device is in fastboot: %s", command_output)
            fastboot_cmd = cmd_prefix + [
                'fastboot', '-s', fastboot_serial_number, 'reboot-bootloader'
            ] + fastboot_opts
            command_output = self.run_command(fastboot_cmd)
            if command_output and 'OKAY' not in command_output:
                raise InfrastructureError("Unable to enter fastboot: %s" %
                                          command_output)
            else:
                lines = [status for status in command_output.split(
                    '\n') if 'finished' in status.lower()]
                if lines:
                    self.results = {'status': lines[0].strip()}
                else:
                    self.results = {'fail': 'fastboot'}
        return connection
