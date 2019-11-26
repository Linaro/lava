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
import os
import re
import subprocess

from lava_common.exceptions import JobError
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.actions.deploy.apply_overlay import (
    ExtractRamdisk,
    CompressRamdisk,
    InjectIntoDiskImage,
    ApplyOverlayTftp,
    ExtractRamdiskFromDisk,
    ApplyOverlayImage,
)
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment


class FVP(Deployment):

    compatibility = 1
    name = "fvp"

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = FVPDeploy()
        self.action.job = self.job
        self.action.section = self.action_type
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        to = parameters.get("to")
        if to != "fvp":
            return False, "'to' was not fvp"
        return True, "accepted"


class FVPDeploy(DeployAction):  # pylint: disable=too-many-instance-attributes

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
                for overlay in self.parameters["images"][image]["overlays"]:
                    # Supported options:
                    # - This is an image file and a partition is a rootfs
                    # - This is an image file and a ramdisk is contained on a partition
                    # Therefore "partition" should be specified and optionally "ramdisk"
                    if "partition" not in overlay:
                        self.errors = "Missing partition value for 'overlays' value for FVPDeploy."

    def populate(self, parameters):
        self.image_path = self.mkdtemp()
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        if self.test_needs_overlay(parameters):
            self.internal_pipeline.add_action(OverlayAction())
        uniquify = parameters.get("uniquify", True)
        if "images" in parameters:
            for k in sorted(parameters["images"].keys()):
                self.internal_pipeline.add_action(
                    DownloaderAction(k, path=self.image_path, uniquify=uniquify)
                )
                if parameters["images"][k].get("overlays", None):
                    for overlay in parameters["images"][k]["overlays"]:
                        partition = overlay.get("partition")
                        ramdisk = overlay.get("ramdisk", None)
                        if not self.test_needs_overlay(parameters):
                            continue
                        if ramdisk is not None:
                            self.internal_pipeline.add_action(
                                OffsetAction(k, partition_number=partition)
                            )
                            self.internal_pipeline.add_action(
                                ExtractRamdiskFromDisk(file=ramdisk, key=k)
                            )
                            self.internal_pipeline.add_action(
                                ExtractRamdisk(
                                    ramdisk_label=ExtractRamdiskFromDisk.name,
                                    ramdisk_action=ExtractRamdiskFromDisk.name,
                                    force=True,
                                )
                            )
                            self.internal_pipeline.add_action(
                                ApplyOverlayTftp(force_ramdisk=True)
                            )
                            self.internal_pipeline.add_action(
                                CompressRamdisk(
                                    action=ExtractRamdiskFromDisk.name,
                                    label=ExtractRamdiskFromDisk.name,
                                    force=True,
                                )
                            )
                            self.internal_pipeline.add_action(
                                InjectIntoDiskImage(file=ramdisk, key=k)
                            )
                        # Partition should always be specified, see validate.
                        else:
                            self.internal_pipeline.add_action(
                                ApplyOverlayImage(image_key=k, root_partition=partition)
                            )


class OffsetAction(DeployAction):
    """
    Uses the target.deployment_data['lava_test_results_part_attr']
    which, for example, maps to the root_part in the Device config for a qemu.
    The Device object is passed into the parser which uses the action
    parameters to determine the deployment_data parameter of the Device object.
    The calculated offset is dynamic data, stored in the context.
    """

    name = "offset-action"
    description = "calculate offset of the image"
    summary = "offset calculation"

    def __init__(self, key, partition_number=None):
        super().__init__()
        self.key = key
        self.partition_number = partition_number

    def validate(self):
        super().validate()
        if not self.get_namespace_data(
            action="download-action", label=self.key, key="file"
        ):
            self.errors = "no file specified to calculate offset"

    def run(self, connection, max_end_time):
        if self.get_namespace_data(
            action="download-action", label=self.key, key="offset"
        ):
            # idempotency
            return connection
        connection = super().run(connection, max_end_time)
        image = self.get_namespace_data(
            action="download-action", label=self.key, key="file"
        )
        if not os.path.exists(image):
            raise JobError("Not able to mount %s: file does not exist" % image)
        part_data = subprocess.check_output(
            ["/sbin/parted", image, "-m", "-s", "unit", "b", "print"]
        )
        if not part_data:
            raise JobError("Unable to identify offset")
        if not self.partition_number:
            deploy_params = self.job.device["actions"]["deploy"]["methods"]["image"][
                "parameters"
            ]
            self.partition_number = deploy_params[
                self.parameters["deployment_data"]["lava_test_results_part_attr"]
            ]

        # Note that we want to use 0 based index
        # Parted however uses 1 based index.
        # As the qemu image code already uses 0 based index, ensure both are the same
        # for the test writers.
        pattern = re.compile("%d:([0-9]+)B:" % (int(self.partition_number) + 1))
        for line in part_data.splitlines():
            found = re.match(pattern, line.decode())
            if found:
                self.logger.debug(
                    "Found partition %s has offset %s bytes.",
                    self.partition_number,
                    found.group(1),
                )
                self.set_namespace_data(
                    action=self.name, label=self.key, key="offset", value=found.group(1)
                )
        if not self.get_namespace_data(action=self.name, label=self.key, key="offset"):
            raise JobError(  # FIXME: JobError needs a unit test
                "Unable to determine offset for %s" % image
            )
        return connection
