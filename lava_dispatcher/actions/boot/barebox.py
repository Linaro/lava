# Copyright (C) 2019 Pengutronix e.K
#
# Author: Michael Grzeschik <mgr@pengutronix.de>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

from lava_common.exceptions import ConfigurationError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import (
    AutoLoginAction,
    BootHasMixin,
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    BootloaderInterruptAction,
    OverlayUnpack,
)
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.shell import ExpectShellSession


class Barebox(Boot):
    """
    The Barebox method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then interrupt barebox.
    An expect shell session can then be handed over to the BareboxAction.
    self.run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    @classmethod
    def action(cls):
        return BareboxAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "barebox":
            return False, '"method" was not "barebox"'
        if "commands" not in parameters:
            raise ConfigurationError("commands not specified in boot parameters")
        if "barebox" in device["actions"]["boot"]["methods"]:
            return True, "accepted"
        return False, '"barebox" was not in the device configuration boot methods'


class BareboxAction(Action):
    """
    Wraps the Retry Action to allow for actions which precede
    the reset, e.g. Connect.
    """

    name = "barebox-action"
    description = "interactive barebox action"
    summary = "pass barebox commands"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # customize the device configuration for this job
        self.pipeline.add_action(BootloaderCommandOverlay())
        self.pipeline.add_action(ConnectDevice())
        self.pipeline.add_action(BareboxRetry())


class BareboxRetry(BootHasMixin, RetryAction):
    name = "barebox-retry"
    description = "interactive barebox retry action"
    summary = "barebox commands with retry"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # establish a new connection before trying the reset
        self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(BootloaderInterruptAction())
        self.pipeline.add_action(BootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack())
                self.pipeline.add_action(ExportDeviceEnvironment())

    def validate(self):
        super().validate()
        self.set_namespace_data(
            action=self.name,
            label="bootloader_prompt",
            key="prompt",
            value=self.job.device["actions"]["boot"]["methods"]["barebox"][
                "parameters"
            ]["bootloader_prompt"],
        )
