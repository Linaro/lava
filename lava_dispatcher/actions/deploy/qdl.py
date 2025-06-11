# Copyright 2026 Qualcomm Inc.
#
# Author: Milosz Wasilewski <milosz.wasilewski@oss.qualcomm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import ApplyQDLOverlay
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.utils.compression import decompress_file, untar_file

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class QDLAction(Action):
    name = "qdl-deploy"
    description = "deploy qcomflash tarball using qdl"
    summary = "qdl deployment"

    def __init__(self, job: Job):
        super().__init__(job)
        self.param_key = "qcomflash"
        # - deploy:
        #     rootfs_image: rootfs.img
        #     qcomflash:
        #       url: ...
        #     to: qdl

    def validate(self):
        super().validate()
        if not self.parameters.get(self.param_key):
            self.errors_add(
                f"action {self.name} can't work without {self.param_key} file"
            )

    def populate(self, parameters):
        self.parameters = parameters
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction(self.job))

        namespace = parameters["namespace"]
        download_dir = Path(self.job.tmp_dir) / "qdl" / namespace
        self.set_namespace_data(
            action="qdl-deploy",
            label="qdl-directory",
            key="directory",
            value=download_dir,
        )
        image_params = parameters.get(self.param_key)
        self.pipeline.add_action(
            DownloaderAction(
                self.job,
                self.param_key,
                download_dir,
                params=image_params,
                uniquify=parameters.get("uniquify", False),
            )
        )

        if image_params.get("apply-overlay", False):
            rootfs_image = parameters.get("rootfs_image", "rootfs.img")
            if self.test_needs_overlay(parameters):
                self.pipeline.add_action(
                    ApplyQDLOverlay(
                        self.job,
                        rootfs_image=rootfs_image,
                    )
                )

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        qcomflash_decompressed = self.get_namespace_data(
            action="qdl-deploy",
            label="directory-decompress",
            key="directory-decompress",
        )
        if qcomflash_decompressed:
            return connection

        qcomflash = None
        for action in self.get_namespace_keys(  # pylint: disable=unused-variable
            "download-action"
        ):
            qcomflash = self.get_namespace_data(
                action="download-action", label="qcomflash", key="file"
            )
            break
        if qcomflash is None:
            raise JobError("QCOMflash file missing")

        qdl_dir = self.get_namespace_data(
            action="qdl-deploy", label="qdl-directory", key="directory"
        )
        dest = Path(qdl_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)

        out_path = decompress_file(qcomflash, "gz")
        untar_file(out_path, qdl_dir)

        return connection
