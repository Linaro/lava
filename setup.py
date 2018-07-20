#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
    name='lava',
    version=version_tag(),
    author="Neil Williams",
    author_email="lava-team@linaro.org",
    namespace_packages=['lava', ],
    packages=find_packages(),
    test_suite="lava_server.tests.run_tests",
    license="AGPL",
    description="LAVA",
    long_description="""
     LAVA is a continuous integration system for deploying operating
     systems onto physical and virtual hardware for running tests.
     Tests can be simple boot testing, bootloader testing and system
     level testing. Extra hardware may be required for some
     system tests. Results are tracked over time and data can be
    exported for further analysis.
    """,
    url='https://www.linaro.org/initiatives/lava/',
    package_data={
        'lava_dispatcher': [
            'dynamic_vm_keys/lava*',
            'devices/*.yaml',
            'lava_test_shell/lava-add-keys',
            'lava_test_shell/lava-add-sources',
            'lava_test_shell/lava-background-process-start',
            'lava_test_shell/lava-background-process-stop',
            'lava_test_shell/lava-echo-ipv4',
            'lava_test_shell/lava-installed-packages',
            'lava_test_shell/lava-install-packages',
            'lava_test_shell/lava-lxc-device-add',
            'lava_test_shell/lava-lxc-device-wait-add',
            'lava_test_shell/lava-os-build',
            'lava_test_shell/lava-probe-channel',
            'lava_test_shell/lava-probe-ip',
            'lava_test_shell/lava-target-ip',
            'lava_test_shell/lava-target-mac',
            'lava_test_shell/lava-target-storage',
            'lava_test_shell/lava-test-case',
            'lava_test_shell/lava-test-feedback',
            'lava_test_shell/lava-test-raise',
            'lava_test_shell/lava-test-reference',
            'lava_test_shell/lava-test-runner',
            'lava_test_shell/lava-test-set',
            'lava_test_shell/lava-test-shell',
            'lava_test_shell/multi_node/*',
            'lava_test_shell/vland/*',
            'lava_test_shell/lmp/*',
            'lava_test_shell/distro/fedora/*',
            'lava_test_shell/distro/android/*',
            'lava_test_shell/distro/ubuntu/*',
            'lava_test_shell/distro/debian/*',
            'lava_test_shell/distro/oe/*',
        ],
    },
    scripts=[
        'lava/dispatcher/lava-run',
        'lava/dispatcher/lava-slave'
    ],
    data_files=[
        ('/usr/share/lava-dispatcher/',
            ['etc/tftpd-hpa',
             'etc/dispatcher.yaml']),
        ('/etc/exports.d',
            ['etc/lava-dispatcher-nfs.exports']),
        ('/etc/modules-load.d/',
            ['etc/lava-modules.conf']),
        ('/etc/logrotate.d/',
            ['etc/logrotate.d/lava-slave-log']),
        ('/usr/share/lava-dispatcher/',
            ['etc/lava-slave.service']),
        ('/etc/lava-server',
         ['etc/settings.conf',
          'etc/env.yaml']),
        ('/etc/apache2/sites-available',
         ['etc/lava-server.conf']),
        ('/etc/logrotate.d',
         ['etc/logrotate.d/django-log',
          'etc/logrotate.d/lava-master-log',
          'etc/logrotate.d/lava-publisher-log',
          'etc/logrotate.d/lava-server-gunicorn-log']),
        ('/usr/share/lava-server',
         ['etc/lava-master.service',
          'etc/lava-publisher.service',
          'etc/lava-logs.service',
          'etc/instance.conf.template',
          'share/render-template.py']),
    ].extend(DEVICE_TYPE_TEMPLATES),
    tests_require=[
        'django-testscenarios >= 0.9.1',
    ],
    zip_safe=False,
    include_package_data=True)
