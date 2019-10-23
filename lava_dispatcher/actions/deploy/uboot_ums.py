# Copyright (C) 2018 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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

from lava_dispatcher.logical import Deployment
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.actions.deploy.apply_overlay import ApplyOverlayImage
from lava_dispatcher.actions.deploy.download import DownloaderAction


class UBootUMS(Deployment):
    """
    Strategy class for a UBoot USB Mass Storage deployment.
    Downloads the relevant parts, and applies the test overlay into the image.
    """

    compatibility = 1
    name = "uboot-ums"

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = UBootUMSAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

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


class UBootUMSAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    name = "uboot-ums-deploy"
    description = "download image and deploy using uboot mass storage emulation"
    summary = "uboot-ums deployment"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        path = self.mkdtemp()
        self.pipeline.add_action(DownloaderAction("image", path=path))
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())
            self.pipeline.add_action(ApplyOverlayImage())
            if self.test_needs_deployment(parameters):
                self.pipeline.add_action(DeployDeviceEnvironment())
