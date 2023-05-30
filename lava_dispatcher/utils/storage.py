# Copyright (C) 2018 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Action, JobError
from lava_dispatcher.utils.shell import which


class FlashUBootUMSAction(Action):
    """
    Write the image file to USB Mass Storage
    """

    name = "flash-uboot-ums"
    description = "Write the image file to USB Mass Storage"
    summary = "USB Mass storage flash"

    def __init__(self, usb_mass_device):
        super().__init__()
        self.params = None
        self.usb_mass_device = usb_mass_device

    def validate(self):
        super().validate()
        which("bmaptool")
        self.params = self.job.device["actions"]["boot"]["methods"][
            self.parameters["method"]
        ]["parameters"]
        if "uboot_mass_storage_device" not in self.params:
            raise JobError("uboot_mass_storage_device is not set")

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        image_file = self.get_namespace_data(
            action="download-action", label="image", key="file"
        )
        cmd = f"bmaptool create --output {image_file}.layout {image_file}"
        self.run_cmd(cmd, error_msg="Fail to create the bmap layout")
        cmd = f"bmaptool --quiet copy --bmap {image_file}.layout {image_file} {self.usb_mass_device}"
        self.run_cmd(cmd, error_msg="writing to the USB mass storage device failed")

        connection.sendcontrol("c")
        return connection
