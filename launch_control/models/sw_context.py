# Copyright (C) 2010 Linaro Limited
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
Module with the SoftwareContext model.
"""

from launch_control.models.sw_image import SoftwareImage
from launch_control.models.sw_package import SoftwarePackage
from launch_control.utils.json import PlainOldData


class SoftwareContext(PlainOldData):
    """
    Model representing the software context of a test run.

    The whole context is a collection of packages and a name
    of the operating system image.
    """
    __slots__ = ('packages', 'sw_image')

    def __init__(self, packages = None, sw_image = None):
        self.packages = packages or []
        self.sw_image = sw_image

    @classmethod
    def get_json_attr_types(cls):
        return {'packages': [SoftwarePackage],
                'sw_image': SoftwareImage}
