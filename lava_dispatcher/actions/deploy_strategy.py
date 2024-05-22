# Copyright (C) 2024 Linaro Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.exceptions import ConfigurationError, JobError

from .base_strategy import BaseStrategy

if TYPE_CHECKING:
    from typing import ClassVar

    from lava_dispatcher.action import Action
    from lava_dispatcher.job import Job


class DeployStrategy(BaseStrategy):
    section = "deploy"
    name = "base-deploy"
    uses_deployment_data: ClassVar[bool] = True

    @classmethod
    def check_subclass(cls, device, parameters) -> None:
        if not device:
            raise JobError('job "device" was None')
        if "actions" not in device:
            raise ConfigurationError(
                'Invalid device configuration, no "actions" in device configuration'
            )
        if "to" not in parameters:
            raise ConfigurationError('"to" not specified in deploy parameters')
        if "deploy" not in device["actions"]:
            raise ConfigurationError(
                '"deploy" is not in the device configuration actions'
            )
        if "methods" not in device["actions"]["deploy"]:
            raise ConfigurationError(
                'Device misconfiguration, no "methods" in device configuration deploy actions'
            )


class Avh(DeployStrategy):
    name = "avh"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.avh import AvhRetryAction

        return AvhRetryAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "avh" not in device["actions"]["deploy"]["methods"]:
            return False, "'avh' not in the device configuration deploy methods"
        if parameters["to"] != "avh":
            return False, "'to' parameter is not 'avh'"
        return True, "accepted"


class Docker(DeployStrategy):
    name = "docker"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.docker import DockerAction

        return DockerAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "docker" not in device["actions"]["deploy"]["methods"]:
            return False, "'docker' not in the device configuration deploy methods"
        if parameters["to"] != "docker":
            return False, '"to" parameter is not "docker"'
        if "image" not in parameters:
            return False, '"image" is not in the deployment parameters'
        return True, "accepted"


class Download(DeployStrategy):
    """
    Strategy class for a download deployment.
    Downloads the relevant parts, copies to LXC if available.
    """

    name = "download"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.download import DownloadAction

        return DownloadAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "download":
            return False, '"to" parameter is not "download"'
        return True, "accepted"


class Downloads(DeployStrategy):
    """
    Strategy class for a download deployment.
    Just downloads files, and that's it.
    """

    name = "downloads"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.downloads import DownloadsAction

        return DownloadsAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "downloads":
            return False, '"to" parameter is not "downloads"'
        return True, "accepted"


class Fastboot(DeployStrategy):
    """
    Strategy class for a fastboot deployment.
    Downloads the relevant parts, copies to the locations using fastboot.
    """

    name = "fastboot"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.fastboot import FastbootAction

        return FastbootAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "fastboot":
            return False, '"to" parameter is not "fastboot"'
        if "deploy" not in device["actions"]:
            return False, '"deploy" is not in the device configuration actions'
        if not device.get("fastboot_auto_detection", False):
            if "adb_serial_number" not in device:
                return False, '"adb_serial_number" is not in the device configuration'
            if "fastboot_serial_number" not in device:
                return (
                    False,
                    '"fastboot_serial_number" is not in the device configuration',
                )
        if "fastboot_options" not in device:
            return False, '"fastboot_options" is not in the device configuration'
        if "fastboot" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"fastboot" was not in the device configuration deploy methods"'


class Flasher(DeployStrategy):
    name = "flasher"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.flasher import FlasherRetryAction

        return FlasherRetryAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "flasher" not in device["actions"]["deploy"]["methods"]:
            return False, "'flasher' not in the device configuration deploy methods"
        if parameters["to"] != "flasher":
            return False, '"to" parameter is not "flasher"'
        return True, "accepted"


class FVP(DeployStrategy):
    name = "fvp"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.fvp import FVPDeploy

        return FVPDeploy(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        to = parameters.get("to")
        if to != "fvp":
            return False, "'to' was not fvp"
        return True, "accepted"


class DeployQemuNfs(DeployStrategy):
    """
    Strategy class for a kernel & NFS QEMU deployment.
    Does not use GuestFS, adds overlay to the NFS
    """

    name = "qemu-nfs"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.image import DeployQemuNfsAction

        return DeployQemuNfsAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        """
        As a classmethod, this cannot set data
        in the instance of the class.
        This is *not* the same as validation of the action
        which can use instance data.
        """
        if "nfs" not in device["actions"]["deploy"]["methods"]:
            return False, '"nfs" is not in the device configuration deploy methods'
        if parameters["to"] != "nfs":
            return False, '"to" is not "nfs"'
        if "qemu-nfs" not in device["actions"]["boot"]["methods"]:
            return False, '"qemu-nfs" is not in the device configuration boot methods'
        if "type" in parameters:
            if parameters["type"] != "monitor":
                return False, '"type" was set, but it was not "monitor"'
        return True, "accepted"


class DeployPosixImages(DeployStrategy):
    """
    Strategy class for an Image based Deployment.
    Accepts parameters to deploy a QEMU
    Uses existing Actions to download and checksum
    as well as creating a qcow2 image for the test files.
    Does not boot the device.
    Requires guestfs instead of loopback support.
    Prepares the following actions and pipelines:
        retry-pipeline
            download-action
        report-checksum-action
        customisation-action
        test-definitions-action
    """

    name = "images"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.image import DeployImagesAction

        return DeployImagesAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        """
        As a classmethod, this cannot set data
        in the instance of the class.
        This is *not* the same as validation of the action
        which can use instance data.
        """
        if "image" not in device["actions"]["deploy"]["methods"]:
            return False, '"image" is not in the device configuration deploy methods'
        if parameters["to"] != "tmpfs":
            return False, '"to" parameter is not "tmpfs"'
        # lookup if the job parameters match the available device methods
        if "images" not in parameters:
            return False, '"images" was not in the deployment parameters'
        if "type" in parameters:
            if parameters["type"] != "monitor":
                return False, '"type" parameter was set but it was not "monitor"'
        return True, "accepted"


class DeployIso(DeployStrategy):
    name = "iso"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.iso import DeployIsoAction

        return DeployIsoAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "image" not in device["actions"]["deploy"]["methods"]:
            return False, '"image" is not in the device configuration deploy methods'
        if "to" in parameters and parameters["to"] == "iso-installer":
            if "iso" in parameters:
                if "installation_size" in parameters["iso"]:
                    return True, "accepted"
                else:
                    return False, '"installation_size" was not in the iso parameters'
            else:
                return False, '"iso" was not in the parameters'
        return False, '"to" was not in parameters, or "to" was not "iso-installer"'


class Lxc(DeployStrategy):
    """
    Strategy class for a lxc deployment.
    Downloads the relevant parts, copies to the locations using lxc.
    """

    name = "lxc"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.lxc import LxcAction

        return LxcAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "lxc":
            return False, '"to" parameter is not "lxc"'
        if "lxc" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"lxc" was not in the device configuration deploy methods'


class Mps(DeployStrategy):
    """
    Strategy class for a booting Arm MPS devices.
    Downloads board recovery image and deploys to target
    """

    name = "mps"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.mps import MpsAction

        return MpsAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "mps" not in device["actions"]["deploy"]["methods"]:
            return False, '"mps" was not in the device configuration deploy methods'
        if "to" not in parameters:
            return False, '"to" was not in parameters'
        if parameters["to"] != "mps":
            return False, '"to" was not "mps"'
        if "usb_filesystem_label" not in device:
            return False, '"usb_filesystem_label" is not in the device configuration'
        return True, "accepted"


class Musca(DeployStrategy):
    """
    Strategy class for a booting Arm Musca devices.
    Downloads an image and deploys to the board.
    """

    name = "musca"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.musca import MuscaAction

        return MuscaAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "musca" not in device["actions"]["deploy"]["methods"]:
            return False, '"musca" was not in the device configuration deploy methods'
        if "to" not in parameters:
            return False, '"to" was not in parameters'
        if parameters["to"] != "musca":
            return False, '"to" was not "musca"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class Nbd(DeployStrategy):
    """
    Strategy class for a tftp+initrd+nbd based Deployment.
    tftp is used for kernel/initrd/fdt. Rootfs over nbd (network block device).
    Downloads the relevant parts, copies to the tftp location.
    Limited to what the bootloader can deploy which means ramdisk or nfsrootfs.
    rootfs deployments would format the device and create a single partition for the rootfs.
    """

    name = "nbd"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.nbd import NbdAction

        return NbdAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "nbd":
            return False, '"to" parameter is not "nbd"'
        if "nbd" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"ndb" was not in the device configuration deploy methods'


class Nfs(DeployStrategy):
    """
    Strategy class for a NFS deployment.
    Downloads rootfs and deploys to NFS server on dispatcher
    """

    name = "nfs"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.nfs import NfsAction

        return NfsAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "nfs":
            return False, '"to" parameter is not "nfs"'
        if "image" in device["actions"]["deploy"]["methods"]:
            return False, '"image" was in the device configuration deploy methods'
        if "nfs" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"nfs" was not in the device configuration deploy methods"'


class Overlay(DeployStrategy):
    name = "overlay"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.overlay import OverlayAction

        return OverlayAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "overlay" not in device["actions"]["deploy"]["methods"]:
            return False, "'overlay' not in the device configuration deploy methods"
        if parameters["to"] != "overlay":
            return False, '"to" parameter is not "overlay"'
        return True, "accepted"


class RecoveryMode(DeployStrategy):
    name = "recovery-mode"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.recovery import RecoveryModeAction

        return RecoveryModeAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "recovery" not in device["actions"]["deploy"]["methods"]:
            return False, "'recovery' not in the device configuration deploy methods"
        if parameters["to"] != "recovery":
            return False, '"to" parameter is not "recovery"'
        if "images" not in parameters:
            return False, '"images" is not in the deployment parameters'
        return True, "accepted"


class Removable(DeployStrategy):
    """
    Deploys an image to a usb or sata mass storage device
    *Destroys* anything on that device, including partition table
    Requires a preceding boot (e.g. ramdisk) which may have a test shell of it's own.
    Does not require the ramdisk to be able to mount the usb storage, just for the kernel
    to be able to see the device (the filesystem will be replaced anyway).

    SD card partitions will use a similar approach but the UUID will be fixed in the device
    configuration and specifying a restricted UUID will invalidate the job to protect the bootloader.

    """

    name = "removable"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.removable import MassStorage

        return MassStorage(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        media = parameters.get("to")
        job_device = parameters.get("device")

        # Is the media supported?
        if media not in ["sata", "sd", "usb"]:
            return False, '"media" was not "sata", "sd", or "usb"'
        # "parameters.media" is not defined for every devices
        if "parameters" not in device or "media" not in device["parameters"]:
            return (
                False,
                '"parameters" was not in the device or "media" was not in the parameters',
            )
        # Is the device allowing this method?
        if job_device not in device["parameters"]["media"].get(media, {}):
            return False, 'media was not in the device "media" parameters'
        # Is the configuration correct?
        if "uuid" in device["parameters"]["media"][media].get(job_device, {}):
            return True, "accepted"
        return (
            False,
            '"uuid" was not in the parameters for the media device %s' % job_device,
        )


class Ssh(DeployStrategy):
    """
    Copies files to the target to support further actions,
    typically the overlay.
    """

    name = "ssh"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.ssh import ScpOverlay

        return ScpOverlay(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "ssh" not in device["actions"]["deploy"]["methods"]:
            return False, '"ssh" is not in the device configuration deploy methods'
        if parameters["to"] != "ssh":
            return False, '"to" parameter is not "ssh"'
        return True, "accepted"


class Tftp(DeployStrategy):
    """
    Strategy class for a tftp ramdisk based Deployment.
    Downloads the relevant parts, copies to the tftp location.
    Limited to what the bootloader can deploy which means ramdisk or nfsrootfs.
    rootfs deployments would format the device and create a single partition for the rootfs.
    """

    name = "tftp"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.tftp import TftpAction

        return TftpAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "tftp":
            return False, '"to" parameter is not "tftp"'
        if "tftp" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"tftp" was not in the device configuration deploy methods"'


class UBootUMS(DeployStrategy):
    """
    Strategy class for a UBoot USB Mass Storage deployment.
    Downloads the relevant parts, and applies the test overlay into the image.
    """

    name = "uboot-ums"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.uboot_ums import UBootUMSAction

        return UBootUMSAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "u-boot-ums":
            return False, '"to" parameter is not "u-boot-ums"'
        if "deploy" not in device["actions"]:
            return False, '"deploy" is not in the device configuration actions'
        if "image" not in parameters:
            return False, '"image" was not in the deploy parameters'
        if "u-boot-ums" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"u-boot-ums" was not in the device configuration deploy methods"'


class USBGMS(DeployStrategy):
    """
    Strategy class for a usbg-ms deployment.
    """

    name = "usbg-ms"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.usbg_ms import USBGMSAction

        return USBGMSAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["to"] != "usbg-ms":
            return False, '"to" parameter is not "usbg-ms"'
        if "usbg-ms" not in device["actions"]["deploy"]["methods"]:
            return False, "'usbg-ms' not in the device configuration deploy methods"
        keys = set(device["actions"]["deploy"]["methods"]["usbg-ms"].keys())
        if keys != {"disable", "enable"}:
            raise ConfigurationError(
                "usbg-ms 'disable' and 'enable' commands missing: %s", keys
            )
        return True, "accepted"


class UUU(DeployStrategy):
    """
    Strategy class for a UUU deployment.
    Downloads images and apply overlay if needed.
    """

    name = "uuu"

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.uuu import UUUAction

        return UUUAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "uuu":
            return False, '"to" parameter is not "uuu"'
        if "deploy" not in device["actions"]:
            return False, '"deploy" is not in the device configuration actions'
        if "images" not in parameters:
            return False, "'images' not in deploy parameters"
        if "boot" not in parameters["images"].keys():
            return False, "'boot' image is required, not found in 'images' parameter"
        return True, "accepted"


class VExpressMsd(DeployStrategy):
    """
    Strategy class for a Versatile Express firmware deployment.
    Downloads Versatile Express board recovery image and deploys
    to target device
    """

    name = "vemsd"

    # recovery image deployment does not involve an OS
    uses_deployment_data = False

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.deploy.vemsd import VExpressMsdRetry

        return VExpressMsdRetry(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "vemsd":
            return False, '"to" parameter is not "vemsd"'
        if "vemsd" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"vemsd" was not in the device configuration deploy methods'
