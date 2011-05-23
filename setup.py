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

import dashboard_app
import versiontools


setup(
    name='lava-server',
    version=versiontools.format_version(dashboard_app.__version__),
    author="Zygmunt Krynicki",
    author_email="zygmunt.krynicki@linaro.org",
    packages=find_packages(),
    license="AGPL",
    description="LAVA Server Application Container",
    long_description="""
    LAVA Server is an application container for various server side
    applications of the LAVA stack. Currently it can host the dashboard
    application. More applications (such as the scheduler and driver)
    will be added later.
    """,
    url='https://launchpad.net/lava-server',
    #test_suite='launch_control.tests.test_suite',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.6",
        "Topic :: Software Development :: Testing",
    ],
    install_requires=[
        'Django >= 1.2',
        'django-openid-auth >= 0.2',
        'django-pagination >= 1.0.7.1',
        'django-reports >= 0.2.3',
        'django-restricted-resource >= 0.2.3',
        "django-staticfiles >= 0.3.4",
        'docutils >= 0.6',
        'linaro-dashboard-bundle >= 1.4',
        'linaro-json >= 2.0',
        'python-openid >= 2.2.4',  # this should be a part of django-openid-auth deps
        'versiontools >= 1.1',
    ],
    setup_requires=[
        'versiontools >= 1.1',
    ],
    tests_require=[
        'django-testscenarios >= 0.5.3',
    ],
    zip_safe=False,
    include_package_data=True)
