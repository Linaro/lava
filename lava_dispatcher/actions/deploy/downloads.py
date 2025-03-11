# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from pathlib import Path
from shutil import copy
from typing import TYPE_CHECKING

from lava_common.constants import LAVA_DOWNLOADS
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloadAction, DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.utils.docker import DockerRun
from lava_dispatcher.utils.network import dispatcher_ip

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class DownloadsAction(DownloadAction):
    name = "downloads"
    description = "Just downloads files"
    summary = "downloads files"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)

        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction(self.job))

        namespace = parameters["namespace"]
        download_dir = Path(self.job.tmp_dir) / "downloads" / namespace
        for image_key, image_params in parameters["images"].items():
            self.pipeline.add_action(
                DownloaderAction(
                    self.job,
                    image_key,
                    download_dir,
                    params=image_params,
                    uniquify=parameters.get("uniquify", False),
                )
            )

        postprocess = parameters.get("postprocess")
        if postprocess:
            if postprocess.get("docker"):
                self.pipeline.add_action(PostprocessWithDocker(self.job, download_dir))


class PostprocessWithDocker(Action):
    """
    Modify images from within a Docker container
    """

    name = "download-postprocess-docker"
    description = "Postprocess downloaded images with Docker"
    summary = "download-postprocess"

    def __init__(self, job: Job, path: Path):
        super().__init__(job)
        self.path = path
        self.steps: list[str] = []

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
        script = ["#!/bin/sh", "exec 2>&1", "set -ex"]

        # Export data generated during run of the Pipeline like NFS settings
        if self.job.device:
            for key in self.job.device["dynamic_data"]:
                script.append(
                    "export %s='%s'" % (key, self.job.device["dynamic_data"][key])
                )
        # Export job and dispatcher env vars.
        environment = self.job.parameters.get("environment", {})
        environment["LAVA_JOB_ID"] = self.job.job_id
        environment["LAVA_DISPATCHER_IP"] = dispatcher_ip(
            self.job.parameters["dispatcher"]
        )
        for key, value in environment.items():
            script.append("export %s='%s'" % (key, value))

        script = script + self.steps
        script = "\n".join(script) + "\n"

        scriptfile = self.path / "postprocess.sh"
        scriptfile.write_text(script)
        scriptfile.chmod(0o755)

        # make overlay available in the downloads directory
        # Note: overlay filename is not constant
        overlay_full_path = self.get_namespace_data(
            action="compress-overlay", label="output", key="file"
        )
        if overlay_full_path:
            copy(overlay_full_path, self.path)

        docker = DockerRun.from_parameters(self.docker_parameters, self.job)
        docker.add_device("/dev/kvm", skip_missing=True)
        docker.bind_mount(self.path, LAVA_DOWNLOADS)

        docker.workdir(LAVA_DOWNLOADS)

        docker.run(
            f"{LAVA_DOWNLOADS}/postprocess.sh",
            action=self,
            error_msg="Post-processing of downloads failed",
        )

        return connection
