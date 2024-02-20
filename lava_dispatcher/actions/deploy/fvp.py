# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment


class FVP(Deployment):
    name = "fvp"

    @classmethod
    def action(cls):
        return FVPDeploy()

    @classmethod
    def accepts(cls, device, parameters):
        to = parameters.get("to")
        if to != "fvp":
            return False, "'to' was not fvp"
        return True, "accepted"


class FVPDeploy(Action):
    name = "fvp-deploy"
    description = "Download images for use with fvp"
    summary = "download images for use with fvp"

    def __init__(self):
        super().__init__()
        self.suffix = None
        self.image_path = None

    def validate(self):
        super().validate()
        if "images" not in self.parameters.keys():
            raise JobError("No 'images' specified on FVP deploy")
        for image in self.parameters["images"]:
            if "overlays" in self.parameters["images"][image]:
                if self.parameters.get("format", None) == "disk":
                    if "partition" not in self.parameters["images"][image]:
                        self.errors = "Missing partition value for 'overlays' value for FVPDeploy."

    def populate(self, parameters):
        self.image_path = self.mkdtemp()
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())
        uniquify = parameters.get("uniquify", True)
        if "images" in parameters:
            if not isinstance(parameters["images"], dict):
                raise JobError("'deploy.images' should be a dictionary")
            for k in sorted(parameters["images"].keys()):
                self.pipeline.add_action(
                    DownloaderAction(
                        k, self.image_path, parameters["images"][k], uniquify=uniquify
                    )
                )
