#!/usr/bin/env python
#
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
Helper script for running launch_control tests
"""

import os
import sys
import unittest


if __name__ == "__main__":
    try:
        import coverage
    except ImportError:
        coverage = None
        print "WARNING: No coverage test performed"
        print "Please install python-coverage package"
    else:
        # Start coverage check before importing from mocker, to get all of it.
        if os.getenv("PYCOVERAGE", "yes").lower() == "yes":
            coverage.erase()
            coverage.start()
        else:
            coverage = None
    try:
        # XXX: Hack, this is related to the fact that unittest uses
        # __import__() and does not use fromlist=[''] to import packages
        # correctly. Fortunately (?) python imports sub-packages when the
        # package itself is already imported. This is ugly but it works
        import launch_control.tests
        unittest.main(defaultTest='launch_control.tests.test_suite')
    finally:
        if coverage and len(sys.argv) == 1:
            coverage.stop()
            from launch_control.tests import app_modules
            mod_paths = []
            for module in app_modules():
                module = __import__(module, fromlist=[''])
                mod_paths.append(module.__file__)
            coverage.report(mod_paths)
