# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.


from lava_dispatcher.logical import Boot
from lava_common.exceptions import InfrastructureError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.power import PowerOn, PowerOff


class RecoveryBoot(Boot):

    compatibility = 4

    @classmethod
    def action(cls):
        return RecoveryBootAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "method" in parameters:
            if parameters["method"] == "recovery":
                return True, "accepted"
        return False, 'boot "method" was not "recovery"'


class RecoveryBootAction(Action):

    name = "recovery-boot"
    description = "handle entering and leaving recovery mode"
    summary = "boot into or out of recovery mode"

    def populate(self, parameters):
        """
        PowerOff commands will include recovery mode switching commands
        so that when jobs end, the device is available.
        Use PowerOn instead of ResetDevice so that the effect of the
        switching is preserved until the recovery boot action which
        specifies the 'exit' command.
        """
        super().populate(parameters)
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if parameters["commands"] == "recovery":
            # only switch into recovery mode with power off.
            self.pipeline.add_action(PowerOff())
            self.pipeline.add_action(SwitchRecoveryCommand(mode="recovery_mode"))
            self.pipeline.add_action(PowerOn())
        elif parameters["commands"] == "exit":
            self.pipeline.add_action(PowerOff())
            self.pipeline.add_action(SwitchRecoveryCommand(mode="recovery_exit"))
            self.pipeline.add_action(PowerOn())
        else:
            self.errors = "Invalid recovery command"


class SwitchRecoveryCommand(Action):

    name = "switch-recovery"
    description = "call commands to switch device into and out of recovery"
    summary = "execute recovery mode commands"
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError

    def __init__(self, mode):
        super().__init__()
        self.recovery = []
        self.mode = mode

    def validate(self):
        super().validate()
        self.recovery = self.job.device["actions"]["deploy"]["methods"]["recovery"]
        if "commands" not in self.recovery:
            self.errors = "Missing commands to enter recovery mode"
        command = self.recovery["commands"].get(self.mode)
        if not command:
            self.errors = "Unable to find %s recovery command" % self.mode

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        command = self.recovery["commands"][self.mode]
        self.logger.info("Switching using '%s' recovery command", self.mode)
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            self.run_cmd(
                cmd, error_msg="Fail to switch device in recovery mode %s" % self.mode
            )
        return connection
