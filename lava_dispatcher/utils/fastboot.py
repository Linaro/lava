# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import subprocess
import time
from typing import TYPE_CHECKING

from lava_common.exceptions import FastbootDeviceNotFound, JobError
from lava_dispatcher.action import Action
from lava_dispatcher.power import PowerOff
from lava_dispatcher.utils.containers import OptionalContainerAction
from lava_dispatcher.utils.decorator import retry
from lava_dispatcher.utils.shell import which

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class OptionalContainerFastbootAction(OptionalContainerAction):
    def get_fastboot_cmd(self, cmd):
        serial_number = self.job.device["fastboot_serial_number"]
        fastboot_opts = self.job.device["fastboot_options"]
        fastboot_cmd = ["fastboot", "-s", serial_number] + cmd + fastboot_opts
        return fastboot_cmd

    def run_fastboot(self, cmd):
        self.run_maybe_in_container(self.get_fastboot_cmd(cmd))

    def get_fastboot_output(self, cmd, **kwargs):
        return self.get_output_maybe_in_container(self.get_fastboot_cmd(cmd), **kwargs)

    def on_timeout(self):
        self.logger.error("fastboot timing out, power-off the DuT")
        power_off = PowerOff(self.job)
        power_off.run(None, self.timeout.duration)


class DetectFastbootDevice(Action):
    name = "detect-fastboot-device"
    description = "Detect fastboot device serial number."
    summary = "Set fastboot SN if only one device found."

    def __init__(self, job: Job):
        super().__init__(job)
        self.fastboot_path = None

    @classmethod
    def add_if_needed(cls, action) -> None:
        board_id = action.job.device["fastboot_serial_number"]
        if board_id == "0000000000" and action.job.device.get(
            "fastboot_auto_detection", False
        ):
            if not action.get_namespace_data(
                action=cls.name, label=cls.name, key="added"
            ):
                action.pipeline.add_action(cls(action.job))
                action.set_namespace_data(
                    action=cls.name,
                    label=cls.name,
                    key="added",
                    value=True,
                )

    def validate(self):
        super().validate()
        self.fastboot_path = which("fastboot")

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
    def detect(self):
        cmd = subprocess.run(
            [self.fastboot_path, "devices"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if cmd.returncode == 0:
            # 'fastboot devices' output line example: a2c22e48\tfastboot\n
            output = cmd.stdout.strip().split("\n")
            devices = [
                str(line.split("\t")[0])
                for line in output
                if line.endswith("\tfastboot")
            ]

            if len(devices) > 1:
                raise JobError(f"More then one fastboot devices found: {devices}")
            if len(devices) < 1:
                raise FastbootDeviceNotFound("Fastboot device not found.")

            fastboot_serial_number = devices[0]
            self.logger.info(
                f"Detected fastboot serial number: {fastboot_serial_number}"
            )

            self.set_sn("fastboot_serial_number", fastboot_serial_number)
            self.set_sn("adb_serial_number", fastboot_serial_number)
            # wait-device-boardid needs board_id.
            self.set_sn("board_id", fastboot_serial_number)
        else:
            raise JobError(f"Failed to run 'fastboot devices': {cmd.stderr}")

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        # Wait a while for the device to enter fastboot.
        time.sleep(3)
        # Try the detection up to 10 times.
        self.detect()

        return connection
