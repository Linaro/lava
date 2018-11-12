# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

from lava_dispatcher.action import Pipeline
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.actions.boot import (
    BootAction,
    BootloaderCommandsAction,
    BootloaderCommandOverlay,
    BootloaderInterruptAction,
)
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.connections.serial import ConnectDevice


class BootBootloader(Boot):
    compatibility = 4

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = BootBootloaderAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

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


class BootBootloaderAction(BootAction):

    name = "boot-bootloader"
    description = "boot to bootloader"
    summary = "boot bootloader"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(
            BootloaderCommandOverlay(method=parameters["bootloader"])
        )
        self.internal_pipeline.add_action(BootBootloaderRetry())


class BootBootloaderRetry(RetryAction):

    name = "boot-bootloader-retry"
    description = "boot to bootloader with retry"
    summary = "boot bootloader retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(
            BootloaderInterruptAction(method=parameters["bootloader"])
        )
        self.internal_pipeline.add_action(
            BootloaderCommandsAction(
                expect_final=False, method=parameters["bootloader"]
            )
        )
