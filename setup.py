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

import os
import glob
import fnmatch
from setuptools import setup, find_packages
from version import version_tag


# based on https://wiki.python.org/moin/Distutils/Tutorial
def find_data_files(srcdir, *wildcards):
    badnames = [".pyc", "~"]

    def walk_helper(arg, dirname, files):
        names = []
        lst, wilds = arg
        for wcard in wilds:
            wc_name = os.path.normpath(os.path.join(dirname, wcard))
            for listed in files:
                filename = os.path.normpath(os.path.join(dirname, listed))
                if not any(bad in filename for bad in badnames):
                    if fnmatch.fnmatch(filename, wc_name) and not os.path.isdir(filename):
                        names.append(filename)
        if names:
            lst.append(('/etc/lava-server/dispatcher-config/device-types', names))
    file_list = []
    walk_helper(
        (file_list, wildcards), srcdir,
        [os.path.basename(f) for f in glob.glob(os.path.normpath(os.path.join(srcdir, '*')))])
    return file_list

SRCDIR = os.path.join('.', 'lava_scheduler_app', 'tests', 'device-types')
DEVICE_TYPE_TEMPLATES = find_data_files(SRCDIR, '*.jinja2')

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
        'django >= 1.8',
        'django-restricted-resource >= 2015.09',
        'django-tables2 >= 1.2',
        'docutils >= 0.6',
        'lava-tool >= 0.2',
        'versiontools >= 1.8',
        'markdown >= 2.0.3',
        'psycopg2',
        'markupsafe',
        'mocker >= 1.0',
        'netifaces >= 0.10.4',
        'django-kvstore',
        'pyzmq',
        'jinja2',
        'django-auth-ldap >= 1.1.8',
        'voluptuous',
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
          'etc/uwsgi.reload',
          'etc/env.yaml']),
        ('/etc/apache2/sites-available',
         ['etc/lava-server.conf']),
        ('/etc/logrotate.d',
         ['etc/logrotate.d/lava-scheduler-log',
          'etc/logrotate.d/lava-master-log',
          'etc/logrotate.d/lava-server-uwsgi-log',
          'etc/logrotate.d/django-log']),
        ('/usr/share/lava-server',
         ['instance.template']),
        ('/usr/share/lava-server',
         ['share/add_device.py',
          'etc/lava-master.service',
          'share/render-template.py']),
    ].extend(DEVICE_TYPE_TEMPLATES),
    scripts=[
        'lava_server/lava-daemon',
        'lava_server/lava-master',
        'share/lava-mount-masterfs',
    ],
    tests_require=[
        'django-testscenarios >= 0.7.2',
    ],
    zip_safe=False,
    include_package_data=True)
