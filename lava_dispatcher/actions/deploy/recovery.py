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

from lava_dispatcher.action import Pipeline
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.actions.deploy.download import DownloaderAction, CopyToLxcAction
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.logical import Deployment


class RecoveryModeAction(DeployAction):

    name = "deploy-recovery-mode"
    description = "deploy firmware by switching to recovery mode"
    summary = "deploy firmware in recovery mode"

    def populate(self, parameters):
        super().populate(parameters)
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        recovery = self.job.device["actions"]["deploy"]["methods"]["recovery"]
        recovery_dir = self.mkdtemp()
        for image in sorted(parameters["images"].keys()):
            self.pipeline.add_action(
                DownloaderAction(
                    image, recovery_dir, params=parameters["images"][image]
                )
            )
        self.pipeline.add_action(CopyToLxcAction())

        tags = []
        if "tags" in recovery:
            tags = recovery["tags"]
        if "serial" in tags:
            # might not be a usable shell here, just power on.
            # FIXME: if used, FastbootAction must not try to reconnect
            self.pipeline.add_action(ConnectDevice())


class RecoveryMode(Deployment):

    compatibility = 4
    name = "recovery-mode"

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = RecoveryModeAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if "recovery" not in device["actions"]["deploy"]["methods"]:
            return False, "'recovery' not in the device configuration deploy methods"
        if parameters["to"] != "recovery":
            return False, '"to" parameter is not "recovery"'
        if "images" not in parameters:
            return False, '"images" is not in the deployment parameters'
        return True, "accepted"
