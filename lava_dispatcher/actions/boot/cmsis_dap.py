# Copyright (C) 2016 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
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

import shutil

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.action import Pipeline, Action
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.filesystem import mkdtemp
from lava_dispatcher.utils.udev import WaitUSBSerialDeviceAction, WaitDevicePathAction


class CMSIS(Boot):

    compatibility = 4  # FIXME: change this to 5 and update test cases

    @classmethod
    def action(cls):
        return BootCMSISRetry()

    @classmethod
    def accepts(cls, device, parameters):
        if "cmsis-dap" not in device["actions"]["boot"]["methods"]:
            return False, '"cmsis-dap" is not in the device configuration boot methods'
        if "method" not in parameters:
            return False, '"method" not in parameters'
        if parameters["method"] != "cmsis-dap":
            return False, '"method" was not "cmsis-dap"'
        if "board_id" not in device:
            return False, 'device has no "board_id" configured'
        if "parameters" not in device["actions"]["boot"]["methods"]["cmsis-dap"]:
            return (
                False,
                '"parameters" was not in the device boot method configuration for "cmsis-dap"',
            )
        if (
            "usb_mass_device"
            not in device["actions"]["boot"]["methods"]["cmsis-dap"]["parameters"]
        ):
            return (
                False,
                '"usb_mass_device" was not in the device configuration "cmsis-dap" boot method parameters',
            )
        return True, "accepted"


class BootCMSISRetry(RetryAction):

    name = "boot-cmsis-retry"
    description = "boot cmsis usb image with retry"
    summary = "boot cmsis usb image with retry"

    def validate(self):
        super().validate()
        method_params = self.job.device["actions"]["boot"]["methods"]["cmsis-dap"][
            "parameters"
        ]
        usb_mass_device = method_params.get("usb_mass_device")
        if not usb_mass_device:
            self.errors = "usb_mass_device unset"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        method_params = self.job.device["actions"]["boot"]["methods"]["cmsis-dap"][
            "parameters"
        ]
        usb_mass_device = method_params.get("usb_mass_device")
        resets_after_flash = method_params.get("resets_after_flash", True)
        if self.job.device.hard_reset_command:
            self.pipeline.add_action(ResetDevice())
            self.pipeline.add_action(WaitDevicePathAction(usb_mass_device))
        self.pipeline.add_action(FlashCMSISAction())
        if resets_after_flash:
            self.pipeline.add_action(WaitUSBSerialDeviceAction())
        self.pipeline.add_action(ConnectDevice())


class FlashCMSISAction(Action):

    name = "flash-cmsis"
    description = "flash cmsis to usb mass storage"
    summary = "flash cmsis to usb mass storage"
    command_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.filelist = []
        self.usb_mass_device = None

    def validate(self):
        super().validate()
        if self.job.device["board_id"] == "0000000000":
            self.errors = "[FLASH_CMSIS] board_id unset"
        method_parameters = self.job.device["actions"]["boot"]["methods"]["cmsis-dap"][
            "parameters"
        ]
        self.usb_mass_device = method_parameters.get("usb_mass_device")
        if not self.usb_mass_device:
            self.errors = "usb_mass_device unset"
        for action in self.get_namespace_keys("download-action"):
            action_arg = self.get_namespace_data(
                action="download-action", label=action, key="file"
            )
            self.filelist.extend([action_arg])

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        dstdir = mkdtemp()
        # mount
        self.run_cmd(
            ["mount", "-t", "vfat", self.usb_mass_device, dstdir],
            error_msg="Unable to mount USB device %s" % self.usb_mass_device,
        )
        # copy files
        for f in self.filelist:
            self.logger.debug("Copying %s to %s", f, dstdir)
            shutil.copy2(f, dstdir)
        # sync
        self.run_cmd(["sync", dstdir], error_msg="Unable to sync %s" % dstdir)
        # umount
        self.run_cmd(
            ["umount", self.usb_mass_device],
            error_msg="Unable to unmount USB device %s" % self.usb_mass_device,
        )

        return connection
