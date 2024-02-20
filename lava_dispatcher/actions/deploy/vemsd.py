# Copyright (C) 2017-2019 Linaro Limited
#
# Author: Dean Arnold <dean.arnold@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os
import shutil

from lava_common.constants import VEXPRESS_AUTORUN_INTERRUPT_CHARACTER
from lava_common.exceptions import InfrastructureError, LAVABug
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.lxc import LxcCreateUdevRuleAction
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Deployment, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.compression import decompress_file, untar_file
from lava_dispatcher.utils.filesystem import (
    copy_directory_contents,
    remove_directory_contents,
)
from lava_dispatcher.utils.udev import WaitUSBMassStorageDeviceAction


class VExpressMsd(Deployment):
    """
    Strategy class for a Versatile Express firmware deployment.
    Downloads Versatile Express board recovery image and deploys
    to target device
    """

    name = "vemsd"

    @classmethod
    def action(cls):
        return VExpressMsdRetry()

    @classmethod
    def uses_deployment_data(cls):
        # recovery image deployment does not involve an OS
        return False

    @classmethod
    def accepts(cls, device, parameters):
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "vemsd":
            return False, '"to" parameter is not "vemsd"'
        if "vemsd" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"vemsd" was not in the device configuration deploy methods'


class VExpressMsdRetry(RetryAction):
    name = "vexpress-fw-deploy-retry"
    description = "deploy vexpress board recovery image with retry"
    summary = "VExpress FW deployment with retry"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(VExpressMsdAction())


class VExpressMsdAction(Action):
    """
    Action for deploying firmware to a Versatile Express board
    in the form of a board recovery image.
    """

    name = "vexpress-fw-deploy"
    description = "deploy vexpress board recovery image"
    summary = "VExpress FW deployment"

    def validate(self):
        super().validate()
        if "recovery_image" not in self.parameters:
            self.errors = "recovery_image is required"

    def populate(self, parameters):
        download_dir = self.mkdtemp()
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(
            DownloaderAction(
                "recovery_image", path=download_dir, params=parameters["recovery_image"]
            )
        )
        self.pipeline.add_action(LxcCreateUdevRuleAction())
        self.force_prompt = True
        self.pipeline.add_action(ConnectDevice())
        self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(ExtractVExpressRecoveryImage())
        self.pipeline.add_action(EnterVExpressMCC())
        self.pipeline.add_action(EnableVExpressMassStorage())
        self.pipeline.add_action(WaitUSBMassStorageDeviceAction())
        self.pipeline.add_action(MountVExpressMassStorageDevice())
        self.pipeline.add_action(DeployVExpressRecoveryImage())
        self.pipeline.add_action(UnmountVExpressMassStorageDevice())
        if self.job.device["actions"]["deploy"]["methods"]["vemsd"]["parameters"].get(
            "flash_prompt", False
        ):
            self.pipeline.add_action(VExpressFlashErase())


class ExtractVExpressRecoveryImage(Action):
    """
    Unpacks the Versatile Express Board Recovery Image
    """

    name = "extract-vexpress-recovery-image"
    description = "unpack versatile express recovery image"
    summary = "unpack versatile express recovery image ready for deployment"

    def __init__(self):
        super().__init__()
        self.param_key = "recovery_image"
        self.file_key = "recovery_image"
        self.compression = None

    def validate(self):
        super().validate()
        if not self.get_namespace_data(
            action="download-action", label=self.param_key, key="file"
        ):
            self.errors = "no file specified extract as %s" % self.param_key
        self.compression = self.get_namespace_data(
            action="download-action", label=self.param_key, key="compression"
        )
        if not self.compression:
            self.errors = "no compression set for recovery image"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        recovery_image_dir = self.get_namespace_data(
            action="extract-vexpress-recovery-image", label="file", key=self.file_key
        )
        if recovery_image_dir:
            self.logger.debug("Clearing existing data at %s", recovery_image_dir)
            shutil.rmtree(recovery_image_dir)
        # copy recovery image to a temporary directory and unpack
        recovery_image = self.get_namespace_data(
            action="download-action", label=self.param_key, key="file"
        )
        recovery_image_dir = self.mkdtemp()
        shutil.copy(recovery_image, recovery_image_dir)
        tmp_recovery_image = os.path.join(
            recovery_image_dir, os.path.basename(recovery_image)
        )

        if os.path.isfile(tmp_recovery_image):
            if self.compression == "zip":
                decompress_file(tmp_recovery_image, self.compression)
            elif self.compression == "gz":
                untar_file(tmp_recovery_image, recovery_image_dir)
            else:
                raise InfrastructureError(
                    "Unsupported compression for VExpress recovery: %s"
                    % self.compression
                )
            os.remove(tmp_recovery_image)
            self.set_namespace_data(
                action="extract-vexpress-recovery-image",
                label="file",
                key=self.file_key,
                value=recovery_image_dir,
            )
            self.logger.debug("Extracted %s to %s", self.file_key, recovery_image_dir)
        else:
            raise InfrastructureError("Unable to decompress recovery image")
        return connection


class EnterVExpressMCC(Action):
    """
    Interrupts autorun if necessary and enters Versatile Express MCC.
    From here commands can be issued for enabling USB and erasing flash
    """

    name = "enter-vexpress-mcc"
    description = "enter Versatile Express MCC"
    summary = "enter Versatile Express MCC, interrupting autorun if needed"

    def __init__(self):
        super().__init__()
        self.device_params = None
        self.interrupt_char = None
        self.mcc_prompt = None
        self.autorun_prompt = None
        self.mcc_reset_msg = None

    def validate(self):
        super().validate()
        if not self.valid:
            return
        self.device_params = self.job.device["actions"]["deploy"]["methods"]["vemsd"][
            "parameters"
        ]
        self.interrupt_char = self.device_params.get(
            "interrupt_char", VEXPRESS_AUTORUN_INTERRUPT_CHARACTER
        )
        self.mcc_prompt = self.device_params.get("mcc_prompt")
        self.autorun_prompt = self.device_params.get("autorun_prompt")
        self.mcc_reset_msg = self.device_params.get("mcc_reset_msg")
        if not isinstance(self.mcc_prompt, str):
            self.errors = "Versatile Express MCC prompt unset"
        if not isinstance(self.autorun_prompt, str):
            self.errors = "Versatile Express autorun prompt unset"
        if not isinstance(self.mcc_reset_msg, str):
            self.errors = "Versatile Express MCC reset message unset"

    def run(self, connection, max_end_time):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super().run(connection, max_end_time)

        # Get possible prompts from device config
        prompt_list = [self.autorun_prompt, self.mcc_prompt, self.mcc_reset_msg]
        connection.prompt_str = prompt_list

        self.logger.debug("Changing prompt to '%s'", connection.prompt_str)
        index = self.wait(connection)

        # Interrupt autorun if enabled
        if connection.prompt_str[index] == self.autorun_prompt:
            self.logger.debug("Autorun enabled: interrupting..")
            connection.sendline(self.interrupt_char)
            connection.prompt_str = [self.mcc_prompt, self.mcc_reset_msg]
            index = self.wait(connection)
        elif connection.prompt_str[index] == self.mcc_prompt:
            self.logger.debug("Already at MCC prompt: autorun looks to be disabled")

        # Check that mcc_reset_msg hasn't been received
        if connection.prompt_str[index] == self.mcc_reset_msg:
            raise InfrastructureError("MCC: Unable to interrupt auto-run")
        return connection


class EnableVExpressMassStorage(Action):
    """
    Enable Versatile Express USB mass storage device from the MCC prompt
    """

    name = "enable-vexpress-usbmsd"
    description = "enable vexpress usb msd"
    summary = "enable vexpress usb mass storage device"

    def __init__(self):
        super().__init__()
        self.mcc_prompt = None
        self.mcc_cmd = None

    def validate(self):
        super().validate()
        device_params = self.job.device["actions"]["deploy"]["methods"]["vemsd"][
            "parameters"
        ]
        self.mcc_prompt = device_params.get("mcc_prompt")
        self.mcc_cmd = device_params.get("msd_mount_cmd")
        if not isinstance(self.mcc_prompt, str):
            self.errors = "Versatile Express MCC prompt unset"
        if not isinstance(self.mcc_cmd, str):
            self.errors = "Versatile Express USB Mass Storage mount command unset"

    def run(self, connection, max_end_time):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super().run(connection, max_end_time)

        # Issue command and check that you are returned to the prompt again
        connection.sendline(self.mcc_cmd)
        self.logger.debug("Changing prompt to '%s'", self.mcc_prompt)
        connection.prompt_str = self.mcc_prompt
        self.wait(connection)
        return connection


class MountDeviceMassStorageDevice(Action):
    """
    Generic action to mount a device's mass storage device, with a range of identifiers.
    """

    name = "mount-device-usbmsd"
    description = "mount device usb msd"
    summary = "mount device usb mass storage device on the dispatcher"
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.device_name = None
        self.disk_identifier = None
        self.disk_identifier_type = None  # uuid, id, label
        self.namespace_label = None

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        device_path = "/dev/disk/by-%s/%s" % (
            self.disk_identifier_type,
            self.disk_identifier,
        )
        if not os.path.exists(device_path):
            raise InfrastructureError(
                "Unable to find disk by %s %s"
                % (self.disk_identifier_type, device_path)
            )

        mount_point = "/mnt/%s" % self.disk_identifier
        if not os.path.exists(mount_point):
            try:
                self.logger.debug("Creating mount point '%s'", mount_point)
                os.makedirs(mount_point, 0o755)
            except OSError:
                raise InfrastructureError(
                    "Failed to create mount point %s" % mount_point
                )

        self.run_cmd(
            ["mount", device_path, mount_point],
            error_msg="Failed to mount device %s to %s" % (device_path, mount_point),
        )

        self.set_namespace_data(
            action=self.name,
            label=self.namespace_label,
            key="mount-point",
            value=mount_point,
        )
        return connection

    def cleanup(self, connection):
        mount_point = "/mnt/%s" % self.disk_identifier
        if os.path.ismount(mount_point):
            self.logger.debug("Unmounting %s", mount_point)
            self.run_cmd(
                ["umount", mount_point],
                error_msg="Failed to unmount device at %s" % mount_point,
            )


class MountVExpressMassStorageDevice(MountDeviceMassStorageDevice):
    """
    Mounts Versatile Express USB mass storage device on the dispatcher.
    The device is identified by the filesystem label given when running the
    format command on the Versatile Express board.
    """

    name = "mount-vexpress-usbmsd"
    description = "mount vexpress usb msd"
    summary = "mount vexpress usb mass storage device on the dispatcher"

    def __init__(self):
        super().__init__()
        self.device_name = "Versatile Express"
        self.disk_identifier = None
        self.disk_identifier_type = "label"
        self.namespace_label = "vexpress-fw"

    def validate(self):
        super().validate()
        self.disk_identifier = self.job.device.get("usb_filesystem_label")
        if not isinstance(self.disk_identifier, str):
            self.errors = "Filesystem %s unset for " + self.device_name


class DeployVExpressRecoveryImage(Action):
    """
    Removes the current recovery image from the mounted Versatile Express
    USB mass storage device, and copies over the new one
    """

    name = "deploy-vexpress-recovery-image"
    description = "deploy vexpress recovery image to usb msd"
    summary = "copy recovery image contents to vexpress usb mass storage device"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        mount_point = self.get_namespace_data(
            action="mount-vexpress-usbmsd", label="vexpress-fw", key="mount-point"
        )
        if not os.path.exists(mount_point):
            raise InfrastructureError("Unable to locate mount point: %s" % mount_point)

        src_dir = self.get_namespace_data(
            action="extract-vexpress-recovery-image", label="file", key="recovery_image"
        )
        if not os.path.exists(src_dir):
            raise InfrastructureError(
                "Unable to locate recovery image source directory: %s" % src_dir
            )

        self.logger.debug(
            "Removing existing recovery image from Versatile Express mass storage device.."
        )
        try:
            remove_directory_contents(mount_point)
        except Exception:
            raise InfrastructureError("Failed to erase old recovery image")

        self.logger.debug(
            "Transferring new recovery image to Versatile Express mass storage device.."
        )
        try:
            copy_directory_contents(src_dir, mount_point)
        except Exception:
            raise InfrastructureError(
                "Failed to deploy recovery image to %s" % mount_point
            )
        return connection


class UnmountVExpressMassStorageDevice(Action):
    """
    Unmount Versatile Express USB mass storage device on the dispatcher
    """

    name = "unmount-vexpress-usbmsd"
    description = "unmount vexpress usb msd"
    summary = "unmount vexpress usb mass storage device"
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.namespace_label = "vexpress-fw"
        self.namespace_action = "mount-vexpress-usbmsd"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        mount_point = self.get_namespace_data(
            action=self.namespace_action, label=self.namespace_label, key="mount-point"
        )
        self.run_cmd(
            ["sync", mount_point], error_msg="Failed to sync device %s" % mount_point
        )
        self.run_cmd(
            ["umount", mount_point],
            error_msg="Failed to unmount device %s" % mount_point,
        )
        return connection


class VExpressFlashErase(Action):
    """
    Enter Versatile Express Flash menu and erase NOR Flash.
    The job writer can define whether this should be a range or all.
    """

    name = "erase-vexpress-flash"
    description = "erase vexpress flash"
    summary = "erase vexpress flash using the commands set by the user"

    def __init__(self):
        super().__init__()
        self.mcc_prompt = None
        self.flash_prompt = None
        self.flash_enter_cmd = None
        self.flash_erase_cmd = None
        self.flash_erase_msg = None
        self.flash_exit_cmd = None

    def validate(self):
        super().validate()
        device_methods = self.job.device["actions"]["deploy"]["methods"]
        self.mcc_prompt = device_methods["vemsd"]["parameters"].get("mcc_prompt")
        self.flash_prompt = device_methods["vemsd"]["parameters"].get("flash_prompt")
        self.flash_enter_cmd = device_methods["vemsd"]["parameters"].get(
            "flash_enter_cmd"
        )
        self.flash_erase_cmd = device_methods["vemsd"]["parameters"].get(
            "flash_erase_cmd"
        )
        self.flash_erase_msg = device_methods["vemsd"]["parameters"].get(
            "flash_erase_msg"
        )
        self.flash_exit_cmd = device_methods["vemsd"]["parameters"].get(
            "flash_exit_cmd"
        )
        if not isinstance(self.mcc_prompt, str):
            self.errors = "Versatile Express MCC prompt unset"
        if not isinstance(self.flash_prompt, str):
            self.errors = "Versatile Express flash prompt unset"
        if not isinstance(self.flash_enter_cmd, str):
            self.errors = "Versatile Express flash enter command unset"
        if not isinstance(self.flash_erase_cmd, str):
            self.errors = "Versatile Express flash erase command unset"
        if not isinstance(self.flash_erase_msg, str):
            self.errors = "Versatile Express flash erase message unset"
        if not isinstance(self.flash_exit_cmd, str):
            self.errors = "Versatile Express flash exit command unset"

    def run(self, connection, max_end_time):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super().run(connection, max_end_time)

        # From Versatile Express MCC, enter flash menu
        connection.sendline(self.flash_enter_cmd)
        self.logger.debug("Changing prompt to '%s'", self.flash_prompt)
        connection.prompt_str = self.flash_prompt
        self.wait(connection)

        # Issue flash erase command
        connection.sendline(self.flash_erase_cmd)
        self.logger.debug("Changing prompt to '%s'", self.flash_erase_msg)
        connection.prompt_str = self.flash_erase_msg
        self.wait(connection)

        # Once we know the erase is underway.. wait for the prompt
        self.logger.debug("Changing prompt to '%s'", self.flash_prompt)
        connection.prompt_str = self.flash_prompt
        self.wait(connection)

        # If flash erase command has completed, return to MCC main menu
        connection.sendline(self.flash_exit_cmd)
        self.logger.debug("Changing prompt to '%s'", self.mcc_prompt)
        connection.prompt_str = self.mcc_prompt
        self.wait(connection)
        return connection
