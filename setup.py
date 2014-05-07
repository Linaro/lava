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
from version import version_tag


setup(
    name='lava-server',
    version=version_tag(),
    author="Zygmunt Krynicki",
    author_email="lava-team@linaro.org",
    namespace_packages=['lava', ],
    packages=find_packages(),
    entry_points=open('entry_points.ini', 'r').read(),
    test_suite="lava_server.tests.run_tests",
    license="AGPL",
    description="LAVA Server",
    long_description="""
    LAVA Server is an application container for various server side
    applications of the LAVA stack. It has an extensible architecture that
    allows to add extra features that live in their own Python packages.  The
    standard LAVA extensions (dashboard and scheduler) are already contained in
    this package.
    """,
    url='http://www.linaro.org/engineering/engineering-groups/validation',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        ("License :: OSI Approved :: GNU Library or Lesser General Public"
         " License (LGPL)"),
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Topic :: Software Development :: Testing",
    ],
    install_requires=[
        'django >= 1.6.1',
        'django-openid-auth >= 0.5',
        'django-restricted-resource >= 0.2.7',
        'django-tables2 >= 0.13.0',
        'docutils >= 0.6',
        'lava-tool >= 0.2',
        'linaro-django-xmlrpc >= 0.4',
        'south >= 0.7.3',
        'versiontools >= 1.8',
        'markdown >= 2.0.3',
        'longerusername',
        'psycopg2',
        'markupsafe',
        'mocker >= 1.0',

        # optional dependency; for authentication with Attlassian Crowd SSO
        # 'django-crowd-rest-backend >= 0.3,

        # dashboard
        'pygments >= 1.2',

        # scheduler
        "lava-dispatcher",
        "simplejson",
        "twisted",
    ],
    data_files=[
        ('/etc/lava-server',
            ['etc/settings.conf',
                'etc/uwsgi.ini',
                'etc/debug.wsgi',
                'etc/lava-server.wsgi',
                'etc/uwsgi.reload']),
        ('/etc/apache2/sites-available',
            ['etc/lava-server.conf']),
        ('/etc/logrotate.d',
            ['etc/logrotate.d/lava-scheduler-log',
                'etc/logrotate.d/lava-server-uwsgi-log']),
        ('/usr/share/lava-server',
            ['instance.template']),
        ('/usr/share/lava-server',
            ['share/add_device.py']),
    ],
    scripts=[
        'lava_server/lava-daemon',
        'share/lava-mount-masterfs',
    ],
    tests_require=[
        'django-testscenarios >= 0.7.2',
    ],
    zip_safe=False,
    include_package_data=True)
