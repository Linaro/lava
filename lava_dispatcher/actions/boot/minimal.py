# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Arnold <dean.arnold@linaro.org>
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
from lava_dispatcher.actions.boot import AutoLoginAction, BootAction, OverlayUnpack
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.logical import Boot
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.shell import ExpectShellSession


class Minimal(Boot):

    compatibility = 1

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = MinimalBoot()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if "minimal" not in device["actions"]["boot"]["methods"]:
            return False, '"minimal" was not in device configuration boot methods'
        if "method" not in parameters:
            return False, '"method" was not in parameters'
        if parameters["method"] != "minimal":
            return False, '"method" was not "minimal"'
        return True, "accepted"


class MinimalBoot(BootAction):

    name = "minimal-boot"
    description = "connect and reset device"
    summary = "connect and reset device"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(ResetDevice())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())

    def run(self, connection, max_end_time):
        connection = self.get_namespace_data(
            action="shared", label="shared", key="connection", deepcopy=False
        )
        connection = super().run(connection, max_end_time)
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection
