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

    @classmethod
    def action(cls):
        return BootloaderAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "ipxe":
            return False, '"method" was not "ipxe"'
        if "ipxe" in device["actions"]["boot"]["methods"]:
            return True, "accepted"
        else:
            return False, '"ipxe" was not in the device configuration boot methods'


class BootloaderAction(Action):
    """
    Wraps the Retry Action to allow for actions which precede
    the reset, e.g. Connect.
    """

    name = "bootloader-action"
    description = "interactive bootloader action"
    summary = "pass boot commands"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # customize the device configuration for this job
        self.pipeline.add_action(BootloaderCommandOverlay())
        self.pipeline.add_action(ConnectDevice())
        self.pipeline.add_action(BootloaderRetry())


class BootloaderRetry(BootHasMixin, RetryAction):

    name = "bootloader-retry"
    description = "interactive uboot retry action"
    summary = "uboot commands with retry"

    def __init__(self):
        super().__init__()
        self.type = "ipxe"
        self.force_prompt = False

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # establish a new connection before trying the reset
        self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(BootloaderInterruptAction())
        # need to look for Hit any key to stop autoboot
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
        if (
            "bootloader_prompt"
            not in self.job.device["actions"]["boot"]["methods"][self.type][
                "parameters"
            ]
        ):
            self.errors = "Missing bootloader prompt for device"
        self.set_namespace_data(
            action=self.name,
            label="bootloader_prompt",
            key="prompt",
            value=self.job.device["actions"]["boot"]["methods"][self.type][
                "parameters"
            ]["bootloader_prompt"],
        )
