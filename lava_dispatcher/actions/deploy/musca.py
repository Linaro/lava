# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os
import shutil

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.vemsd import (
    MountDeviceMassStorageDevice,
    UnmountVExpressMassStorageDevice,
)
from lava_dispatcher.connections.serial import DisconnectDevice
from lava_dispatcher.logical import Deployment, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.udev import wait_udev_changed_event, wait_udev_event


class Musca(Deployment):
    """
    Strategy class for a booting Arm Musca devices.
    Downloads an image and deploys to the board.
    """

    name = "musca"

    @classmethod
    def action(cls):
        return MuscaAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "musca" not in device["actions"]["deploy"]["methods"]:
            return False, '"musca" was not in the device configuration deploy methods'
        if "to" not in parameters:
            return False, '"to" was not in parameters'
        if parameters["to"] != "musca":
            return False, '"to" was not "musca"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class MuscaAction(RetryAction):
    """
    Action for deploying software to a Musca
    """

    name = "musca-deploy"
    description = "deploy image to Musca device"
    summary = "Musca device image deployment"

    def validate(self):
        super().validate()
        if "images" not in self.parameters:
            self.errors = "Missing 'images'"
            return
        images = self.parameters["images"]
        if "test_binary" not in images:
            self.errors = "Missing 'test_binary'"

    def populate(self, parameters):
        download_dir = self.mkdtemp()
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # Musca will autoboot previously deployed binaries
        # Therefore disconnect serial to avoid clutter.
        self.pipeline.add_action(DisconnectDevice())
        # If we don't run with a strict schema, it is possible to pass validation with warnings
        # even without the required 'test_binary' field.
        # Therefore, ensure the DownloaderAction.populate does not fail, and catch this at validate step.
        image_params = parameters.get("images", {}).get("test_binary")
        if image_params:
            self.pipeline.add_action(
                DownloaderAction("test_binary", path=download_dir, params=image_params)
            )
        # Turn on
        self.pipeline.add_action(ResetDevice())
        # Wait for storage
        self.pipeline.add_action(WaitMuscaMassStorageAction())

        # Deploy test binary
        self.pipeline.add_action(MountMuscaMassStorageDevice())
        self.pipeline.add_action(DeployMuscaTestBinary())
        self.pipeline.add_action(UnmountMuscaMassStorageDevice())

        # Check for FAIL.TXT to check if we were successful
        self.pipeline.add_action(WaitMuscaMassStorageAction(udev_action="change"))
        self.pipeline.add_action(MountMuscaMassStorageDevice())
        self.pipeline.add_action(CheckMuscaFlashAction())
        self.pipeline.add_action(UnmountMuscaMassStorageDevice())


class UnmountMuscaMassStorageDevice(UnmountVExpressMassStorageDevice):
    """
    Unmount Musca USB mass storage device on the dispatcher
    """

    name = "unmount-musca-usbmsd"
    description = "unmount musca usb msd"
    summary = "unmount musca usb mass storage device"

    def __init__(self):
        super().__init__()
        self.namespace_label = "musca-usb"
        self.namespace_action = "mount-musca-usbmsd"


class WaitMuscaMassStorageAction(Action):
    """
    Waits for the Musca storage device to be presented to the dispatcher.
    Often, 2 events are generated. The initial event may not have details about
    the filesystem, so if we attempt to mount at this time, the OS doesn't know
    how to mount due to lack of filesystem information.
    Therefore, ensure we listen to the second event, where the filesystem is
    known. ID_FS_VERSION=FAT16 is therefore also searched for as well as the
    disk ID.
    """

    name = "wait-musca-path"
    description = "wait for musca mass storage"
    summary = "wait for musca mass storage"

    def __init__(self, udev_action="add"):
        super().__init__()
        self.udev_action = udev_action
        # Ensure that we only trigger once FS details are known
        self.match_dict = {"ID_FS_VERSION": "FAT16"}
        self.devicepath = ""

    def validate(self):
        super().validate()
        if not isinstance(self.udev_action, str):
            self.errors = "invalid device action"
        if "board_id" not in self.job.device:
            return (
                False,
                '"board_id" is not in the device configuration (ID_SERIAL_SHORT value of serial device)',
            )
        if "id_serial" not in self.job.device["actions"]["deploy"]["methods"]["musca"]:
            return (
                False,
                '"id_serial" not set in device configuration (/dev/disk/by-id/...)',
            )
        self.devicepath = "/dev/disk/by-id/{}".format(
            self.job.device["actions"]["deploy"]["methods"]["musca"]["id_serial"]
        )

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if self.udev_action == "add":
            self.logger.debug("Waiting for device to appear: %s", self.devicepath)
            wait_udev_event(match_dict=self.match_dict, devicepath=self.devicepath)
        elif self.udev_action == "change":
            self.logger.debug("Waiting for device to reappear: %s", self.devicepath)
            wait_udev_changed_event(
                match_dict=self.match_dict, devicepath=self.devicepath
            )
        return connection


class MountMuscaMassStorageDevice(MountDeviceMassStorageDevice):
    """
    Mounts Musca mass storage device on the dispatcher.
    The device is identified by a id.
    """

    name = "mount-musca-usbmsd"
    description = "mount musca usb msd"
    summary = "mount musca usb mass storage device on the dispatcher"

    def __init__(self):
        super().__init__()
        self.disk_identifier = None
        self.disk_identifier_type = "id"
        self.namespace_label = "musca-usb"

    def validate(self):
        super().validate()
        if "id_serial" not in self.job.device["actions"]["deploy"]["methods"]["musca"]:
            self.errors = "id_serial parameter not set for actions.deploy.methods.musca"
        self.disk_identifier = self.job.device["actions"]["deploy"]["methods"]["musca"][
            "id_serial"
        ]
        if not isinstance(self.disk_identifier, str):
            self.errors = "USB ID unset for Musca"


class DeployMuscaTestBinary(Action):
    """
    Copies test binary to Musca device
    """

    name = "deploy-musca-test-binary"
    description = "deploy test binary to usb msd"
    summary = "copy test binary to Musca device"

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
            action="mount-musca-usbmsd", label="musca-usb", key="mount-point"
        )
        if not os.path.exists(mount_point):
            raise InfrastructureError("Unable to locate mount point: %s" % mount_point)

        test_binary = self.get_namespace_data(
            action="download-action", label=self.param_key, key="file"
        )
        dest = os.path.join(mount_point)
        self.logger.debug("Copying %s to %s", test_binary, dest)
        shutil.copy(test_binary, dest)

        return connection


class DeployMuscaAutomationAction(Action):
    """
    Copies automation file to Musca device

    Not actually used in this flow, but allows for creation of automation files.
    https://github.com/ARMmbed/DAPLink/blob/master/docs/MSD_COMMANDS.md
    """

    name = "deploy-musca-automation-file"
    description = "deploy automation file to usb msd"
    summary = "copy automation file to Musca device"

    def __init__(self, automation_filename=""):
        super().__init__()
        self.automation_filename = automation_filename

    def validate(self):
        super().validate()
        if not self.automation_filename:
            self.errors = "Musca deploy was not given an automation filename."

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        mount_point = self.get_namespace_data(
            action="mount-musca-usbmsd", label="musca-usb", key="mount-point"
        )
        if not os.path.exists(mount_point):
            raise InfrastructureError("Unable to locate mount point: %s" % mount_point)

        dest = os.path.join(mount_point, self.automation_filename)
        self.logger.debug("Creating empty file %s", dest)
        try:
            with open(dest, "w"):
                pass
        except OSError:
            raise InfrastructureError("Unable to write to %s" % dest)

        return connection


class CheckMuscaFlashAction(Action):
    """
    Checks for a FAIL.TXT file to see if there were flashing issues
    """

    name = "check-musca-flash"
    description = "checks if software flashed to the musca correctly"
    summary = "check for FAIL.TXT on musca"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        mount_point = self.get_namespace_data(
            action="mount-musca-usbmsd", label="musca-usb", key="mount-point"
        )
        if not os.path.realpath(mount_point):
            raise InfrastructureError("Unable to locate mount point: %s" % mount_point)

        fail_file = os.path.join(mount_point, "FAIL.TXT")
        if os.path.exists(fail_file):
            failure_details = ""
            with open(fail_file) as fail_details_file:
                failure_details = fail_details_file.read().strip()
            raise InfrastructureError(
                "Flash failure indicated by presence of FAIL.TXT (Details: %s)"
                % failure_details
            )

        return connection
