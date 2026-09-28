# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from lava_dispatcher.utils.containers import OptionalContainerAction


class OptionalContainerAdbAction(OptionalContainerAction):
    def get_adb_cmd(self, cmd: list[str]) -> list[str]:
        serial_number = self.job.device["adb_serial_number"]
        return ["adb", "-s", serial_number] + cmd

    def run_adb(self, cmd: list[str]) -> None:
        self.run_maybe_in_container(self.get_adb_cmd(cmd))

    def get_adb_output(self, cmd: list[str], allow_fail: bool = False) -> str:
        return self.get_output_maybe_in_container(
            self.get_adb_cmd(cmd), allow_fail=allow_fail
        )
