# Copyright (C) 2014 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import (
    AutoLoginAction,
    BootHasMixin,
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    BootloaderInterruptAction,
    BootloaderSecondaryMedia,
    OverlayUnpack,
)
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.actions.boot.fastboot import WaitFastBootInterrupt
from lava_dispatcher.actions.boot.uefi_menu import UEFIMenuInterrupt, UefiMenuSelector
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import PowerOff, ResetDevice
from lava_dispatcher.shell import ExpectShellSession


class GrubSequence(Boot):
    @classmethod
    def action(cls):
        return GrubSequenceAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] not in ["grub", "grub-efi"]:
            return False, '"method" was not "grub" or "grub-efi"'

        params = device["actions"]["boot"]["methods"]
        if "grub" not in params:
            return False, '"grub" was not in the device configuration boot methods'
        if "grub-efi" in params:
            return False, '"grub-efi" was not in the device configuration boot methods'
        if "sequence" in params["grub"]:
            return True, "accepted"
        return False, '"sequence" not in device configuration boot methods'


class Grub(Boot):
    @classmethod
    def action(cls):
        return GrubMainAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] not in ["grub", "grub-efi"]:
            return False, '"method" was not "grub" or "grub-efi"'

        params = device["actions"]["boot"]["methods"]
        if "grub" in params and "sequence" in params["grub"]:
            return False, '"sequence" was in "grub" parameters'
        if "grub" in params or "grub-efi" in params:
            return True, "accepted"
        else:
            return (
                False,
                '"grub" or "grub-efi" was not in the device configuration boot methods',
            )


def _grub_sequence_map(sequence):
    """Maps grub sequence with corresponding class."""
    sequence_map = {
        "wait-fastboot-interrupt": (WaitFastBootInterrupt, "grub"),
        "auto-login": (AutoLoginAction, None),
        "shell-session": (ExpectShellSession, None),
        "export-env": (ExportDeviceEnvironment, None),
    }
    return sequence_map.get(sequence, (None, None))


class GrubSequenceAction(BootHasMixin, RetryAction):
    name = "grub-sequence-action"
    description = "grub boot sequence"
    summary = "run grub boot using specified sequence of actions"

    def __init__(self):
        super().__init__()
        self.expect_shell = False

    def validate(self):
        super().validate()
        sequences = self.job.device["actions"]["boot"]["methods"]["grub"].get(
            "sequence", []
        )
        for sequence in sequences:
            if not _grub_sequence_map(sequence):
                self.errors = "Unknown boot sequence '%s'" % sequence

    def populate(self, parameters):
        super().populate(parameters)
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        sequences = self.job.device["actions"]["boot"]["methods"]["grub"].get(
            "sequence", []
        )
        for sequence in sequences:
            mapped = _grub_sequence_map(sequence)
            if mapped[1]:
                self.pipeline.add_action(mapped[0](itype=mapped[1]))
            elif mapped[0]:
                self.pipeline.add_action(mapped[0]())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack())
                self.pipeline.add_action(ExportDeviceEnvironment())
        else:
            if self.has_boot_finished(parameters):
                self.logger.debug("Doing a boot without a shell (installer)")
                self.pipeline.add_action(InstallerWait())
                self.pipeline.add_action(PowerOff())


class GrubMainAction(BootHasMixin, RetryAction):
    name = "grub-main-action"
    description = "main grub boot action"
    summary = "run grub boot from power to system"

    def __init__(self):
        super().__init__()
        self.expect_shell = True

    def populate(self, parameters):
        self.expect_shell = parameters.get("expect_shell", True)
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(BootloaderSecondaryMedia())
        self.pipeline.add_action(BootloaderCommandOverlay())
        self.pipeline.add_action(ConnectDevice())
        # FIXME: reset_device is a hikey hack due to fastboot/OTG issues
        # remove as part of LAVA-940 - convert to use fastboot-sequence
        reset_device = (
            self.job.device["actions"]["boot"]["methods"]
            .get("grub-efi", {})
            .get("reset_device", True)
        )
        if parameters["method"] == "grub-efi" and reset_device:
            # added unless the device specifies not to reset the device in grub.
            self.pipeline.add_action(ResetDevice())
        elif parameters["method"] == "grub":
            self.pipeline.add_action(ResetDevice())
        if parameters["method"] == "grub-efi":
            self.pipeline.add_action(UEFIMenuInterrupt())
            self.pipeline.add_action(GrubMenuSelector())
        self.pipeline.add_action(BootloaderInterruptAction())
        self.pipeline.add_action(BootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack())
                self.pipeline.add_action(ExportDeviceEnvironment())
        else:
            if self.has_boot_finished(parameters):
                self.logger.debug("Doing a boot without a shell (installer)")
                self.pipeline.add_action(InstallerWait())
                self.pipeline.add_action(PowerOff())


class GrubMenuSelector(UefiMenuSelector):
    name = "grub-efi-menu-selector"
    description = "select specified grub-efi menu items"
    summary = "select grub options in the efi menu"

    def __init__(self):
        super().__init__()
        self.selector.prompt = "Start:"
        self.commands = []
        self.boot_message = None
        self.params = None

    def validate(self):
        if self.method_name not in self.job.device["actions"]["boot"]["methods"]:
            self.errors = "No %s in device boot methods" % self.method_name
            return
        self.params = self.job.device["actions"]["boot"]["methods"][self.method_name]
        if "menu_options" not in self.params:
            self.errors = "Missing entry for menu item to use for %s" % self.method_name
            return
        self.commands = self.params["menu_options"]
        super().validate()

    def run(self, connection, max_end_time):
        # Needs to get the interrupt_prompt from the bootloader device config
        interrupt_prompt = self.params["parameters"].get(
            "interrupt_prompt",
            self.job.device.get_constant("interrupt-prompt", prefix="grub"),
        )
        self.logger.debug("Adding '%s' to prompt", interrupt_prompt)
        connection.prompt_str = interrupt_prompt
        # override base class behaviour to interact with grub.
        self.boot_message = None
        connection = super().run(connection, max_end_time)
        return connection


class InstallerWait(Action):
    """
    Wait for the non-interactive installer to finished
    """

    name = "installer-wait"
    description = "installer wait"
    summary = "wait for task to finish match arbitrary string"

    def __init__(self):
        super().__init__()
        self.type = "grub"

    def validate(self):
        super().validate()
        if "boot_finished" not in self.parameters:
            self.errors = "Missing boot_finished string"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        wait_string = self.parameters["boot_finished"]
        msg = wait_string if isinstance(wait_string, str) else ", ".join(wait_string)
        self.logger.debug(
            "Not expecting a shell, so waiting for boot_finished: %s", msg
        )
        connection.prompt_str = wait_string
        self.wait(connection)
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection
