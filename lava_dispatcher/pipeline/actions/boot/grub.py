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
    Pipeline
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import (
    BootAction,
    AutoLoginAction,
    BootloaderCommandOverlay,
    BootloaderCommandsAction
)
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.power import (
    ResetDevice,
    PowerOff
)
from lava_dispatcher.pipeline.utils.constants import (
    GRUB_BOOT_PROMPT,
)


def bootloader_accepts(device, parameters):
    if 'method' not in parameters:
        raise ConfigurationError("method not specified in boot parameters")
    if parameters['method'] != 'grub':
        return False
    if 'actions' not in device:
        raise ConfigurationError("Invalid device configuration")
    if 'boot' not in device['actions']:
        return False
    if 'methods' not in device['actions']['boot']:
        raise ConfigurationError("Device misconfiguration")
    return True


class Grub(Boot):

    compatibility = 3

    def __init__(self, parent, parameters):
        super(Grub, self).__init__(parent)
        self.action = GrubMainAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not bootloader_accepts(device, parameters):
            return False
        return 'grub' in device['actions']['boot']['methods']


class GrubMainAction(BootAction):
    def __init__(self):
        super(GrubMainAction, self).__init__()
        self.name = "grub-main-action"
        self.description = "main grub boot action"
        self.summary = "run grub boot from power to system"
        self.expect_shell = True

    def populate(self, parameters):
        self.expect_shell = parameters.get('expect_shell', True)
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootloaderCommandOverlay())
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(BootloaderInterrupt())
        self.internal_pipeline.add_action(BootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())
        else:
            if self.has_boot_finished(parameters):
                self.logger.debug("Doing a boot without a shell (installer)")
                self.internal_pipeline.add_action(InstallerWait())
                self.internal_pipeline.add_action(PowerOff())

    def run(self, connection, max_end_time, args=None):
        connection = super(GrubMainAction, self).run(connection, max_end_time, args)
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
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
        self.type = "grub"

    def validate(self):
        super(BootloaderInterrupt, self).validate()
        hostname = self.job.device['hostname']
        # boards which are reset manually can be supported but errors have to handled manually too.
        if self.job.device.power_state in ['on', 'off']:
            # to enable power to a device, either power_on or hard_reset are needed.
            if self.job.device.power_command is '':
                self.errors = "Unable to power on or reset the device %s" % hostname
            if self.job.device.connect_command is '':
                self.errors = "Unable to connect to device %s" % hostname
        else:
            self.logger.debug("%s may need manual intervention to reboot", hostname)
        device_methods = self.job.device['actions']['boot']['methods']
        if 'bootloader_prompt' not in device_methods[self.type]['parameters']:
            self.errors = "Missing bootloader prompt for device"

    def run(self, connection, max_end_time, args=None):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super(BootloaderInterrupt, self).run(connection, max_end_time, args)
        self.logger.debug("Changing prompt to '%s'", GRUB_BOOT_PROMPT)
        # device is to be put into a reset state, either by issuing 'reboot' or power-cycle
        connection.prompt_str = GRUB_BOOT_PROMPT
        self.wait(connection)
        connection.sendline("c")
        return connection


class InstallerWait(Action):
    """
    Wait for the non-interactive installer to finished
    """
    def __init__(self):
        super(InstallerWait, self).__init__()
        self.name = "installer-wait"
        self.description = "installer wait"
        self.summary = "wait for task to finish match arbitrary string"
        self.type = "grub"

    def validate(self):
        super(InstallerWait, self).validate()
        if "boot_finished" not in self.parameters:
            self.errors = "Missing boot_finished string"

    def run(self, connection, max_end_time, args=None):
        connection = super(InstallerWait, self).run(connection, max_end_time, args)
        wait_string = self.parameters['boot_finished']
        msg = wait_string if isinstance(wait_string, str) else ', '.join(wait_string)
        self.logger.debug("Not expecting a shell, so waiting for boot_finished: %s", msg)
        connection.prompt_str = wait_string
        self.wait(connection)
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        return connection
