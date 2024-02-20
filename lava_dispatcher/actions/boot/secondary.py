# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, BootHasMixin, OverlayUnpack
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.serial import ConnectShell
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.shell import ExpectShellSession


class SecondaryShell(Boot):
    """
    SecondaryShell method can be used by a variety of other boot methods to
    read from the kernel console independently of the shell interaction
    required to interact with the bootloader and test shell.
    It is also the updated way to connect to the primary console.
    """

    @classmethod
    def action(cls):
        return SecondaryShellAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "new_connection":
            return False, "new_connection not in method"
        if "method" not in parameters:
            return False, "no boot method"
        return True, "accepted"


class SecondaryShellAction(BootHasMixin, RetryAction):
    name = "secondary-shell-action"
    description = "Connect to a secondary shell on specified hardware"
    summary = "connect to a specified second shell"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        name = parameters["connection"]
        self.pipeline.add_action(ConnectShell(name=name))
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction(booting=False))
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack())
                self.pipeline.add_action(ExportDeviceEnvironment())
