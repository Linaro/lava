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
Module with the TestCase model.
"""

from launch_control.utils.json.pod import PlainOldData


class TestCase(PlainOldData):
    """
    TestCase model.

    Currently contains just two fields:
        - test_case_id (test-case specific ID)
        - name (human readable)
    """

    __slots__ = ('test_case_id', 'name')

    def __init__(self, test_case_id, name):
        self.test_case_id = test_case_id
        self.name = name
