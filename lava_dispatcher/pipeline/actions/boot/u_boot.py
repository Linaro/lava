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

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os
from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    Boot,
    Timeout,
    InfrastructureError,
)
from lava_dispatcher.pipeline.actions.boot import BootAction, AutoLoginAction
from lava_dispatcher.pipeline.shell import (
    ConnectDevice,
    ExpectShellSession,
)
from lava_dispatcher.pipeline.power import ResetDevice
from lava_dispatcher.pipeline.utils.constants import (
    UBOOT_AUTOBOOT_PROMPT,
    UBOOT_DEFAULT_CMD_TIMEOUT,
    AUTOLOGIN_DEFAULT_TIMEOUT,
)
from lava_dispatcher.pipeline.utils.network import dispatcher_ip


def uboot_accepts(device, parameters):
    if 'method' not in parameters:
        raise RuntimeError("method not specified in boot parameters")
    if parameters['method'] != 'u-boot':
        return False
    if 'actions' not in device.parameters:
        raise RuntimeError("Invalid device configuration")
    if 'boot' not in device.parameters['actions']:
        return False
    if 'methods' not in device.parameters['actions']['boot']:
        raise RuntimeError("Device misconfiguration")
    return True


class UBoot(Boot):
    """
    The UBoot method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then interrupt u-boot.
    An expect shell session can then be handed over to the UBootAction.
    self._run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    def __init__(self, parent, parameters):
        super(UBoot, self).__init__(parent)
        self.action = UBootAction()
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not uboot_accepts(device, parameters):
            return False
        for tmp in device.parameters['actions']['boot']['methods']:
            if type(tmp) != dict:
                return False
            if 'u-boot' in tmp:  # 2to3 false positive, works with python3
                return True
        return False


class UBootAction(BootAction):
    """
    Wraps the Retry Action to allow for actions which precede
    the reset, e.g. Connect.
    """
    def __init__(self):
        super(UBootAction, self).__init__()
        self.name = "uboot-action"
        self.description = "interactive uboot action"
        self.summary = "pass uboot commands"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # customize the device configuration for this job
        self.internal_pipeline.add_action(UBootCommandOverlay())
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(UBootRetry())


class UBootRetry(BootAction):

    def __init__(self):
        super(UBootRetry, self).__init__()
        self.name = "uboot-retry"
        self.description = "interactive uboot retry action"
        self.summary = "uboot commands with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # establish a new connection before trying the reset
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(UBootInterrupt())
        # need to look for Hit any key to stop autoboot
        self.internal_pipeline.add_action(ExpectShellSession())  # wait
        # and set prompt to the uboot prompt
        self.internal_pipeline.add_action(UBootCommandsAction())
        # Add AutoLoginAction unconditionnally as this action does nothing if
        # the configuration does not contain 'auto_login'
        auto_login = AutoLoginAction()
        auto_login.timeout = Timeout(self.name, AUTOLOGIN_DEFAULT_TIMEOUT)
        self.internal_pipeline.add_action(auto_login)

    def validate(self):
        super(UBootRetry, self).validate()
        self.data['common']['bootloader_prompt'] = self.parameters['u-boot']['parameters']['bootloader_prompt']

    def run(self, connection, args=None):
        super(UBootRetry, self).run(connection, args)
        # FIXME: tests with multiple boots need to be handled too.
        self.data.update({'boot-result': 'failed' if self.errors else 'success'})


class UBootInterrupt(Action):
    """
    Support for interrupting the bootloader.
    """
    def __init__(self):
        super(UBootInterrupt, self).__init__()
        self.name = "u-boot-interrupt"
        self.description = "interrupt u-boot"
        self.summary = "interrupt u-boot to get a prompt"

    def validate(self):
        super(UBootInterrupt, self).validate()
        hostname = self.job.device.parameters['hostname']
        # boards which are reset manually can be supported but errors have to handled manually too.
        if self.job.device.power_state in ['on', 'off']:
            # to enable power to a device, either power_on or hard_reset are needed.
            if self.job.device.power_command is '':
                self.errors = "Unable to power on or reset the device %s" % hostname
            if self.job.device.connect_command is '':
                self.errors = "Unable to connect to device %s" % hostname
        else:
            self.logger.debug("%s may need manual intervention to reboot" % hostname)

    def run(self, connection, args=None):
        if not connection:
            raise RuntimeError("%s started without a connection already in use" % self.name)
        self.logger.debug("Changing prompt to 'Hit any key to stop autoboot'")
        # device is to be put into a reset state, either by issuing 'reboot' or power-cycle
        connection.prompt_str = UBOOT_AUTOBOOT_PROMPT
        # command = self.job.device.parameters['commands'].get('interrupt', '\n')
        connection.wait()
        connection.sendline(' \n')
        connection.prompt_str = self.parameters['u-boot']['parameters']['bootloader_prompt']
        connection.wait()
        return connection


class UBootCommandOverlay(Action):
    """
    Replace KERNEL_ADDR and DTB placeholders with the actual values for this
    particular pipeline.
    addresses are read from the device configuration parameters
    bootloader_type is determined from the boot action method strategy
    bootz or bootm is determined by boot action method type. (i.e. it is up to
    the test writer to select the correct download file for the correct boot command.)
    server_ip is calculated at runtime
    filenames are determined from the download Action.
    """
    def __init__(self):
        super(UBootCommandOverlay, self).__init__()
        self.name = "uboot-overlay"
        self.summary = "replace placeholders with job data"
        self.description = "substitute job data into uboot command list"

    def substitute(self, command_list, dictionary):
        parsed = []
        for line in command_list:
            for key, value in dictionary.items():  # 2to3 false positive, works with python3
                line = line.replace(key, value)
            parsed.append(line)
        self.data['u-boot']['commands'] = parsed
        self.logger.debug("Parsed boot commands: %s" % '; '.join(parsed))

    def validate(self):
        super(UBootCommandOverlay, self).validate()
        if 'method' not in self.parameters:
            self.errors = "missing method"
        elif 'commands' not in self.parameters:
            self.errors = "missing commands"
        elif self.parameters['commands'] not in self.parameters[self.parameters['method']]:
            self.errors = "Command not found in supported methods"
        elif 'commands' not in self.parameters[self.parameters['method']][self.parameters['commands']]:
            self.errors = "No commands found in parameters"
        commands = self.parameters[self.parameters['method']][self.parameters['commands']]['commands']
        # download_action will set ['dtb'] as tftp_path, tmpdir & filename later, in the run step.
        self.data.setdefault('u-boot', {})
        self.data['u-boot'].setdefault('commands', [])
        if 'type' not in self.parameters:
            self.errors = "No boot type specified in device parameters."
        else:
            if self.parameters['type'] not in self.job.device.parameters['parameters']:
                self.errors = "Unable to match specified boot type with device parameters"
        self.data['u-boot']['commands'] = commands

    def run(self, connection, args=None):
        """
        Read data from the download action and replace in context
        """
        try:
            ip_addr = dispatcher_ip()
        except InfrastructureError as exc:
            raise RuntimeError("Unable to get dispatcher IP address: %s" % exc)
        substitutions = {
            '{SERVER_IP}': ip_addr
        }

        kernel_addr = self.job.device.parameters['parameters'][self.parameters['type']]['kernel']
        dtb_addr = self.job.device.parameters['parameters'][self.parameters['type']]['dtb']
        ramdisk_addr = self.job.device.parameters['parameters'][self.parameters['type']]['ramdisk']

        substitutions['{KERNEL_ADDR}'] = kernel_addr
        substitutions['{DTB_ADDR}'] = dtb_addr
        substitutions['{RAMDISK_ADDR}'] = ramdisk_addr
        substitutions['{BOOTX}'] = "%s %s %s %s" % (
            self.parameters['type'], kernel_addr, ramdisk_addr, dtb_addr)

        suffix = self.data['tftp-deploy'].get('suffix', '')
        if self.data['compress-ramdisk'].get('ramdisk', None):
            substitutions['{RAMDISK}'] = os.path.join(
                suffix, os.path.basename(self.data['compress-ramdisk']['ramdisk'])
            )
        else:
            substitutions['{BOOTX}'] = "%s %s - %s" % (
                self.parameters['type'], kernel_addr, dtb_addr)

        substitutions['{KERNEL}'] = os.path.join(
            suffix, os.path.basename(self.data['download_action']['kernel']['file'])
        )
        substitutions['{DTB}'] = os.path.join(
            suffix, os.path.basename(self.data['download_action']['dtb']['file'])
        )

        if 'nfsrootfs' in self.data['download_action']:
            substitutions['{NFSROOTFS}'] = self.data['extract-nfsrootfs'].get('nfsroot')

        self.substitute(self.data['u-boot']['commands'], substitutions)
        return connection


class UBootCommandsAction(Action):
    """
    Send the ramdisk commands to u-boot
    """
    def __init__(self):
        super(UBootCommandsAction, self).__init__()
        self.name = "u-boot-commands"
        self.description = "send commands to u-boot"
        self.summary = "interactive u-boot"
        self.prompt = None
        # FIXME: the default timeout needs to be configurable.
        self.timeout = Timeout(self.name, UBOOT_DEFAULT_CMD_TIMEOUT)

    def validate(self):
        super(UBootCommandsAction, self).validate()
        if 'u-boot' not in self.data:
            self.errors = "Unable to read uboot context data"
        elif 'commands' not in self.data['u-boot']:
            self.errors = "Unable to read uboot command list"
        # get prompt_str from device parameters
        self.prompt = self.parameters['u-boot']['parameters']['bootloader_prompt']

    def run(self, connection, args=None):
        if not connection:
            self.errors = "%s started without a connection already in use" % self.name
        connection.timeout = self.timeout
        self.logger.debug("Changing prompt to %s" % self.prompt)
        for line in self.data['u-boot']['commands']:
            connection.wait()
            connection.sendline(line)
        # allow for auto_login
        return connection
