# Copyright (C) 2018 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.exceptions import JobError
from lava_dispatcher.action import Action
from lava_dispatcher.utils.shell import which

if TYPE_CHECKING:
    from typing import Any

    from lava_dispatcher.job import Job
    from lava_dispatcher.shell import ShellSession


class FlashUBootUMSAction(Action):
    """
    Write the image file to USB Mass Storage
    """

    name = "flash-uboot-ums"
    description = "Write the image file to USB Mass Storage"
    summary = "USB Mass storage flash"

    def __init__(self, job: Job, usb_mass_device: str):
        super().__init__(job)
        self.usb_mass_device = usb_mass_device

    def validate(self) -> None:
        super().validate()
        which("bmaptool")
        params: dict[str, Any] = self.job.device["actions"]["boot"]["methods"][
            self.parameters["method"]
        ]["parameters"]
        if "uboot_mass_storage_device" not in params:
            raise JobError("uboot_mass_storage_device is not set")

    def run(
        self, connection: ShellSession | None, max_end_time: float | None
    ) -> ShellSession | None:
        connection = super().run(connection, max_end_time)
        if connection is None:
            raise JobError("connection not found")
        image_file: str | None = self.get_namespace_data(
            action="download-action", label="image", key="file"
        )
        if image_file is None:
            raise JobError("image file not downloaded")
        self.run_cmd(
            [
                "bmaptool",
                "create",
                "--output",
                f"{image_file}.layout",
                image_file,
            ],
            error_msg="Fail to create the bmap layout",
        )
        self.run_cmd(
            [
                "bmaptool",
                "--quiet",
                "copy",
                "--bmap",
                f"{image_file}.layout",
                image_file,
                self.usb_mass_device,
            ],
            error_msg="writing to the USB mass storage device failed",
        )

        connection.sendcontrol("c")
        return connection
