# Copyright 2019-2020 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
#         Franck Lenormand <franck.lenormand@nxp.com>
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

import time
from lava_dispatcher.action import Pipeline, Action
from lava_common.exceptions import ConfigurationError, JobError
from lava_dispatcher.actions.boot.bootloader import BootBootloaderAction
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.actions.boot import BootloaderCommandOverlay

from lava_dispatcher.connections.serial import ConnectDevice, DisconnectDevice
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.strings import safe_dict_format
from lava_dispatcher.utils.uuu import OptionalContainerUuuAction


class CheckSerialDownloadMode(OptionalContainerUuuAction):
    name = "check-serial-availability"
    description = "Store in 'otg_availability_check' namespace_data if USB serial download mode available"
    summary = "Store in 'otg_availability_check' namespace_data if USB serial download mode available"

    def populate(self, parameters):
        self.parameters = parameters
        self.uuu = self.which("uuu")
        self.linux_timeout = self.which("timeout")

    def check_board_availability(self):
        """
        Check if the board is available in USB serial download mode
        This method try to boot the board using uuu, (uuu <bootimage>)
        If 'uuu <bootimage>' does not terminate within 10 seconds this method return false

        see the doc : https://github.com/NXPmicro/mfgtools
        :return: True if board is available in USB serial download mode
        """
        usb_otg_path = self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "usb_otg_path"
        ]
        boot = self.get_namespace_data(
            action="download-action", label="boot", key="file"
        )
        # Sleep 5 seconds before availability check
        time.sleep(5)

        cmd = "{} --preserve-status 10 {} -m {} {}".format(
            self.linux_timeout, self.uuu, usb_otg_path, boot
        )

        self.maybe_copy_to_container(boot)

        # Board available if cmd terminates correctly
        return self.run_uuu(cmd.split(" "), allow_fail=True) == 0

    def run(self, connection, max_end_time):
        super().run(connection, max_end_time)
        board_available = self.check_board_availability()

        if not board_available:
            self.logger.info(
                "Board not available in serial download mode, corrupting boot media"
            )
            self.set_namespace_data(
                action="boot", label="uuu", key="otg_availability_check", value=False
            )
        else:
            self.logger.info("Board available for usb serial download")
            self.set_namespace_data(
                action="boot", label="uuu", key="otg_availability_check", value=True
            )


class UUUBoot(Boot):
    """
    The UUUBoot method allow to always boot on USB serial download mode
    used by uuu to flash on boot media a fresh bootimage.

    If the board is not available for USB serial download, action 'boot-corrupt-boot-media'
    will run commands in u-boot to corrupt boot media. After this action, board must be available in USB serial download
    mode.
    if the board is available without the previous action, 'boot-corrupt-boot-media' won't add anything to pipeline.

    """

    compatibility = 1

    @classmethod
    def action(cls):
        return UUUBootRetryAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "uuu":
            return False, '"method" was not "uuu"'
        if "commands" not in parameters:
            raise ConfigurationError("commands not specified in boot parameters")
        params = device["actions"]["boot"]["methods"]["uuu"]["options"]
        if not params["usb_otg_path"]:
            raise ConfigurationError(
                "uuu_usb_otg_path not defined in device definition"
            )
        if params["corrupt_boot_media_command"] is None:
            raise ConfigurationError(
                "uuu_corrupt_boot_media_command not defined in device definition"
            )
        if "u-boot" in device["actions"]["boot"]["methods"]:
            return True, "accepted"
        return False, '"uuu" was not in the device configuration boot methods'


class BootBootloaderCorruptBootMediaAction(Action):

    name = "boot-corrupt-boot-media"
    description = "boot using 'bootloader' method and corrupt boot media"
    summary = "boot bootloader"

    def populate(self, parameters):
        SD_ERASE_CMDS = self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "corrupt_boot_media_command"
        ]
        if isinstance(SD_ERASE_CMDS, str):
            SD_ERASE_CMDS = [SD_ERASE_CMDS]

        u_boot_params = {
            "method": "bootloader",
            "bootloader": "u-boot",
            "commands": SD_ERASE_CMDS,
            "prompts": ["=>"],
        }
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=u_boot_params)
        self.pipeline.add_action(ConnectDevice())
        self.pipeline.add_action(
            BootloaderCommandOverlay(
                method=u_boot_params["bootloader"], commands=u_boot_params["commands"]
            )
        )
        self.pipeline.add_action(BootBootloaderAction())
        self.pipeline.add_action(DisconnectDevice())

    def run(self, connection, max_end_time):
        otg_available = self.get_namespace_data(
            action="boot", label="uuu", key="otg_availability_check"
        )
        if otg_available:
            return connection
        else:
            super().run(connection, max_end_time)


class UUUBootRetryAction(RetryAction):
    """
    Wraps the Retry Action to allow for actions which precede
    the reset, e.g. Connect.
    """

    name = "uuu-boot-retry"
    description = "Boot the board using uboot and perform uuu commands"
    summary = "Pass uuu commands"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(CheckSerialDownloadMode())
        self.pipeline.add_action(BootBootloaderCorruptBootMediaAction())
        self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(UUUBootAction(), parameters=parameters)
        self.pipeline.add_action(ConnectDevice())


class UUUBootAction(OptionalContainerUuuAction):

    name = "uuu-boot"
    description = "interactive uuu action"
    summary = "uuu commands"

    def populate(self, parameters):
        self.parameters = parameters
        self.uuu = self.which("uuu")

    def validate(self):
        super().validate()
        self.set_namespace_data(
            action=self.name, label="bootloader_prompt", key="prompt", value=None
        )

    def run(self, connection, max_end_time):
        usb_otg_path = self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "usb_otg_path"
        ]
        uuu_cmds = self.parameters["commands"]

        images_name = self.get_namespace_data(
            action="uuu-deploy", label="uuu-images", key="images_names"
        )

        # Use to replace {boot} identifier in cmd by correct 'boot' image path
        templates = dict()
        for image in images_name:
            templates[image] = self.get_namespace_data(
                "download-action", label=image, key="file"
            )
            self.maybe_copy_to_container(templates[image])

        self.logger.info(templates)

        uuu_cmd_list = []
        for dico in uuu_cmds:
            for protocol, cmd in dico.items():
                cmd = safe_dict_format(cmd, templates)
                uuu_cmd_list.append("{}: {}".format(protocol, cmd))

        uuu_cmds = uuu_cmd_list

        if usb_otg_path is None:
            raise JobError("USB path of the device not set for uuu")

        for cmd in uuu_cmds:
            if "uuu:" in cmd:
                # uuu can be used in 2 different ways, by using built-in scripts in a single command,
                # or with a list of commands, each prefixed with a protocol type.
                #   Example of built-in: uuu -b sd bootimage
                #   Example of protocol: uuu SDP: boot -f flash.bin
                # So it is more convenient for LAVA job writers to use uuu built-in script with a tuple (protocol, command), like uuu: -b sd_all
                # In this last case, we remove the 'uuu: ' here
                cmd = cmd.replace("uuu: ", "")
            exec_cmd = "{} -m {} {}".format(self.uuu, usb_otg_path, cmd)

            time.sleep(1)
            self.run_uuu(
                exec_cmd.split(" "),
                allow_fail=False,
                error_msg="Fail UUUBootAction on cmd : {}".format(cmd),
            )

        return None
