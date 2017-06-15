# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Birch <dean.birch@linaro.org>
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

from lava_dispatcher.pipeline.action import (
    Pipeline
)
from lava_dispatcher.pipeline.actions.boot import (
    AutoLoginAction,
    BootloaderCommandOverlay,
    OverlayUnpack
)
from lava_dispatcher.pipeline.actions.boot.bootloader_defaults import (
    BootloaderCommandsAction,
    BootloaderDefaultsRetry,
)
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.actions.boot.uefi_menu import UEFIMenuInterrupt, UefiMenuSelector
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.menus.menus import MenuInterrupt, MenuConnect
from lava_dispatcher.pipeline.power import (
    ResetDevice
)
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.utils.constants import UEFI_LINE_SEPARATOR


class UefiShell(Boot):

    compatibility = 3

    def __init__(self, parent, parameters):
        super(UefiShell, self).__init__(parent)
        self.action = UefiShellAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' not in parameters:
            raise RuntimeError("method not specified in boot parameters")
        if parameters['method'] != 'uefi':
            return False
        if 'boot' not in device['actions']:
            return False
        if 'methods' not in device['actions']['boot']:
            raise RuntimeError("Device misconfiguration")
        if 'uefi' in device['actions']['boot']['methods']:
            params = device['actions']['boot']['methods']['uefi']['parameters']
            if not params:
                return False
            if 'shell_interrupt_string' not in params:
                return False
            if 'shell_interrupt_prompt' in params and 'bootloader_prompt' in params:
                return True
        return False


class UefiShellAction(BootloaderDefaultsRetry):
    def __init__(self):
        super(UefiShellAction, self).__init__()
        self.name = "uefi-shell-main-action"
        self.description = "UEFI shell boot action"
        self.summary = "run UEFI shell to system"
        self.shell_menu = []

    def _skip_menu(self, parameters):
        # shell_menu can be set to '' to indicate there is no menu.
        if 'shell_menu' in parameters:
            self.shell_menu = parameters['shell_menu']
        elif 'shell_menu' in self.job.device['actions']['boot']['methods']['uefi']['parameters']:
            self.shell_menu = self.job.device['actions']['boot']['methods']['uefi']['parameters']['shell_menu']

        if self.shell_menu and isinstance(self.shell_menu, str):
            return False
        return True

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootloaderCommandOverlay())
        self.internal_pipeline.add_action(MenuConnect())
        self.internal_pipeline.add_action(ResetDevice())
        # Newer firmware often needs no menu interaction, just press to drop to shell
        if not self._skip_menu(parameters):
            # Some older firmware, UEFI Shell has to be selected from a menu.
            self.internal_pipeline.add_action(UefiShellMenuInterrupt())
            self.internal_pipeline.add_action(UefiShellMenuSelector())
        self.internal_pipeline.add_action(UefiShellInterrupt())
        self.internal_pipeline.add_action(UefiBootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if 'transfer_overlay' in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())

    def run(self, connection, max_end_time, args=None):
        connection = super(UefiShellAction, self).run(connection, max_end_time, args)
        connection.raw_connection.linesep = UEFI_LINE_SEPARATOR
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        return connection

    def validate(self):
        super(UefiShellAction, self).validate()
        params = self.job.device['actions']['boot']['methods']['uefi']['parameters']
        self.set_namespace_data(
            action=self.name,
            label='bootloader_prompt',
            key='prompt',
            value=params['bootloader_prompt']
        )


class UefiShellMenuInterrupt(UEFIMenuInterrupt):
    def __init__(self):
        super(UefiShellMenuInterrupt, self).__init__()
        self.name = 'uefi-shell-menu-interrupt'
        self.summary = 'interrupt default boot and to menu'
        self.description = 'interrupt default boot and to menu'
        # Take parameters from the uefi method, not uefi menu.
        self.method = 'uefi'


class UefiBootloaderCommandsAction(BootloaderCommandsAction):
    """
    Same as BootloaderCommandsAction, but uses UEFI_LINE_SEPARATOR.
    """
    def line_separator(self):
        return UEFI_LINE_SEPARATOR


class UefiShellInterrupt(MenuInterrupt):
    """
    Support for interrupting the UEFI menu and dropping to the shell.
    """
    def __init__(self):
        super(UefiShellInterrupt, self).__init__()
        self.name = 'uefi-shell-interrupt'
        self.summary = 'first uefi interrupt'
        self.description = 'interrupt uefi menu to get to a shell'

    def run(self, connection, max_end_time, args=None):
        if not connection:
            self.logger.debug("%s called without active connection", self.name)
            return
        connection = super(UefiShellInterrupt, self).run(connection, max_end_time, args)
        # param keys already checked in accepts() classmethod
        params = self.job.device['actions']['boot']['methods']['uefi']['parameters']
        connection.prompt_str = params['shell_interrupt_prompt']
        self.wait(connection)
        connection.raw_connection.send(params['shell_interrupt_string'])
        # now move on to bootloader prompt match
        return connection


class UefiShellMenuSelector(UefiMenuSelector):
    """
    Special version of the UefiMenuSelector configured to drop to the shell
    """
    def __init__(self):
        super(UefiShellMenuSelector, self).__init__()
        self.name = 'uefi-shell-menu-selector'
        self.summary = 'use uefi menu to drop to shell'
        self.description = 'select uefi menu items to drop to a uefi shell'
        # Take parameters from the uefi method, not uefi menu.
        self.method_name = 'uefi'
        # Default menu command name: drop to shell
        self.commands = 'shell'

    def validate(self):
        params = self.job.device['actions']['boot']['methods'][self.method_name]['parameters']
        if 'shell_menu' in self.parameters:
            self.commands = self.parameters['shell_menu']
        elif 'shell_menu' in params:
            self.commands = params['shell_menu']

        if self.commands in self.job.device['actions']['boot']['methods'][self.method_name]:
            self.items = self.job.device['actions']['boot']['methods'][self.method_name][self.commands]
        else:
            self.errors = "Missing menu commands for %s" % self.commands
        if 'menu_boot_message' in params:
            self.boot_message = params['menu_boot_message']
        super(UefiShellMenuSelector, self).validate()
        if 'menu_prompt' in params:
            self.selector.prompt = params['menu_prompt']
