# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
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

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment


class FVP(Deployment):

    compatibility = 1
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
            self.errors = "No 'images' specified on FVP deploy"
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
            for k in sorted(parameters["images"].keys()):
                self.pipeline.add_action(
                    DownloaderAction(
                        k, self.image_path, parameters["images"][k], uniquify=uniquify
                    )
                )
