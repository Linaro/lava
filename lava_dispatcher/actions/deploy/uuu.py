# Copyright 2019-2020 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
#         Franck Lenormand <franck.lenormand@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import (
    ApplyOverlayImage,
    ApplyOverlaySparseImage,
)
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment


# pylint: disable=too-many-return-statements,too-many-instance-attributes,missing-docstring
class UUU(Deployment):
    """
    Strategy class for a UUU deployment.
    Downloads images and apply overlay if needed.
    """

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


class UUUAction(Action):
    name = "uuu-deploy"
    description = "deploy images using uuu"
    summary = "uuu deployment"

    def populate(self, parameters):
        self.parameters = parameters
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())
        path = self.mkdtemp()
        self.set_namespace_data(
            action="uuu-deploy", label="uuu-images", key="root_location", value=path
        )

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
                    use_root_part = (
                        images_param[image].get("root_partition") is not None
                    )
                    if images_param[image].get("sparse", False):
                        self.pipeline.add_action(
                            ApplyOverlaySparseImage(image_key=image)
                        )
                    else:
                        self.pipeline.add_action(
                            ApplyOverlayImage(
                                image_key=image, use_root_partition=use_root_part
                            )
                        )
