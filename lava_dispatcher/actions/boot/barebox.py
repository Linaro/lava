# Copyright (C) 2019 Pengutronix e.K
#
# Author: Michael Grzeschik <mgr@pengutronix.de>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.
from __future__ import annotations

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
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.shell import ExpectShellSession


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
        self.pipeline.add_action(BootloaderCommandOverlay(self.job))
        self.pipeline.add_action(ConnectDevice(self.job))
        self.pipeline.add_action(BareboxRetry(self.job))


class BareboxRetry(BootHasMixin, RetryAction):
    name = "barebox-retry"
    description = "interactive barebox retry action"
    summary = "barebox commands with retry"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # establish a new connection before trying the reset
        self.pipeline.add_action(ResetDevice(self.job))
        self.pipeline.add_action(BootloaderInterruptAction(self.job))
        self.pipeline.add_action(BootloaderCommandsAction(self.job))
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction(self.job))
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession(self.job))
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack(self.job))
                self.pipeline.add_action(ExportDeviceEnvironment(self.job))

    def validate(self):
        super().validate()
        self.state.barebox.bootloader_prompt = self.job.device["actions"]["boot"][
            "methods"
        ]["barebox"]["parameters"]["bootloader_prompt"]
