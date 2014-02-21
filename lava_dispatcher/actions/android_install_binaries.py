# Copyright (C) 2012 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
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
# along with this program; if not, see <http://www.gnu.org/licenses>.

import logging

from lava_dispatcher.actions import BaseAction, null_or_empty_schema


class cmd_android_install_binaries(BaseAction):

    parameters_schema = null_or_empty_schema

    def run(self):
        driver_tarball = self.client.config.android_binary_drivers
        partition = self.client.config.root_part

        if driver_tarball is None:
            logging.warning("android_binary_drivers not defined in any config")
            return

        self.client.target_device.extract_tarball(driver_tarball, partition)
