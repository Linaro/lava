# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, BootHasMixin, OverlayUnpack
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.serial import ConnectShell
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.shell import ExpectShellSession


class SecondaryShellAction(BootHasMixin, RetryAction):
    name = "secondary-shell-action"
    description = "Connect to a secondary shell on specified hardware"
    summary = "connect to a specified second shell"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        name = parameters["connection"]
        self.pipeline.add_action(ConnectShell(self.job, name=name))
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction(self.job, booting=False))
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession(self.job))
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack(self.job))
                self.pipeline.add_action(ExportDeviceEnvironment(self.job))
