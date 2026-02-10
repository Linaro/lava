# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.connections.serial import ConnectDevice


class RecoveryModeAction(Action):
    name = "deploy-recovery-mode"
    description = "deploy firmware by switching to recovery mode"
    summary = "deploy firmware in recovery mode"

    def populate(self, parameters):
        super().populate(parameters)
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        recovery = self.job.device["actions"]["deploy"]["methods"]["recovery"]
        recovery_dir = self.mkdtemp()
        for image_key, image_params in parameters["images"].items():
            self.pipeline.add_action(
                DownloaderAction(self.job, image_key, recovery_dir, params=image_params)
            )

        tags = []
        if "tags" in recovery:
            tags = recovery["tags"]
        if "serial" in tags:
            # might not be a usable shell here, just power on.
            # FIXME: if used, FastbootAction must not try to reconnect
            self.pipeline.add_action(ConnectDevice(self.job))
