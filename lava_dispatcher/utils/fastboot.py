# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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
