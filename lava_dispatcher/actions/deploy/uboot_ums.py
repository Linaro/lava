# Copyright (C) 2018 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import ApplyOverlayImage
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction


class UBootUMSAction(Action):
    name = "uboot-ums-deploy"
    description = "download image and deploy using uboot mass storage emulation"
    summary = "uboot-ums deployment"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        path = self.mkdtemp()
        self.pipeline.add_action(
            DownloaderAction(self.job, "image", path=path, params=parameters["image"])
        )
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction(self.job))
            self.pipeline.add_action(ApplyOverlayImage(self.job))
            if self.test_needs_deployment(parameters):
                self.pipeline.add_action(DeployDeviceEnvironment(self.job))
