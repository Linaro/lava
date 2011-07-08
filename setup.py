#!/usr/bin/env python
#
# Copyright (C) 2011 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
#
# This file is part of LAVA Scheduler.
#
# LAVA Scheduler is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License version 3 as
# published by the Free Software Foundation
#
# LAVA Scheduler is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Scheduler.  If not, see <http://www.gnu.org/licenses/>.

from setuptools import setup, find_packages

setup(
    name='lava-scheduler',
    version=":versiontools:lava_scheduler_app:__version__",
    author="Michael Hudson-Doyle",
    author_email="michael.hudson@linaro.org",
    packages=find_packages() + [
        'twisted/plugins',
    ],
    license="AGPL",
    description="LAVA Scheduler Application",
    entry_points="""
    [lava_server.extensions]
    scheduler = lava_scheduler_app.extension:SchedulerExtension
    """,
    scripts=["lava-scheduler"],
    install_requires=[
        "lava-server >= 0.1",
        "twisted",
        "south",
    ],
    setup_requires=[
        "versiontools >= 1.3.1",
    ],
    tests_require=[
        "django-testscenarios",
    ],
    zip_safe=False,
    include_package_data=True)
