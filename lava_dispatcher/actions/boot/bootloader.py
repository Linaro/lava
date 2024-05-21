# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import (
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    BootloaderInterruptAction,
)
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class BootBootloader(Boot):
    @classmethod
    def action(cls, job: Job) -> Action:
        return BootBootloaderRetry(job)

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "bootloader":
            return False, "'method' was not 'bootloader'"
        if "bootloader" not in parameters:
            return False, "'bootloader' is undefined"
        bootloader = parameters["bootloader"]
        if bootloader not in device["actions"]["boot"]["methods"]:
            return (
                False,
                "boot method '%s' not in the device configuration" % bootloader,
            )
        return True, "accepted"


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
        self.pipeline.add_action(ConnectDevice(self.job))
        self.pipeline.add_action(ResetDevice(self.job))
        self.pipeline.add_action(
            BootloaderInterruptAction(self.job, method=parameters["bootloader"])
        )
        self.pipeline.add_action(
            BootloaderCommandsAction(
                self.job, expect_final=False, method=parameters["bootloader"]
            )
        )
