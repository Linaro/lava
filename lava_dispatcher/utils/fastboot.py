# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from lava_common.exceptions import FastbootDeviceNotFound, JobError
from lava_dispatcher.power import PowerOff
from lava_dispatcher.utils.containers import OptionalContainerAction
from lava_dispatcher.utils.decorator import retry
from lava_dispatcher.utils.shell import which

if TYPE_CHECKING:
    from lava_dispatcher.action import Action
    from lava_dispatcher.shell import ShellSession


class OptionalContainerFastbootAction(OptionalContainerAction):
    def get_fastboot_cmd(self, cmd: list[str]) -> list[str]:
        serial_number: str = self.job.device["fastboot_serial_number"]
        fastboot_opts: list[str] = self.job.device["fastboot_options"]
        fastboot_cmd: list[str] = (
            ["fastboot", "-s", serial_number] + cmd + fastboot_opts
        )
        return fastboot_cmd

    def run_fastboot(self, cmd: list[str]) -> None:
        self.run_maybe_in_container(self.get_fastboot_cmd(cmd))

    def get_fastboot_output(self, cmd: list[str], allow_fail: bool = False) -> str:
        return self.get_output_maybe_in_container(
            self.get_fastboot_cmd(cmd), allow_fail=allow_fail
        )

    def on_timeout(self) -> None:
        self.logger.error("fastboot timing out, power-off the DuT")
        power_off = PowerOff(self.job)
        power_off.run(None, self.timeout.duration)


class DetectFastbootDevice(OptionalContainerFastbootAction):
    name = "detect-fastboot-device"
    description = "Detect fastboot device serial number."
    summary = "Set fastboot SN if only one device found."

    @classmethod
    def add_if_needed(cls, action: Action) -> None:
        board_id: str = action.job.device["fastboot_serial_number"]
        if board_id != "0000000000":
            return

        if not action.job.device.get("fastboot_auto_detection", False):
            return

        if action.get_namespace_data(action=cls.name, label=cls.name, key="added"):
            return

        if action.pipeline is None:
            return

        action.pipeline.add_action(cls(action.job))
        action.set_namespace_data(
            action=cls.name,
            label=cls.name,
            key="added",
            value=True,
        )

    def validate(self) -> None:
        super().validate()
        if not self.is_container():
            which("fastboot")

    def set_sn(self, name: str, sn: str) -> None:
        # Respect sn set in device dictionary.
        if self.job.device.get(name, "0000000000") == "0000000000":
            self.logger.info(f"{name!r} is set to {sn!r}")
            self.job.device[name] = sn

            if name == "board_id":
                # Device passing to container needs 'device_info[0].board_id'.
                self.job.device["device_info"] = [{"board_id": sn}]
                self.logger.info(f"'device_info[0].board_id' is set to {sn}")

    @retry(exception=FastbootDeviceNotFound, retries=10, delay=3)
    def detect(self) -> None:
        # 'fastboot devices' output line example: a2c22e48\tfastboot\n
        output = self.get_output_maybe_in_container(["fastboot", "devices"])
        devices = [
            str(line.split()[0])
            for line in output.strip().split("\n")
            if line.split()[-1:] == ["fastboot"]
        ]

        if len(devices) > 1:
            raise JobError(f"More then one fastboot devices found: {devices}")
        if len(devices) < 1:
            raise FastbootDeviceNotFound("Fastboot device not found.")

        fastboot_serial_number = devices[0]
        self.logger.info(f"Detected fastboot serial number: {fastboot_serial_number}")

        self.set_sn("fastboot_serial_number", fastboot_serial_number)
        self.set_sn("adb_serial_number", fastboot_serial_number)
        # wait-device-boardid needs board_id.
        self.set_sn("board_id", fastboot_serial_number)

    def run(
        self, connection: ShellSession | None, max_end_time: float | None
    ) -> ShellSession | None:
        connection = super().run(connection, max_end_time)

        # Wait a while for the device to enter fastboot.
        time.sleep(3)
        # Try the detection up to 10 times.
        self.detect()

        return connection
