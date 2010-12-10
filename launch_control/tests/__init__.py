# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Package with unit tests for launch_control
"""

import doctest
import unittest


def app_modules():
    return [
            'launch_control.models',
            'launch_control.models.bundle',
            'launch_control.models.hw_context',
            'launch_control.models.hw_device',
            'launch_control.models.sw_context',
            'launch_control.models.sw_image',
            'launch_control.models.sw_package',
            'launch_control.models.test_case',
            'launch_control.models.test_result',
            'launch_control.models.test_run',
            'launch_control.utils.call_helper',
            'launch_control.utils.filesystem',
            'launch_control.utils.import_prohibitor',
            ]


def test_modules():
    return [
            'launch_control.tests.test_dashboard_bundle_format_1_0',
            'launch_control.tests.test_utils_filesystem',
            ]


def test_suite():
    """
    Build an unittest.TestSuite() object with all the tests in _modules.
    Each module is harvested for both regular unittests and doctests
    """
    modules = app_modules() + test_modules()
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for name in modules:
        unit_suite = loader.loadTestsFromName(name)
        suite.addTests(unit_suite)
        doc_suite = doctest.DocTestSuite(name)
        suite.addTests(doc_suite)
    return suite
