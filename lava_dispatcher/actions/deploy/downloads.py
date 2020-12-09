# -*- coding: utf-8 -*-
# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

from pathlib import Path
from lava_common.constants import LAVA_DOWNLOADS
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloadAction
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.utils.docker import DockerRun


class Downloads(Deployment):
    """
    Strategy class for a download deployment.
    Just downloads files, and that's it.
    """

    compatibility = 1
    name = "downloads"

    @classmethod
    def action(cls):
        return DownloadsAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "downloads":
            return False, '"to" parameter is not "downloads"'
        return True, "accepted"


class DownloadsAction(DownloadAction):
    name = "downloads"
    description = "Just downloads files"
    summmary = "downloads files"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        namespace = parameters["namespace"]
        download_dir = Path(self.job.tmp_dir) / "downloads" / namespace
        for image in sorted(parameters["images"].keys()):
            self.pipeline.add_action(
                DownloaderAction(
                    image,
                    download_dir,
                    params=parameters["images"][image],
                    uniquify=parameters.get("uniquify", False),
                )
            )

        postprocess = parameters.get("postprocess")
        if postprocess:
            if postprocess.get("docker"):
                self.pipeline.add_action(PostprocessWithDocker(download_dir))

        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())


class PostprocessWithDocker(Action):
    """
    Modify images from within a Docker container
    """

    name = "download-postprocess-docker"
    description = "Postprocess downloaded images with Docker"
    summary = "download-postprocess"

    def __init__(self, path):
        super().__init__()
        self.path = Path(path)
        self.steps = []

    def populate(self, parameters):
        self.docker_parameters = parameters.get("postprocess", {}).get("docker", {})
        self.steps = self.docker_parameters.get("steps", [])

    def validate(self):
        res = True
        if not self.steps:
            self.errors.append("postprocessing steps missing")
            res = False
        return res

    def run(self, connection, max_end_time):
        job_id = self.job.job_id

        script = ["#!/bin/sh", "exec 2>&1", "set -ex"]

        # Export data generated during run of the Pipeline like NFS settings
        if self.job.device:
            for key in self.job.device["dynamic_data"]:
                script.append(
                    "export %s='%s'" % (key, self.job.device["dynamic_data"][key])
                )

        script = script + self.steps
        script = "\n".join(script) + "\n"

        scriptfile = self.path / "postprocess.sh"
        scriptfile.write_text(script)
        scriptfile.chmod(0o755)

        docker = DockerRun.from_parameters(self.docker_parameters)
        docker.add_device("/dev/kvm", skip_missing=True)
        docker.bind_mount(self.path, LAVA_DOWNLOADS)

        docker.hostname("lava")
        docker.workdir(LAVA_DOWNLOADS)

        docker.run(f"{LAVA_DOWNLOADS}/postprocess.sh", action=self)

        return connection
