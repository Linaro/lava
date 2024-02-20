# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Arnold <dean.arnold@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, BootHasMixin, OverlayUnpack
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import PreOs, PrePower, ResetDevice
from lava_dispatcher.shell import ExpectShellSession


class Minimal(Boot):
    @classmethod
    def action(cls):
        return MinimalBoot()

    @classmethod
    def accepts(cls, device, parameters):
        if "minimal" not in device["actions"]["boot"]["methods"]:
            return False, '"minimal" was not in device configuration boot methods'
        if parameters["method"] != "minimal":
            return False, '"method" was not "minimal"'
        return True, "accepted"


class MinimalBoot(BootHasMixin, RetryAction):
    name = "minimal-boot"
    description = "connect and reset device"
    summary = "connect and reset device"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ConnectDevice())
        if parameters.get("pre_power_command", False):
            self.pipeline.add_action(PrePower())
        if parameters.get("pre_os_command", False):
            self.pipeline.add_action(PreOs())
        if parameters.get("reset", True):
            self.pipeline.add_action(ResetDevice())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack())
                self.pipeline.add_action(ExportDeviceEnvironment())
