#!/usr/bin/env python
# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

from setuptools import setup, find_packages


setup(
    name='lava-dashboard',
    version=":versiontools:dashboard_app:__version__",
    author="Zygmunt Krynicki",
    author_email="zygmunt.krynicki@linaro.org",
    packages=find_packages(),
    license="AGPL",
    description="Validation Dashboard for LAVA Server",
    long_description="""
    Validation Dashboard is a repository for test results.
    """,
    url='https://launchpad.net/lava-dashboard',
    #test_suite='dashboard_app.tests.test_suite',
    entry_points="""
        [lava_server.extensions]
        dashboard=dashboard_app.extension:DashboardExtension
        """,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Topic :: Software Development :: Testing",
    ],
    install_requires=[
        'Django >= 1.2',
        'django-restricted-resource >= 0.2.6',
        'django-staticfiles == 0.3.4',
        'docutils >= 0.6',
        'lava-server >= 0.8',
        'linaro-dashboard-bundle >= 1.5.2',
        'linaro-django-pagination >= 2.0.2',
        'linaro-django-xmlrpc >= 0.4',
        'linaro-json >= 2.0.1',  # TODO: use json-schema-validator
        'pygments >= 1.2',
        'south >= 0.7.3',
        'versiontools >= 1.8',
    ],
    setup_requires=[
        'versiontools >= 1.8',
    ],
    tests_require=[
        'django-testscenarios >= 0.7.1',
        'mocker >= 1.0',
    ],
    zip_safe=False,
    include_package_data=True
)

