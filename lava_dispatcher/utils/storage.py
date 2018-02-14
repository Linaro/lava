# Copyright (C) 2018 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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

from lava_dispatcher.action import (
    Action,
    InfrastructureError,
    JobError,
    ConfigurationError,
    Timeout)
from lava_dispatcher.utils.constants import BOOTLOADER_DEFAULT_CMD_TIMEOUT
import time


class FlashUBootUMSAction(Action):
    """
    Write the image file to USB Mass Storage
    """

    name = "flash-uboot-ums"
    description = "Write the image file to USB Mass Storage"
    summary = "USB Mass storage flash"

    def __init__(self, usb_mass_device):
        super(FlashUBootUMSAction, self).__init__()
        self.params = None
        self.usb_mass_device = usb_mass_device

    def validate(self):
        super(FlashUBootUMSAction, self).validate()
        self.params = self.job.device['actions']['boot']['methods'][self.parameters['method']]['parameters']
        if self.params.get('uboot_mass_storage_device', False):
            self.ums_device = self.params['uboot_mass_storage_device']
        else:
            raise JobError("uboot_mass_storage_device is not set")

    def run(self, connection, max_end_time, args=None):
        image_file = self.get_namespace_data(action='download-action', label='image', key='file')
        cmd = 'dd if={} of={} bs=1M oflag=sync conv=fsync'.format(image_file, self.usb_mass_device)
        if not self.run_command(cmd.split(' '), allow_silent=True):
            raise JobError("writing to the USB mass storage device failed")

        connection.sendcontrol('c')
        return connection
