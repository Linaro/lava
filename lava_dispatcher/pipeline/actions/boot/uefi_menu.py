# Copyright (C) 2015 Linaro Limited
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


from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    InfrastructureError,
)
from lava_dispatcher.pipeline.menus.menus import (
    SelectorMenuAction,
    MenuConnect,
    MenuInterrupt,
    MenuReset
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.power import ResetDevice
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.network import dispatcher_ip
from lava_dispatcher.pipeline.actions.boot import BootAction, AutoLoginAction
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.actions.deploy.lxc import LxcAddDeviceAction
from lava_dispatcher.pipeline.utils.constants import (
    DEFAULT_UEFI_LABEL_CLASS,
    UEFI_LINE_SEPARATOR
)


class UefiMenu(Boot):
    """
    The UEFI Menu strategy selects the specified options
    and inserts relevant strings into the UEFI menu instead
    of issuing commands over a shell-like serial connection.
    """

    def __init__(self, parent, parameters):
        super(UefiMenu, self).__init__(parent)
        self.action = UefiMenuAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' not in parameters:
            raise RuntimeError("method not specified in boot parameters")
        if parameters['method'] != 'uefi-menu':
            return False
        if 'boot' not in device['actions']:
            return False
        if 'methods' not in device['actions']['boot']:
            raise RuntimeError("Device misconfiguration")
        if 'uefi-menu' in device['actions']['boot']['methods']:
            params = device['actions']['boot']['methods']['uefi-menu']['parameters']
            if 'interrupt_prompt' in params and 'interrupt_string' in params:
                return True
        return False


class UEFIMenuInterrupt(MenuInterrupt):

    def __init__(self):
        super(UEFIMenuInterrupt, self).__init__()
        self.name = 'uefi-menu-interrupt'
        self.summary = 'interrupt for uefi menu'
        self.description = 'interrupt for uefi menu'

    def validate(self):
        super(UEFIMenuInterrupt, self).validate()
        params = self.job.device['actions']['boot']['methods']['uefi-menu']['parameters']
        if 'interrupt_prompt' not in params:
            self.errors = "Missing interrupt prompt"
        if 'interrupt_string' not in params:
            self.errors = "Missing interrupt string"

    def run(self, connection, max_end_time, args=None):
        if not connection:
            self.logger.debug("%s called without active connection", self.name)
            return
        connection = super(UEFIMenuInterrupt, self).run(connection, max_end_time, args)
        params = self.job.device['actions']['boot']['methods']['uefi-menu']['parameters']
        connection.prompt_str = params['interrupt_prompt']
        self.wait(connection)
        connection.raw_connection.send(params['interrupt_string'])
        return connection


class UefiMenuSelector(SelectorMenuAction):

    def __init__(self):
        super(UefiMenuSelector, self).__init__()
        self.name = 'uefi-menu-selector'
        self.summary = 'select options in the uefi menu'
        self.description = 'select specified uefi menu items'
        self.selector.prompt = "Start:"
        self.boot_message = None

    def validate(self):
        """
        Setup the items and pattern based on the parameters for this
        specific action, then let the base class complete the validation.
        """
        params = self.job.device['actions']['boot']['methods']['uefi-menu']['parameters']
        if ('item_markup' not in params or
                'item_class' not in params or 'separator' not in params):
            self.errors = "Missing device parameters for UEFI menu operations"
        if 'commands' not in self.parameters:
            self.errors = "Missing commands in action parameters"
            return
        if self.parameters['commands'] not in self.job.device['actions']['boot']['methods']['uefi-menu']:
            self.errors = "Missing commands for %s" % self.parameters['commands']
        self.selector.item_markup = params['item_markup']
        self.selector.item_class = params['item_class']
        self.selector.separator = params['separator']
        if 'label_class' in params:
            self.selector.label_class = params['label_class']
        else:
            # label_class is problematic via jinja and yaml templating.
            self.selector.label_class = DEFAULT_UEFI_LABEL_CLASS
        self.selector.prompt = params['bootloader_prompt']  # initial prompt
        self.boot_message = params['boot_message']  # final prompt
        self.items = self.job.device['actions']['boot']['methods']['uefi-menu'][self.parameters['commands']]
        super(UefiMenuSelector, self).validate()

    def run(self, connection, max_end_time, args=None):
        if self.job.device.pre_os_command:
            self.logger.info("Running pre OS command.")
            command = self.job.device.pre_os_command
            if not self.run_command(command.split(' '), allow_silent=True):
                raise InfrastructureError("%s failed" % command)
        if not connection:
            return connection
        connection.prompt_str = self.selector.prompt
        connection.raw_connection.linesep = UEFI_LINE_SEPARATOR
        self.logger.debug("Looking for %s", self.selector.prompt)
        self.wait(connection)
        connection = super(UefiMenuSelector, self).run(connection, max_end_time, args)
        self.logger.debug("Looking for %s", self.boot_message)
        connection.prompt_str = self.boot_message
        self.wait(connection)
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        return connection


class UefiSubstituteCommands(Action):

    def __init__(self):
        super(UefiSubstituteCommands, self).__init__()
        self.name = 'uefi-commands'
        self.summary = 'substitute job values into uefi commands'
        self.description = 'set job-specific variables into the uefi menu commands'
        self.items = None

    def validate(self):
        super(UefiSubstituteCommands, self).validate()
        if self.parameters['commands'] not in self.job.device['actions']['boot']['methods']['uefi-menu']:
            self.errors = "Missing commands for %s" % self.parameters['commands']
        self.items = self.job.device['actions']['boot']['methods']['uefi-menu'][self.parameters['commands']]
        for item in self.items:
            if 'select' not in item:
                self.errors = "Invalid device configuration for %s: %s" % (self.name, item)

    def run(self, connection, max_end_time, args=None):
        connection = super(UefiSubstituteCommands, self).run(connection, max_end_time, args)
        ip_addr = dispatcher_ip(self.job.parameters['dispatcher'])
        substitution_dictionary = {
            '{SERVER_IP}': ip_addr,
            '{RAMDISK}': self.get_namespace_data(action='compress-ramdisk', label='file', key='ramdisk'),
            '{KERNEL}': self.get_namespace_data(action='download_action', label='file', key='kernel'),
            '{DTB}': self.get_namespace_data(action='download_action', label='file', key='dtb'),
            'TEST_MENU_NAME': "LAVA %s test image" % self.parameters['commands']
        }
        nfs_root = self.get_namespace_data(action='download_action', label='file', key='nfsroot')
        if nfs_root:
            substitution_dictionary['{NFSROOTFS}'] = nfs_root
        for item in self.items:
            if 'enter' in item['select']:
                item['select']['enter'] = substitute([item['select']['enter']], substitution_dictionary)[0]
            if 'items' in item['select']:
                # items is already a list, so pass without wrapping in []
                item['select']['items'] = substitute(item['select']['items'], substitution_dictionary)
        return connection


class UefiMenuAction(BootAction):

    def __init__(self):
        super(UefiMenuAction, self).__init__()
        self.name = 'uefi-menu-action'
        self.summary = 'interact with uefi menu'
        self.description = 'interrupt and select uefi menu items'

    def validate(self):
        super(UefiMenuAction, self).validate()
        self.set_namespace_data(
            action=self.name,
            label='bootloader_prompt',
            key='prompt',
            value=self.job.device['actions']['boot']['methods']['uefi-menu']['parameters']['bootloader_prompt']
        )

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if 'commands' in parameters and 'fastboot' in parameters['commands']:
            self.internal_pipeline.add_action(UefiSubstituteCommands())
            self.internal_pipeline.add_action(UEFIMenuInterrupt())
            self.internal_pipeline.add_action(UefiMenuSelector())
            self.internal_pipeline.add_action(MenuReset())
            self.internal_pipeline.add_action(AutoLoginAction())
            self.internal_pipeline.add_action(LxcAddDeviceAction())
        else:
            self.internal_pipeline.add_action(UefiSubstituteCommands())
            self.internal_pipeline.add_action(MenuConnect())
            self.internal_pipeline.add_action(ResetDevice())
            self.internal_pipeline.add_action(UEFIMenuInterrupt())
            self.internal_pipeline.add_action(UefiMenuSelector())
            self.internal_pipeline.add_action(MenuReset())
            self.internal_pipeline.add_action(AutoLoginAction())
            self.internal_pipeline.add_action(ExportDeviceEnvironment())
