# Copyright 2019-2020 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
#         Franck Lenormand <franck.lenormand@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import (
    ApplyOverlayImage,
    ApplyOverlaySparseImage,
)
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction


class UUUAction(Action):
    name = "uuu-deploy"
    description = "deploy images using uuu"
    summary = "uuu deployment"

    def populate(self, parameters):
        self.parameters = parameters
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction(self.job))
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
                DownloaderAction(
                    self.job, image, path=path, params=parameters["images"][image]
                )
            )
            if images_param[image].get("apply-overlay", False):
                if self.test_needs_overlay(parameters):
                    use_root_part = (
                        images_param[image].get("root_partition") is not None
                    )
                    if images_param[image].get("sparse", False):
                        self.pipeline.add_action(
                            ApplyOverlaySparseImage(self.job, image_key=image)
                        )
                    else:
                        self.pipeline.add_action(
                            ApplyOverlayImage(
                                self.job,
                                image_key=image,
                                use_root_partition=use_root_part,
                            )
                        )
