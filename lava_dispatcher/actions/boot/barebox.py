# Copyright (C) 2019 Pengutronix e.K
#
# Author: Michael Grzeschik <mgr@pengutronix.de>
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

from lava_common.exceptions import ConfigurationError
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.actions.boot import (
    BootAction,
    AutoLoginAction,
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    OverlayUnpack,
    BootloaderInterruptAction,
)
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot
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

    compatibility = 1

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = BareboxAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "barebox":
            return False, '"method" was not "barebox"'
        if "commands" not in parameters:
            raise ConfigurationError("commands not specified in boot parameters")
        if "barebox" in device["actions"]["boot"]["methods"]:
            return True, "accepted"
        return False, '"barebox" was not in the device configuration boot methods'


class BareboxAction(BootAction):
    """
    Wraps the Retry Action to allow for actions which precede
    the reset, e.g. Connect.
    """

    name = "barebox-action"
    description = "interactive barebox action"
    summary = "pass barebox commands"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        # customize the device configuration for this job
        self.internal_pipeline.add_action(BootloaderCommandOverlay())
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(BareboxRetry())


class BareboxRetry(BootAction):

    name = "barebox-retry"
    description = "interactive barebox retry action"
    summary = "barebox commands with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        # establish a new connection before trying the reset
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(BootloaderInterruptAction())
        self.internal_pipeline.add_action(BootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())

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
