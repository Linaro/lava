# Copyright 2019-2022 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
#         Franck Lenormand <franck.lenormand@nxp.com>
#         Gopalakrishnan RAJINE ANAND <gopalakrishnan.rajineanand@nxp.com>
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

import re
import time

from lava_common.exceptions import ConfigurationError, JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import BootloaderCommandOverlay
from lava_dispatcher.actions.boot.bootloader import BootBootloaderAction
from lava_dispatcher.connections.serial import ConnectDevice, DisconnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import PowerOff, ResetDevice
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

        boot = self.get_namespace_data(
            action="download-action", label="boot", key="file"
        )
        # Sleep 5 seconds before availability check
        time.sleep(5)

        usb_otg_path = self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "usb_otg_path"
        ]

        cmd = "{} --preserve-status 10 {} -m {} {}".format(
            self.linux_timeout, self.uuu, usb_otg_path, boot
        )

        self.maybe_copy_to_container(boot)

        # Board available if cmd terminates correctly
        return self.run_uuu(cmd.split(" "), allow_fail=True) == 0

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
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

        return connection


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
        if not params["usb_otg_path"] and not params["usb_otg_path_command"]:
            raise ConfigurationError(
                "'uuu_usb_otg_path' or 'uuu_usb_otg_path_command' not defined in device definition"
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
        power_off = self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "power_off_before_corrupt_boot_media"
        ]

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
        if power_off:
            self.pipeline.add_action(PowerOff())
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
            return super().run(connection, max_end_time)


class UUUBootRetryAction(RetryAction):
    """
    Wraps the Retry Action to allow for actions which precede
    the reset, e.g. Connect.
    """

    name = "uuu-boot-retry"
    description = "Boot the board using uboot and perform uuu commands"
    summary = "Pass uuu commands"

    def populate(self, parameters):
        # Verify format of usb_otg_path if available or process uuu_otg_path_command
        self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "usb_otg_path"
        ] = self.eval_otg_path()
        self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "has_bcu_commands"
        ] = self.has_bcu_commands(parameters)
        if self.has_bcu_commands(parameters):
            self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
                "bcu_board_id"
            ] = self.eval_bcu_board_id()
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(CheckSerialDownloadMode())
        self.pipeline.add_action(BootBootloaderCorruptBootMediaAction())
        self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(UUUBootAction(), parameters=parameters)
        self.pipeline.add_action(ConnectDevice())

    def eval_otg_path(self):
        uuu_options = self.job.device["actions"]["boot"]["methods"]["uuu"]["options"]

        # Match example : "2:112"
        otg_path_fsm = re.compile(r"\d+:\d+")

        if otg_path_fsm.fullmatch(uuu_options.get("usb_otg_path")):
            return uuu_options.get("usb_otg_path")

        if uuu_options.get("usb_otg_path_command") is None:
            raise JobError(
                "uuu_usb_otg_path '{}' does not match with uuu path pattern and 'uuu_usb_otg_path_command' not "
                "defined in device".format(uuu_options.get("usb_otg_path"))
            )
        else:
            usb_otg_path_command = uuu_options.get("usb_otg_path_command")
            cmd = usb_otg_path_command
            self.logger.info(
                "Retrieving 'usb_otg_path' using command : '%s'", " ".join(cmd)
            )

            uuu_path_expected = self.parsed_command(cmd).strip()

            if otg_path_fsm.fullmatch(uuu_path_expected):
                self.logger.info("uuu_otg_path matched : %s", uuu_path_expected)
                return uuu_path_expected

            raise JobError(
                "Unable to parse uuu_usb_otg_path from command '{}'".format(cmd)
            )

    def has_bcu_commands(self, parameters):
        """
        Checks if the bcu is present in the commands list. Returns true if bcu is present
        """
        cmds = parameters["commands"]
        for commands in cmds:
            for protocol, cmd in commands.items():
                if protocol == "bcu":
                    return True
        return False

    def eval_bcu_board_id(self):
        uuu_options = self.job.device["actions"]["boot"]["methods"]["uuu"]["options"]

        if uuu_options.get("bcu_board_name") == "":
            raise JobError("'bcu_board_name' is not defined in device-types")

        # Match example : "2-1.3"
        bcu_id_fsm = re.compile(r"\d+-(\d+|\.)+")

        if bcu_id_fsm.fullmatch(uuu_options.get("bcu_board_id")):
            return uuu_options.get("bcu_board_id")

        if uuu_options.get("bcu_board_id_command") is None:
            raise JobError(
                "bcu_board_id '{}' do not respect bcu format or 'bcu_board_id_command' not "
                "defined in device".format(uuu_options.get("bcu_board_id"))
            )
        else:
            bcu_board_id_command = uuu_options.get("bcu_board_id_command")

        self.logger.info(
            "Retrieving 'bcu_board_id' using command : '%s'",
            " ".join(bcu_board_id_command),
        )

        bcu_id_expected = self.parsed_command(bcu_board_id_command).strip()

        if bcu_id_fsm.fullmatch(bcu_id_expected):
            self.logger.info("Matched bcu_board_id : %s", bcu_id_expected)
            return bcu_id_expected

        raise JobError(
            "Unable to parse bcu_id from command '{}'".format(bcu_board_id_command)
        )


class UUUBootAction(OptionalContainerUuuAction):
    name = "uuu-boot"
    description = "interactive uuu action"
    summary = "uuu commands"

    def populate(self, parameters):
        self.parameters = parameters
        self.uuu = self.which("uuu")
        if self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "has_bcu_commands"
        ]:
            self.bcu = self.which("bcu")

    def validate(self):
        super().validate()
        self.set_namespace_data(
            action=self.name, label="bootloader_prompt", key="prompt", value=None
        )

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        usb_otg_path = self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "usb_otg_path"
        ]
        uuu_cmds = self.parameters["commands"]
        bcu_board_name = self.job.device["actions"]["boot"]["methods"]["uuu"][
            "options"
        ]["bcu_board_name"]
        bcu_board_id = self.job.device["actions"]["boot"]["methods"]["uuu"]["options"][
            "bcu_board_id"
        ]
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
            if "bcu:" in cmd:
                cmd = cmd.replace("bcu: ", "")
                exec_cmd = "{} {} -board={} -id={}".format(
                    self.bcu, cmd, bcu_board_name, bcu_board_id
                )
                self.run_cmd(exec_cmd.split(" "))
                continue
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

        return connection
