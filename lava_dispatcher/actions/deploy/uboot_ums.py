# Copyright (C) 2018 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import ApplyOverlayImage
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment


class UBootUMS(Deployment):
    """
    Strategy class for a UBoot USB Mass Storage deployment.
    Downloads the relevant parts, and applies the test overlay into the image.
    """

    name = "uboot-ums"

    @classmethod
    def action(cls):
        return UBootUMSAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "u-boot-ums":
            return False, '"to" parameter is not "u-boot-ums"'
        if "deploy" not in device["actions"]:
            return False, '"deploy" is not in the device configuration actions'
        if "image" not in parameters:
            return False, '"image" was not in the deploy parameters'
        if "u-boot-ums" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"u-boot-ums" was not in the device configuration deploy methods"'


class UBootUMSAction(Action):
    name = "uboot-ums-deploy"
    description = "download image and deploy using uboot mass storage emulation"
    summary = "uboot-ums deployment"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        path = self.mkdtemp()
        self.pipeline.add_action(
            DownloaderAction("image", path=path, params=parameters["image"])
        )
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())
            self.pipeline.add_action(ApplyOverlayImage())
            if self.test_needs_deployment(parameters):
                self.pipeline.add_action(DeployDeviceEnvironment())
