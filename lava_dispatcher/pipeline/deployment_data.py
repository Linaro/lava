# Copyright (C) 2013 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

import sys
from lava_dispatcher.pipeline.action import JobError


def get_deployment_data(distro):
    """
    Returns the deployment data by name, for the cases where we actually need that.
    """
    this_module = sys.modules[__name__]
    try:
        return getattr(this_module, distro)
    except AttributeError:
        raise JobError("%s is not a supported distribution" % distro)


class deployment_data_dict(object):  # pylint: disable=invalid-name, too-few-public-methods

    """
    A read-only dictionary.
    """

    def __init__(self, data):
        self.__data__ = data

    def __getitem__(self, key):
        return self.__data__[key]

    def __str__(self):
        return str(self.__data__)

    def __repr__(self):
        return repr(self.__data__)

    def get(self, key):
        return self.__data__.get(key)


android = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': "root@linaro# ",
    'TESTER_PS1_PATTERN': "root@linaro# ",
    'TESTER_PS1_INCLUDES_RC': False,
    'boot_cmds': 'boot_cmds_android',

    # for lava-test-shell
    'distro': 'android',
    'lava_test_sh_cmd': '/system/bin/sh',
    'lava_test_dir': '/data/lava-%s',
    'lava_test_results_part_attr': 'data_part_android_org',
    'lava_test_results_dir': '/lava-%s',
})


ubuntu = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds',

    # for lava-test-shell
    'distro': 'ubuntu',
    'lava_test_sh_cmd': '/bin/bash',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
})

debian = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds',

    # for lava-test-shell
    'distro': 'debian',
    'lava_test_sh_cmd': '/bin/bash',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
})

oe = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds_oe',

    # for lava-test-shell
    'distro': 'oe',
    'lava_test_sh_cmd': '/bin/sh',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
})


fedora = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds',

    # for lava-test-shell
    'distro': 'fedora',
    'lava_test_sh_cmd': '/bin/bash',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
})
