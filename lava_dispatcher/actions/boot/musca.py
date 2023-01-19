# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
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
from lava_dispatcher.actions.boot import (
    AutoLoginAction,
    BootHasMixin,
    ExportDeviceEnvironment,
    OverlayUnpack,
)
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.udev import WaitUSBSerialDeviceAction


class Musca(Boot):

    compatibility = 1

    @classmethod
    def action(cls):
        return MuscaBoot()

    @classmethod
    def accepts(cls, device, parameters):
        if "musca" not in device["actions"]["boot"]["methods"]:
            return False, '"musca" was not in device configuration boot methods'
        if "method" not in parameters:
            return False, '"method" was not in parameters'
        if parameters["method"] != "musca":
            return False, '"method" was not "musca"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class MuscaBoot(BootHasMixin, RetryAction):

    name = "musca-boot"
    description = "power device and trigger software to run"
    summary = "power device and trigger software to run"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(WaitUSBSerialDeviceAction())
        self.pipeline.add_action(ConnectDevice())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
        if self.test_has_shell(parameters):
            self.pipeline.add_action(ExpectShellSession())
            if "transfer_overlay" in parameters:
                self.pipeline.add_action(OverlayUnpack())
            self.pipeline.add_action(ExportDeviceEnvironment())
