# Copyright (C) 2016 Linaro Limited
#
# Author: Dean Arnold <dean.arnold@linaro.org>
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
    Pipeline,
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import BootAction, AutoLoginAction
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.power import ResetDevice
from lava_dispatcher.pipeline.utils.constants import (
    UBOOT_AUTOBOOT_PROMPT,
    BOOT_MESSAGE,
)


def default_accepts(device, parameters):
    if 'method' not in parameters:
        raise RuntimeError("method not specified in boot parameters")
    if parameters['method'] != 'bootloader-defaults':
        return False
    if 'actions' not in device:
        raise RuntimeError("Invalid device configuration")
    if 'boot' not in device['actions']:
        return False
    if 'methods' not in device['actions']['boot']:
        raise RuntimeError("Device misconfiguration")
    return True


class BootloaderDefaults(Boot):
    """
    """

    compatibility = 1

    def __init__(self, parent, parameters):
        super(BootloaderDefaults, self).__init__(parent)
        self.action = BootloaderDefaultsAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not default_accepts(device, parameters):
            return False
        return 'bootloader-defaults' in device['actions']['boot']['methods']


class BootloaderDefaultsAction(BootAction):
    """
    Wraps the Retry Action to allow for actions which precede
    the reset, e.g. Connect.
    """
    def __init__(self):
        super(BootloaderDefaultsAction, self).__init__()
        self.name = "bootloader-defaults-action"
        self.description = "Autorun precanned bootloader entry"
        self.summary = "allow bootloader to run"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # customize the device configuration for this job
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(BootloaderDefaultsRetry())


class MonitorBootloaderAutoBoot(Action):
    """
    Waits for a shell connection to the device for the current job.
    """

    def __init__(self):
        super(MonitorBootloaderAutoBoot, self).__init__()
        self.name = "monitor-bootloader-autoboot"
        self.summary = "Monitor that bootloder autoboot is taking place"
        self.description = "Wait for autoboot to happen"

    def run(self, connection, max_end_time, args=None):
        if not connection:
            raise RuntimeError("%s started without a connection already in use" % self.name)
        connection = super(MonitorBootloaderAutoBoot, self).run(connection, max_end_time, args)
        params = self.job.device['actions']['boot']['methods']['bootloader-defaults']['parameters']
        connection.prompt_str = params.get('autoboot_prompt', UBOOT_AUTOBOOT_PROMPT)
        self.logger.debug("Waiting for prompt: %s", connection.prompt_str)
        self.wait(connection)
        # allow for auto_login
        connection.prompt_str = params.get('boot_message', BOOT_MESSAGE)
        self.logger.debug("Waiting for prompt: %s", connection.prompt_str)
        self.wait(connection)
        return connection


class BootloaderDefaultsRetry(BootAction):

    def __init__(self):
        super(BootloaderDefaultsRetry, self).__init__()
        self.name = "uboot-retry"
        self.description = "interactive uboot retry action"
        self.summary = "uboot commands with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # establish a new connection before trying the reset
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(MonitorBootloaderAutoBoot())  # wait
        # and set prompt to the uboot prompt
        # Add AutoLoginAction unconditionally as this action does nothing if
        # the configuration does not contain 'auto_login'
        self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())  # wait
        self.internal_pipeline.add_action(ExportDeviceEnvironment())

    def validate(self):
        super(BootloaderDefaultsRetry, self).validate()
        self.set_namespace_data(
            action=self.name,
            label='bootloader_prompt',
            key='prompt',
            value=self.job.device['actions']['boot']['methods']['bootloader-defaults']['parameters']['bootloader_prompt']
        )

    def run(self, connection, max_end_time, args=None):
        connection = super(BootloaderDefaultsRetry, self).run(connection, max_end_time, args)
        self.logger.debug("Setting default test shell prompt")
        if not connection.prompt_str:
            connection.prompt_str = self.parameters['prompts']
        self.logger.debug(connection.prompt_str)
        connection.timeout = self.connection_timeout
        self.wait(connection)
        self.logger.error(self.errors)
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        return connection
