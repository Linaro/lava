# Copyright 2019-2020 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
#         Franck Lenormand <franck.lenormand@nxp.com>
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
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.actions.deploy.apply_overlay import (
    ApplyOverlayImage,
    ApplyOverlaySparseImage,
)
from lava_dispatcher.actions.deploy.download import DownloaderAction


# pylint: disable=too-many-return-statements,too-many-instance-attributes,missing-docstring
class UUU(Deployment):
    """
    Strategy class for a UUU deployment.
    Downloads images and apply overlay if needed.
    """

    compatibility = 1
    name = "uuu"

    @classmethod
    def action(cls):
        return UUUAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "uuu":
            return False, '"to" parameter is not "uuu"'
        if "deploy" not in device["actions"]:
            return False, '"deploy" is not in the device configuration actions'
        if "images" not in parameters:
            return False, "'images' not in deploy parameters"
        if "boot" not in parameters["images"].keys():
            return False, "'boot' image is required, not found in 'images' parameter"
        return True, "accepted"


class UUUAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    name = "uuu-deploy"
    description = "deploy images using uuu"
    summary = "uuu deployment"

    def populate(self, parameters):
        self.parameters = parameters
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())
        path = self.mkdtemp()

        images_param = dict(parameters["images"])
        images = list(images_param.keys())

        self.set_namespace_data(
            action="uuu-deploy", label="uuu-images", key="images_names", value=images
        )

        for image in images:
            self.pipeline.add_action(
                DownloaderAction(image, path=path, params=parameters["images"][image])
            )
            if images_param[image].get("apply-overlay", False):
                if self.test_needs_overlay(parameters):
                    if images_param[image].get("sparse", False):
                        self.pipeline.add_action(
                            ApplyOverlaySparseImage(image_key=image)
                        )
                    else:
                        self.pipeline.add_action(ApplyOverlayImage(image_key=image))
