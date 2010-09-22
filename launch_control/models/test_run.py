# Copyright (c) 2010 Linaro Limited
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
Module with the TestRun model.
"""

from datetime import datetime
from uuid import (UUID, uuid1)

from launch_control.models.hw_context import HardwareContext
from launch_control.models.sw_context import SoftwareContext
from launch_control.models.test_result import TestResult
from launch_control.utils.json import PlainOldData


class TestRun(PlainOldData):
    """
    Test run is a data container for test results that were
    captured during a single run of a particular test
    """
    __slots__ = ('analyzer_assigned_uuid',
            'analyzer_assigned_date',
            'time_check_performed',
            'attributes',
            'test_id',
            'test_results',
            'attachments',
            'hw_context',
            'sw_context')

    def __init__(self,
            analyzer_assigned_uuid=None,
            analyzer_assigned_date=None,
            time_check_performed=False,
            attributes=None,
            test_id=None,
            test_results=None,
            attachments=None,
            hw_context=None,
            sw_context=None,
            ):
        self.analyzer_assigned_uuid = analyzer_assigned_uuid or uuid1()
        self.analyzer_assigned_date = analyzer_assigned_date or datetime.now()
        self.time_check_performed = time_check_performed
        self.attributes = attributes or {}
        self.test_id = test_id
        self.test_results = test_results or []
        self.attachments = attachments or {}
        self.sw_context = sw_context
        self.hw_context = hw_context

    @classmethod
    def get_json_attr_types(self):
        return {'analyzer_assigned_date': datetime,
                'analyzer_assigned_uuid': UUID,
                'sw_context': SoftwareContext,
                'hw_context': HardwareContext,
                'test_results': [TestResult]}

    def get_stats(self):
        """
        Get statistics about this test run.

        Returns a dictionary with count of each TestResult.result
        """
        stats = {}
        for result in self.test_results:
            if result.result not in stats:
                stats[result.result] = 0
            stats[result.result] += 1
        return stats
