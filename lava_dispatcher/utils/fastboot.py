# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from lava_dispatcher.power import PowerOff
from lava_dispatcher.utils.containers import OptionalContainerAction


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
        power_off = PowerOff()
        power_off.job = self.job
        power_off.run(None, self.timeout.duration)
