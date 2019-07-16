# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

from lava_common.exceptions import ConfigurationError
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import BootAction, AutoLoginAction, OverlayUnpack
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.serial import ConnectShell
from lava_dispatcher.logical import Boot
from lava_dispatcher.shell import ExpectShellSession


class SecondaryShell(Boot):
    """
    SecondaryShell method can be used by a variety of other boot methods to
    read from the kernel console independently of the shell interaction
    required to interact with the bootloader and test shell.
    It is also the updated way to connect to the primary console.
    """

    compatibility = 6

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = SecondaryShellAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if "method" not in parameters:
            raise ConfigurationError("method not specified in boot parameters")
        if parameters["method"] != "new_connection":
            return False, "new_connection not in method"
        if "actions" not in device:
            raise ConfigurationError("Invalid device configuration")
        if "boot" not in device["actions"]:
            return False, "boot not in device actions"
        if "methods" not in device["actions"]["boot"]:
            raise ConfigurationError("Device misconfiguration")
        if "method" not in parameters:
            return False, "no boot method"
        return True, "accepted"


class SecondaryShellAction(BootAction):

    name = "secondary-shell-action"
    description = "Connect to a secondary shell on specified hardware"
    summary = "connect to a specified second shell"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        name = parameters["connection"]
        self.internal_pipeline.add_action(ConnectShell(name=name))
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())
