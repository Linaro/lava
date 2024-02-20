# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot.fastboot import EnterFastbootAction
from lava_dispatcher.actions.boot.u_boot import UBootEnterFastbootAction
from lava_dispatcher.actions.deploy.apply_overlay import (
    ApplyOverlayImage,
    ApplyOverlaySparseImage,
)
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Deployment
from lava_dispatcher.power import PDUReboot, PrePower, ReadFeedback, ResetDevice
from lava_dispatcher.utils.fastboot import OptionalContainerFastbootAction
from lava_dispatcher.utils.lxc import is_lxc_requested
from lava_dispatcher.utils.udev import WaitDeviceBoardID


class Fastboot(Deployment):
    """
    Strategy class for a fastboot deployment.
    Downloads the relevant parts, copies to the locations using fastboot.
    """

    name = "fastboot"

    @classmethod
    def action(cls):
        return FastbootAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "to" not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters["to"] != "fastboot":
            return False, '"to" parameter is not "fastboot"'
        if "deploy" not in device["actions"]:
            return False, '"deploy" is not in the device configuration actions'
        if "adb_serial_number" not in device:
            return False, '"adb_serial_number" is not in the device configuration'
        if "fastboot_serial_number" not in device:
            return False, '"fastboot_serial_number" is not in the device configuration'
        if "fastboot_options" not in device:
            return False, '"fastboot_options" is not in the device configuration'
        if "fastboot" in device["actions"]["deploy"]["methods"]:
            return True, "accepted"
        return False, '"fastboot" was not in the device configuration deploy methods"'


class FastbootAction(
    OptionalContainerFastbootAction
):  # pylint:disable=too-many-instance-attributes
    name = "fastboot-deploy"
    description = "download files and deploy using fastboot"
    summary = "fastboot deployment"

    def __init__(self):
        super().__init__()
        self.force_prompt = False

    def validate(self):
        super().validate()
        if not self.test_needs_deployment(self.parameters):
            return

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())
        # Check if the device has a power command such as HiKey, Dragonboard,
        # etc. against device that doesn't like Nexus, etc.
        if self.job.device.get("fastboot_via_uboot", False):
            self.pipeline.add_action(ConnectDevice())
            self.pipeline.add_action(UBootEnterFastbootAction())
        elif self.job.device.hard_reset_command:
            self.force_prompt = True
            self.pipeline.add_action(ConnectDevice())
            if not is_lxc_requested(self.job):
                self.pipeline.add_action(PrePower())
            self.pipeline.add_action(ResetDevice())
        else:
            self.pipeline.add_action(EnterFastbootAction())

        fastboot_dir = self.mkdtemp()
        for image in sorted(parameters["images"].keys()):
            self.pipeline.add_action(
                DownloaderAction(
                    image, fastboot_dir, params=parameters["images"][image]
                )
            )
            if parameters["images"][image].get("apply-overlay", False):
                if self.test_needs_overlay(parameters):
                    if parameters["images"][image].get("sparse", True):
                        self.pipeline.add_action(ApplyOverlaySparseImage(image))
                    else:
                        use_root_part = parameters["images"][image].get(
                            "root_partition", False
                        )
                        self.pipeline.add_action(
                            ApplyOverlayImage(image, use_root_partition=use_root_part)
                        )

            if self.test_needs_overlay(parameters) and self.test_needs_deployment(
                parameters
            ):
                self.pipeline.add_action(DeployDeviceEnvironment())
        self.pipeline.add_action(FastbootFlashOrderAction())


class FastbootFlashOrderAction(OptionalContainerFastbootAction):
    """
    Fastboot flash image.
    """

    name = "fastboot-flash-order-action"
    description = "Determine support for each flash operation"
    summary = "Handle reset and options for each flash url."

    def __init__(self):
        super().__init__()
        self.retries = 3
        self.sleep = 10
        self.interrupt_prompt = None
        self.interrupt_string = None
        self.reboot = None

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        flash_cmds_order = self.job.device["flash_cmds_order"]
        userlist = list(parameters["images"].keys())
        flash_cmds = set(userlist).difference(set(flash_cmds_order))
        flash_cmds = flash_cmds_order + list(flash_cmds)
        board_id = self.job.device["fastboot_serial_number"]
        self.pipeline.add_action(ReadFeedback(repeat=True))
        for flash_cmd in flash_cmds:
            if flash_cmd not in parameters["images"]:
                continue
            self.pipeline.add_action(WaitDeviceBoardID(board_id))
            self.pipeline.add_action(FastbootFlashAction(cmd=flash_cmd))
            self.reboot = parameters["images"][flash_cmd].get("reboot")
            if self.reboot == "fastboot-reboot":
                self.pipeline.add_action(FastbootReboot())
                self.pipeline.add_action(ReadFeedback(repeat=True))
            elif self.reboot == "fastboot-reboot-bootloader":
                self.pipeline.add_action(FastbootRebootBootloader())
                self.pipeline.add_action(ReadFeedback(repeat=True))
            elif self.reboot == "fastboot-reboot-fastboot":
                self.pipeline.add_action(FastbootRebootFastboot())
                self.pipeline.add_action(ReadFeedback(repeat=True))
            elif self.reboot == "hard-reset":
                self.pipeline.add_action(PDUReboot())
                self.pipeline.add_action(ReadFeedback(repeat=True))

    def validate(self):
        super().validate()
        self.set_namespace_data(
            action=FastbootFlashAction.name,
            label="interrupt",
            key="reboot",
            value=self.reboot,
        )
        if "fastboot" not in self.job.device["actions"]["deploy"]["connections"]:
            self.errors = (
                "Device not configured to support fastboot deployment connections."
            )
        if "fastboot_serial_number" not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device["fastboot_serial_number"] == "0000000000":
            self.errors = "device fastboot serial number unset"
        if "flash_cmds_order" not in self.job.device:
            self.errors = "device flash commands order missing"
        if "fastboot_options" not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device["fastboot_options"], list):
            self.errors = "device fastboot options is not a list"


class FastbootFlashAction(OptionalContainerFastbootAction):

    """
    Fastboot flash image.
    """

    name = "fastboot-flash-action"
    description = "Run a specified flash command"
    summary = "Execute fastboot flash command"
    timeout_exception = InfrastructureError

    def __init__(self, cmd=None):
        super().__init__()
        self.retries = 3
        self.sleep = 10
        self.command = cmd
        self.interrupt_prompt = None
        self.interrupt_string = None

    def validate(self):
        super().validate()
        if not self.command:
            self.errors = "Invalid configuration - missing flash command"
        if "fastboot" not in self.job.device["actions"]["deploy"]["connections"]:
            self.errors = (
                "Device not configured to support fastboot deployment connections."
            )
        device_methods = self.job.device["actions"]["deploy"]["methods"]
        if isinstance(device_methods.get("fastboot"), dict):
            self.interrupt_prompt = device_methods["fastboot"].get("interrupt_prompt")
            self.interrupt_string = device_methods["fastboot"].get("interrupt_string")

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        src = self.get_namespace_data(
            action="download-action", label=self.command, key="file"
        )
        if not src:
            return connection
        self.logger.debug("%s bytes", os.stat(src)[6])

        src = self.maybe_copy_to_container(src)

        sequence = self.job.device["actions"]["boot"]["methods"].get("fastboot", [])
        if "no-flash-boot" in sequence and self.command in ["boot"]:
            return connection

        # if a reboot is requested, will need to wait for the prompt
        # if not, continue in the existing mode.
        reboot = self.get_namespace_data(
            action=self.name, label="interrupt", key="reboot"
        )
        if self.interrupt_prompt and reboot:
            connection.prompt_str = self.interrupt_prompt
            self.logger.debug("Changing prompt to '%s'", connection.prompt_str)
            self.wait(connection)

        self.run_fastboot(["flash", self.command, src])
        self.logger.info("Handling %s", self.command)
        self.results = {"label": self.command}
        return connection


class FastbootReboot(OptionalContainerFastbootAction):
    name = "fastboot-reboot"
    description = "Reset a device between flash operations using fastboot reboot."
    summary = "execute a reboot using fastboot"

    def validate(self):
        super().validate()
        if "fastboot" not in self.job.device["actions"]["deploy"]["connections"]:
            self.errors = (
                "Device not configured to support fastboot deployment connections."
            )
        if "fastboot_serial_number" not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device["fastboot_serial_number"] == "0000000000":
            self.errors = "device fastboot serial number unset"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        serial_number = self.job.device["fastboot_serial_number"]
        fastboot_opts = self.job.device["fastboot_options"]

        self.logger.info("fastboot rebooting device.")
        self.run_fastboot(["reboot"])
        return connection


class FastbootRebootBootloader(OptionalContainerFastbootAction):
    name = "fastboot-reboot-bootloader"
    description = (
        "Reset a device between flash operations using fastboot reboot-bootloader."
    )
    summary = "execute a reboot to bootloader using fastboot"

    def validate(self):
        super().validate()
        if "fastboot" not in self.job.device["actions"]["deploy"]["connections"]:
            self.errors = (
                "Device not configured to support fastboot deployment connections."
            )
        if "fastboot_serial_number" not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device["fastboot_serial_number"] == "0000000000":
            self.errors = "device fastboot serial number unset"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        serial_number = self.job.device["fastboot_serial_number"]
        fastboot_opts = self.job.device["fastboot_options"]

        self.logger.info("fastboot reboot device to bootloader.")
        self.run_fastboot(["reboot-bootloader"])
        return connection


class FastbootRebootFastboot(OptionalContainerFastbootAction):
    name = "fastboot-reboot-fastboot"
    description = (
        "Reset a device between flash operations using fastboot reboot fastboot."
    )
    summary = "execute a reboot to fastbootd using fastboot"

    def validate(self):
        super().validate()
        if "fastboot" not in self.job.device["actions"]["deploy"]["connections"]:
            self.errors = (
                "Device not configured to support fastboot deployment connections."
            )
        if "fastboot_serial_number" not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device["fastboot_serial_number"] == "0000000000":
            self.errors = "device fastboot serial number unset"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        serial_number = self.job.device["fastboot_serial_number"]
        fastboot_opts = self.job.device["fastboot_options"]

        self.logger.info("fastboot reboot device to fastbootd.")
        self.run_fastboot(["reboot", "fastboot"])
        return connection
