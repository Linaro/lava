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
from lava_dispatcher.actions.boot import BootAction
from lava_dispatcher.actions.boot import AutoLoginAction
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.udev import WaitUSBSerialDeviceAction


class Musca(Boot):

    compatibility = 1

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = MuscaBoot()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

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


class MuscaBoot(BootAction):

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

    def run(self, connection, max_end_time):
        connection = self.get_namespace_data(
            action="shared", label="shared", key="connection", deepcopy=False
        )
        connection = super().run(connection, max_end_time)
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection
