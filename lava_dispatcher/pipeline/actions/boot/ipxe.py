# Copyright (C) 2014 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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

from lava_dispatcher.pipeline.action import (
    Action,
    ConfigurationError,
    LAVABug,
    Pipeline,
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import (
    BootAction,
    AutoLoginAction,
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    OverlayUnpack,
)
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.power import ResetDevice
from lava_dispatcher.pipeline.utils.constants import (
    IPXE_BOOT_PROMPT,
)


def bootloader_accepts(device, parameters):
    if 'method' not in parameters:
        raise ConfigurationError("method not specified in boot parameters")
    if parameters['method'] != 'ipxe':
        return False
    if 'actions' not in device:
        raise ConfigurationError("Invalid device configuration")
    if 'boot' not in device['actions']:
        return False
    if 'methods' not in device['actions']['boot']:
        raise ConfigurationError("Device misconfiguration")
    return True


class IPXE(Boot):
    """
    The IPXE method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then interrupt iPXE.
    An expect shell session can then be handed over to the BootloaderAction.
    self.run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    compatibility = 1

    def __init__(self, parent, parameters):
        super(IPXE, self).__init__(parent)
        self.action = BootloaderAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not bootloader_accepts(device, parameters):
            return False
        return 'ipxe' in device['actions']['boot']['methods']


class BootloaderAction(BootAction):
    """
    Wraps the Retry Action to allow for actions which precede
    the reset, e.g. Connect.
    """
    def __init__(self):
        super(BootloaderAction, self).__init__()
        self.name = "bootloader-action"
        self.description = "interactive bootloader action"
        self.summary = "pass boot commands"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # customize the device configuration for this job
        self.internal_pipeline.add_action(BootloaderCommandOverlay())
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(BootloaderRetry())


class BootloaderRetry(BootAction):

    def __init__(self):
        super(BootloaderRetry, self).__init__()
        self.name = "bootloader-retry"
        self.description = "interactive uboot retry action"
        self.summary = "uboot commands with retry"
        self.type = "ipxe"
        self.force_prompt = False

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # establish a new connection before trying the reset
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(BootloaderInterrupt())
        # need to look for Hit any key to stop autoboot
        self.internal_pipeline.add_action(BootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if 'transfer_overlay' in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())

    def validate(self):
        super(BootloaderRetry, self).validate()
        if 'bootloader_prompt' not in self.job.device['actions']['boot']['methods'][self.type]['parameters']:
            self.errors = "Missing bootloader prompt for device"
        self.set_namespace_data(
            action=self.name,
            label='bootloader_prompt',
            key='prompt',
            value=self.job.device['actions']['boot']['methods'][self.type]['parameters']['bootloader_prompt']
        )

    def run(self, connection, max_end_time, args=None):
        connection = super(BootloaderRetry, self).run(connection, max_end_time, args)
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        return connection


class BootloaderInterrupt(Action):
    """
    Support for interrupting the bootloader.
    """
    def __init__(self):
        super(BootloaderInterrupt, self).__init__()
        self.name = "bootloader-interrupt"
        self.description = "interrupt bootloader"
        self.summary = "interrupt bootloader to get a prompt"
        self.type = "ipxe"

    def validate(self):
        super(BootloaderInterrupt, self).validate()
        hostname = self.job.device['hostname']
        if self.job.device.connect_command is '':
            self.errors = "Unable to connect to device %s" % hostname
        device_methods = self.job.device['actions']['boot']['methods']
        if 'bootloader_prompt' not in device_methods[self.type]['parameters']:
            self.errors = "Missing bootloader prompt for device"

    def run(self, connection, max_end_time, args=None):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super(BootloaderInterrupt, self).run(connection, max_end_time, args)
        self.logger.debug("Changing prompt to '%s'", IPXE_BOOT_PROMPT)
        # device is to be put into a reset state, either by issuing 'reboot' or power-cycle
        connection.prompt_str = IPXE_BOOT_PROMPT
        self.wait(connection)
        connection.sendcontrol("b")
        return connection
