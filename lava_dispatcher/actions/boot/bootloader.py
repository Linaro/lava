# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import (
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    BootloaderInterruptAction,
)
from lava_dispatcher.connections.serial import ResetConnection
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.power import ResetDevice


class BootBootloaderRetry(RetryAction):
    name = "boot-bootloader-retry"
    description = "boot to bootloader with retry"
    summary = "boot bootloader retry"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(
            BootloaderCommandOverlay(self.job, method=parameters["bootloader"])
        )
        self.pipeline.add_action(BootBootloaderAction(self.job))


class BootBootloaderAction(Action):
    name = "boot-bootloader"
    description = "boot to bootloader"
    summary = "boot bootloader"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ResetConnection(self.job))
        self.pipeline.add_action(ResetDevice(self.job))
        self.pipeline.add_action(
            BootloaderInterruptAction(self.job, method=parameters["bootloader"])
        )
        self.pipeline.add_action(
            BootloaderCommandsAction(
                self.job, expect_final=False, method=parameters["bootloader"]
            )
        )
