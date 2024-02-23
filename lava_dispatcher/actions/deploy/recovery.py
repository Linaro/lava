# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import CopyToLxcAction, DownloaderAction
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Deployment


class RecoveryModeAction(Action):
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
    name = "recovery-mode"

    @classmethod
    def action(cls):
        return RecoveryModeAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "recovery" not in device["actions"]["deploy"]["methods"]:
            return False, "'recovery' not in the device configuration deploy methods"
        if parameters["to"] != "recovery":
            return False, '"to" parameter is not "recovery"'
        if "images" not in parameters:
            return False, '"images" is not in the deployment parameters'
        return True, "accepted"
