# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class FVP(Deployment):
    name = "fvp"

    @classmethod
    def action(cls, job: Job) -> Action:
        return FVPDeploy(job)

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

    def __init__(self, job: Job):
        super().__init__(job)
        self.suffix = None
        self.image_path = None

    def validate(self):
        super().validate()
        if "images" not in self.parameters.keys():
            raise JobError("No 'images' specified on FVP deploy")
        for image_key, image_params in self.parameters["images"].items():
            if "overlays" in image_params:
                if self.parameters.get("format", None) == "disk":
                    if "partition" not in image_params:
                        self.errors = "Missing partition value for 'overlays' value for FVPDeploy."

    def populate(self, parameters):
        self.image_path = self.mkdtemp()
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction(self.job))
        uniquify = parameters.get("uniquify", True)
        if "images" in parameters:
            if not isinstance(parameters["images"], dict):
                raise JobError("'deploy.images' should be a dictionary")
            for k in parameters["images"].keys():
                self.pipeline.add_action(
                    DownloaderAction(
                        self.job,
                        k,
                        self.image_path,
                        parameters["images"][k],
                        uniquify=uniquify,
                    )
                )
