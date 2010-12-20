#!/usr/bin/env python
#
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

from setuptools import setup, find_packages

from dashboard_app import __version__


setup(
        name = 'launch-control',
        version = str(__version__),
        author = "Zygmunt Krynicki",
        author_email = "zygmunt.krynicki@linaro.org",
        packages = ['dashboard_app', 'launch_control', 'dashboard_server'],
        scripts = ['lc-tool.py'],
        long_description = """
        Launch control is a collection of tools for distribution wide QA
        management. It is implemented for the Linaro organization.
        """,
        url='https://launchpad.net/launch-control',
        test_suite='launch_control.tests.test_suite',
        classifiers=[
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: GNU Affero General Public License v3",
            "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 2.6",
            "Topic :: Software Development :: Testing",
            ],
        install_requires = [
            'Django >= 1.1',
            'django-openid-auth >= 0.2',
            'django-restricted-resource >= 0.2',
            'django-reports >= 0.1',
            'docutils >= 0.6',
            'linaro-python-json >= 1.1',
            ],
        tests_require = [
            'django-testscenarios >= 0.3',
            ],
        ),

