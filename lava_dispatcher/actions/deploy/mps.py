# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Dean Arnold <dean.arnold@linaro.org>
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

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os
import shutil
from lava_dispatcher.action import Action, Pipeline
from lava_common.exceptions import InfrastructureError
from lava_dispatcher.logical import Deployment
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.connections.serial import DisconnectDevice
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.power import PowerOff
from lava_dispatcher.utils.udev import WaitUSBMassStorageDeviceAction
from lava_dispatcher.actions.deploy.vemsd import (
    MountVExpressMassStorageDevice,
    ExtractVExpressRecoveryImage,
    DeployVExpressRecoveryImage,
    UnmountVExpressMassStorageDevice,
)


class Mps(Deployment):
    """
    Strategy class for a booting Arm MPS devices.
    Downloads board recovery image and deploys to target
    """

    compatibility = 1
    name = "mps"

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = MpsAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if "mps" not in device["actions"]["deploy"]["methods"]:
            return False, '"mps" was not in the device configuration deploy methods'
        if "to" not in parameters:
            return False, '"to" was not in parameters'
        if parameters["to"] != "mps":
            return False, '"to" was not "mps"'
        if "usb_filesystem_label" not in device:
            return False, '"usb_filesystem_label" is not in the device configuration'
        return True, "accepted"


class MpsAction(DeployAction):
    """
    Action for deploying firmware to a MPS board in the form
    of a board recovery image.  Recovery images must have AUTORUN
    set to true in config.txt in order for the device to come to
    a prompt after reboot.
    """

    name = "mps-deploy"
    description = "deploy image to MPS device"
    summary = "MPS device image deployment"

    def validate(self):
        super().validate()
        if "images" not in self.parameters:
            self.errors = "Missing 'images'"
            return
        images = self.parameters["images"]
        if "recovery_image" not in images and "test_binary" not in images:
            self.errors = "Missing 'recovery_image' or 'test_binary'"

    def populate(self, parameters):
        download_dir = self.mkdtemp()
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        self.internal_pipeline.add_action(DisconnectDevice())
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(WaitUSBMassStorageDeviceAction())
        for image in parameters["images"].keys():
            self.internal_pipeline.add_action(
                DownloaderAction(image, path=download_dir)
            )
        self.internal_pipeline.add_action(MountVExpressMassStorageDevice())
        if "recovery_image" in parameters["images"].keys():
            self.internal_pipeline.add_action(ExtractVExpressRecoveryImage())
            self.internal_pipeline.add_action(DeployVExpressRecoveryImage())
        if "test_binary" in parameters["images"].keys():
            self.internal_pipeline.add_action(DeployMPSTestBinary())
        self.internal_pipeline.add_action(UnmountVExpressMassStorageDevice())
        self.internal_pipeline.add_action(PowerOff())


class DeployMPSTestBinary(Action):
    """
    Copies test binary to MPS device and renames if required
    """

    name = "deploy-mps-test-binary"
    description = "deploy test binary to usb msd"
    summary = "copy test binary to MPS device and rename if required"

    def __init__(self):
        super().__init__()
        self.param_key = "test_binary"

    def validate(self):
        super().validate()
        if not self.parameters["images"].get(self.param_key):
            self.errors = "Missing '%s' in 'images'" % self.param_key

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        mount_point = self.get_namespace_data(
            action="mount-vexpress-usbmsd", label="vexpress-fw", key="mount-point"
        )
        try:
            os.path.realpath(mount_point)
        except OSError:
            raise InfrastructureError("Unable to locate mount point: %s" % mount_point)

        dest = os.path.join(
            mount_point, self.parameters["images"][self.param_key].get("rename", "")
        )
        test_binary = self.get_namespace_data(
            action="download-action", label=self.param_key, key="file"
        )
        self.logger.debug("Copying %s to %s", test_binary, dest)
        shutil.copy(test_binary, dest)

        return connection
