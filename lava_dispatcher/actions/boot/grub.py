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

from lava_dispatcher.action import (
    Action,
    ConfigurationError,
    LAVABug,
    Pipeline
)
from lava_dispatcher.logical import Boot
from lava_dispatcher.actions.boot import (
    BootAction,
    AutoLoginAction,
    BootloaderCommandOverlay,
    BootloaderSecondaryMedia,
    BootloaderCommandsAction,
    OverlayUnpack,
    BootloaderInterruptAction
)
from lava_dispatcher.actions.boot.uefi_menu import (
    UEFIMenuInterrupt,
    UefiMenuSelector
)
from lava_dispatcher.actions.boot.fastboot import WaitFastBootInterrupt
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.power import (
    ResetDevice,
    PowerOff
)


class GrubSequence(Boot):

    compatibility = 3

    def __init__(self, parent, parameters):
        super(GrubSequence, self).__init__(parent)
        self.action = GrubSequenceAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' not in parameters:
            raise ConfigurationError("method not specified in boot parameters")
        if parameters["method"] not in ["grub", "grub-efi"]:
            return False, '"method" was not "grub" or "grub-efi"'
        if 'actions' not in device:
            raise ConfigurationError("Invalid device configuration")
        if 'boot' not in device['actions']:
            return False, '"boot" was not in the device configuration actions'
        if 'methods' not in device['actions']['boot']:
            raise ConfigurationError("Device misconfiguration")
        params = device['actions']['boot']['methods']
        if 'grub' not in params:
            return False, '"grub" was not in the device configuration boot methods'
        if 'grub-efi' in params:
            return False, '"grub-efi" was not in the device configuration boot methods'
        if 'sequence' in params['grub']:
            return True, 'accepted'
        return False, '"sequence" not in device configuration boot methods'


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
        if 'method' not in parameters:
            raise ConfigurationError("method not specified in boot parameters")
        if parameters["method"] not in ["grub", "grub-efi"]:
            return False, '"method" was not "grub" or "grub-efi"'
        if 'actions' not in device:
            raise ConfigurationError("Invalid device configuration")
        if 'boot' not in device['actions']:
            return False, '"boot" was not in the device configuration actions'
        if 'methods' not in device['actions']['boot']:
            raise ConfigurationError("Device misconfiguration")
        params = device['actions']['boot']['methods']
        if 'grub' in params and 'sequence' in params['grub']:
            return False, '"sequence" was in "grub" parameters'
        if 'grub' in params or 'grub-efi' in params:
            return True, 'accepted'
        else:
            return False, '"grub" or "grub-efi" was not in the device configuration boot methods'


def _grub_sequence_map(sequence):
    """Maps grub sequence with corresponding class."""
    sequence_map = {
        'wait-fastboot-interrupt': (WaitFastBootInterrupt, 'grub'),
        'auto-login': (AutoLoginAction, None),
        'shell-session': (ExpectShellSession, None),
        'export-env': (ExportDeviceEnvironment, None),
    }
    return sequence_map.get(sequence, (None, None))


class GrubSequenceAction(BootAction):

    def __init__(self):
        super(GrubSequenceAction, self).__init__()
        self.name = "grub-sequence-action"
        self.description = "grub boot sequence"
        self.summary = "run grub boot using specified sequence of actions"
        self.expect_shell = False

    def validate(self):
        super(GrubSequenceAction, self).validate()
        sequences = self.job.device['actions']['boot']['methods']['grub'].get(
            'sequence', [])
        for sequence in sequences:
            if not _grub_sequence_map(sequence):
                self.errors = "Unknown boot sequence '%s'" % sequence

    def populate(self, parameters):
        super(GrubSequenceAction, self).populate(parameters)
        self.internal_pipeline = Pipeline(parent=self, job=self.job,
                                          parameters=parameters)
        sequences = self.job.device['actions']['boot']['methods']['grub'].get(
            'sequence', [])
        for sequence in sequences:
            mapped = _grub_sequence_map(sequence)
            if mapped[1]:
                self.internal_pipeline.add_action(
                    mapped[0](type=mapped[1]))
            elif mapped[0]:
                self.internal_pipeline.add_action(mapped[0]())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if 'transfer_overlay' in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())
        else:
            if self.has_boot_finished(parameters):
                self.logger.debug("Doing a boot without a shell (installer)")
                self.internal_pipeline.add_action(InstallerWait())
                self.internal_pipeline.add_action(PowerOff())


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
        self.internal_pipeline.add_action(BootloaderSecondaryMedia())
        self.internal_pipeline.add_action(BootloaderCommandOverlay())
        self.internal_pipeline.add_action(ConnectDevice())
        # FIXME: reset_device is a hikey hack due to fastboot/OTG issues
        # remove as part of LAVA-940 - convert to use fastboot-sequence
        reset_device = self.job.device['actions']['boot']['methods'].get('grub-efi', {}).get('reset_device', True)
        if parameters['method'] == 'grub-efi' and reset_device:
            # added unless the device specifies not to reset the device in grub.
            self.internal_pipeline.add_action(ResetDevice())
        elif parameters['method'] == 'grub':
            self.internal_pipeline.add_action(ResetDevice())
        if parameters['method'] == 'grub-efi':
            self.internal_pipeline.add_action(UEFIMenuInterrupt())
            self.internal_pipeline.add_action(GrubMenuSelector())
        self.internal_pipeline.add_action(BootloaderInterruptAction())
        self.internal_pipeline.add_action(BootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if 'transfer_overlay' in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())
        else:
            if self.has_boot_finished(parameters):
                self.logger.debug("Doing a boot without a shell (installer)")
                self.internal_pipeline.add_action(InstallerWait())
                self.internal_pipeline.add_action(PowerOff())

    def run(self, connection, max_end_time, args=None):
        connection = super(GrubMainAction, self).run(connection, max_end_time, args)
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        return connection


class GrubMenuSelector(UefiMenuSelector):  # pylint: disable=too-many-instance-attributes

    def __init__(self):
        super(GrubMenuSelector, self).__init__()
        self.name = 'grub-efi-menu-selector'
        self.summary = 'select grub options in the efi menu'
        self.description = 'select specified grub-efi menu items'
        self.selector.prompt = "Start:"
        self.commands = []
        self.boot_message = None
        self.params = None

    def validate(self):
        if self.method_name not in self.job.device['actions']['boot']['methods']:
            self.errors = "No %s in device boot methods" % self.method_name
            return
        self.params = self.job.device['actions']['boot']['methods'][self.method_name]
        if 'menu_options' not in self.params:
            self.errors = "Missing entry for menu item to use for %s" % self.method_name
            return
        self.commands = self.params['menu_options']
        super(GrubMenuSelector, self).validate()

    def run(self, connection, max_end_time, args=None):
        interrupt_prompt = self.params['parameters'].get(
            'interrupt_prompt', self.job.device.get_constant('grub-autoboot-prompt'))
        self.logger.debug("Adding '%s' to prompt", interrupt_prompt)
        connection.prompt_str = interrupt_prompt
        # override base class behaviour to interact with grub.
        self.boot_message = None
        connection = super(GrubMenuSelector, self).run(connection, max_end_time, args)
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
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        return connection
