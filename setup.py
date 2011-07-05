#!/usr/bin/env python
#
# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

from setuptools import setup, find_packages


setup(
    name='lava-server',
    version=":versiontools:lava_server:__version__",
    author="Zygmunt Krynicki",
    author_email="zygmunt.krynicki@linaro.org",
    packages=find_packages(),
    entry_points="""
        [console_scripts]
        lava-server = lava_server.manage:main
    """,
    test_suite="lava_server.tests.run_tests",
    license="AGPL",
    description="LAVA Server Application Container",
    long_description="""
    LAVA Server is an application container for various server side
    applications of the LAVA stack. Currently it can host the dashboard
    application. More applications (such as the scheduler and driver)
    will be added later.
    """,
    url='https://launchpad.net/lava-server',
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
        "django-staticfiles == 0.3.4",
        'django < 1.3',
        'django-openid-auth >= 0.2',
        'python-openid >= 2.2.4',  # this should be a part of django-openid-auth deps
        'versiontools >= 1.3.1',
        'linaro-django-xmlrpc >= 0.3.2',
    ],
    setup_requires=[
        'versiontools >= 1.3.1',
    ],
    tests_require=[
        'django-testscenarios >= 0.7.1',
    ],
    zip_safe=False,
    include_package_data=True)
