# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import (
    ApplyOverlayGuest,
    ApplyOverlayTftp,
)
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.utils.compression import untar_file

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class DeployImagesAction(Action):  # FIXME: Rename to DeployPosixImages
    name = "deployimages"
    description = "deploy images using guestfs"
    summary = "deploy images"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        path = self.mkdtemp()

        if self.test_needs_overlay(parameters):
            # idempotent, includes testdef
            self.pipeline.add_action(OverlayAction(self.job))
            self.pipeline.add_action(ApplyOverlayGuest(self.job))
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment(self.job))

        if "uefi" in parameters:
            uefi_path = self.mkdtemp()
            self.pipeline.add_action(
                DownloaderAction(self.job, "uefi", uefi_path, params=parameters["uefi"])
            )
            # uefi option of QEMU needs a directory, not the filename
            self.set_namespace_data(
                action=self.name,
                label="image",
                key="uefi_dir",
                value=uefi_path,
                parameters=parameters,
            )
            # alternatively use the -bios option and standard image args
        for image in parameters["images"].keys():
            self.pipeline.add_action(
                DownloaderAction(
                    self.job, image, path, params=parameters["images"][image]
                )
            )


class DeployQemuNfsAction(Action):
    name = "deploy-qemu-nfs"
    description = "deploy qemu with NFS"
    summary = "deploy NFS for QEMU"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        path = self.mkdtemp()
        if "uefi" in parameters:
            uefi_path = self.mkdtemp()
            self.pipeline.add_action(
                DownloaderAction(self.job, "uefi", uefi_path, params=parameters["uefi"])
            )
            # uefi option of QEMU needs a directory, not the filename
            self.set_namespace_data(
                action=self.name,
                label="image",
                key="uefi_dir",
                value=uefi_path,
                parameters=parameters,
            )
            # alternatively use the -bios option and standard image args
        for image in parameters["images"].keys():
            self.pipeline.add_action(
                DownloaderAction(
                    self.job, image, path, params=parameters["images"][image]
                )
            )
        self.pipeline.add_action(ExtractNfsAction(self.job))
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction(self.job))
            self.pipeline.add_action(ApplyOverlayTftp(self.job))
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment(self.job))


class ExtractNfsAction(Action):
    name = "qemu-nfs-deploy"
    description = "deploy nfsrootfs for QEMU"
    summary = "NFS deployment for QEMU"

    def __init__(self, job: Job):
        super().__init__(job)
        self.param_key = "nfsrootfs"
        self.file_key = "nfsroot"
        self.extra_compression = ["xz"]
        self.use_tarfile = True
        self.use_lzma = False

    def validate(self):
        super().validate()
        if not self.valid:
            return
        if not self.parameters["images"].get(self.param_key):  # idempotency
            return
        if not self.get_namespace_data(
            action="download-action", label=self.param_key, key="file"
        ):
            self.errors = "no file specified extract as %s" % self.param_key
        if "prefix" in self.parameters["images"][self.param_key]:
            prefix = self.parameters["images"][self.param_key]["prefix"]
            if prefix.startswith("/"):
                self.errors = "prefix must not be an absolute path"
            if not prefix.endswith("/"):
                self.errors = "prefix must be a directory and end with /"

    def run(self, connection, max_end_time):
        if not self.parameters["images"].get(self.param_key):  # idempotency
            return connection
        connection = super().run(connection, max_end_time)
        root = self.get_namespace_data(
            action="download-action", label=self.param_key, key="file"
        )
        root_dir = self.mkdtemp()
        untar_file(root, root_dir)
        self.set_namespace_data(
            action="extract-rootfs", label="file", key=self.file_key, value=root_dir
        )
        self.logger.debug("Extracted %s to %s", self.file_key, root_dir)

        if "prefix" in self.parameters["images"][self.param_key]:
            prefix = self.parameters["images"][self.param_key]["prefix"]
            self.logger.warning(
                "Adding '%s' prefix, any other content will not be visible.", prefix
            )

            # Grab the path already defined in super().run() and add the prefix
            root_dir = self.get_namespace_data(
                action="extract-rootfs", label="file", key=self.file_key
            )
            root_dir = os.path.join(root_dir, prefix)
            # sets the directory into which the overlay is unpacked and which
            # is used in the substitutions into the bootloader command string.
            self.set_namespace_data(
                action="extract-rootfs", label="file", key=self.file_key, value=root_dir
            )
        return connection
