# Copyright (c) 2010 Linaro
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Module with the HardwareContext model.
"""

from launch_control.models.hw_device import HardwareDevice
from launch_control.utils.json import PlainOldData


class HardwareContext(PlainOldData):
    """
    Model representing the hardware context of a test run.

    The whole context is just a collection of devices.
    """
    __slots__ = ('devices',)

    def __init__(self, devices=None):
        if devices is None:
            devices = []
        self.devices = devices

    @classmethod
    def get_json_attr_types(cls):
        return {'devices': [HardwareDevice]}

