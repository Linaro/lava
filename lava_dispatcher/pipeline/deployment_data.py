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
    if distro is '':
        raise JobError("Missing 'os' value for deployment - unable to identify operating system for deployment data.")
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

    def get(self, *args):
        if len(args) == 1:
            return self.__data__.get(args[0])
        else:
            if args[0] in self.__data__.keys():
                return self.__data__.get(args[0])
            else:
                return args[1]

    def keys(self):
        """
        Exists principally so that the return looks like a list
        of keys of a normal dict object. The most common thing
        to do with the return value of dict.keys() is to iterate
        or just with if _ in dict.keys():, so take the line of
        least surprise, despite what 2to3 thinks.
        https://docs.python.org/3/library/stdtypes.html#dict-views
        """
        return self.__data__.keys()

android = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': "root@linaro# ",
    'TESTER_PS1_PATTERN': "root@linaro# ",
    'TESTER_PS1_INCLUDES_RC': False,
    'boot_cmds': 'boot_cmds_android',
    'line_separator': '\n',

    # for lava-test-shell
    'distro': 'android',
    'lava_test_sh_cmd': '/system/bin/sh',
    'lava_test_dir': '/data/local/tmp/lava-%s',
    'lava_test_results_part_attr': 'data_part_android_org',
    'lava_test_results_dir': '/data/local/tmp/lava-%s',
    'lava_test_shell_file': None,
})


ubuntu = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds',
    'line_separator': '\n',

    # for lava-test-shell
    'distro': 'ubuntu',
    'tar_flags': '--warning no-timestamp',
    'lava_test_sh_cmd': '/bin/bash',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
    'lava_test_shell_file': '~/.bashrc',
})

debian = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds',
    'line_separator': '\n',

    # for lava-test-shell
    'distro': 'debian',
    'tar_flags': '--warning no-timestamp',
    'lava_test_sh_cmd': '/bin/bash',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
    'lava_test_shell_file': '~/.bashrc',
})

oe = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds_oe',
    'line_separator': '\n',

    # for lava-test-shell
    'distro': 'oe',
    'lava_test_sh_cmd': '/bin/sh',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
    'lava_test_shell_file': '~/.bashrc',
})

lede = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds_lede',
    'line_separator': '\n',

    # for lava-test-shell
    'distro': 'lede',
    'lava_test_sh_cmd': '/bin/sh',
    'lava_test_dir': '/tmp/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/tmp/lava-results-%s',
    'lava_test_shell_file': None,
})

fedora = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds',
    'line_separator': '\n',

    # for lava-test-shell
    'distro': 'fedora',
    'tar_flags': '--warning no-timestamp',
    'lava_test_sh_cmd': '/bin/bash',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
    'lava_test_shell_file': '~/.bashrc',
})

centos = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds',
    'line_separator': '\n',

    # for lava-test-shell
    'distro': 'centos',
    'tar_flags': '--warning no-timestamp',
    'lava_test_sh_cmd': '/bin/bash',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
    'lava_test_shell_file': '~/.bashrc',
})

debian_installer = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds',
    'line_separator': '\n',
    'installer_extra_cmd': 'cp -r /lava-* /target/ || true ;',

    # DEBIAN_INSTALLER preseeeding
    'locale': 'debian-installer/locale=en_US',
    'keymaps': 'console-keymaps-at/keymap=us keyboard-configuration/xkb-keymap=us',
    'netcfg': 'netcfg/choose_interface=auto netcfg/get_hostname=debian netcfg/get_domain=',
    'base': 'auto=true install noshell debug verbose BOOT_DEBUG=1 DEBIAN_FRONTEND=text ',
    'prompts': [
        'ERROR: Installation step failed',
        'Press enter to continue',
        'reboot: Power down',
        'Requesting system poweroff'
    ],

    # for lava-test-shell
    'distro': 'debian',
    'lava_test_sh_cmd': '/bin/bash',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
    'lava_test_shell_file': '~/.bashrc',
})

centos_installer = deployment_data_dict({  # pylint: disable=invalid-name
    'TESTER_PS1': r"linaro-test [rc=$(echo \$?)]# ",
    'TESTER_PS1_PATTERN': r"linaro-test \[rc=(\d+)\]# ",
    'TESTER_PS1_INCLUDES_RC': True,
    'boot_cmds': 'boot_cmds',
    'line_separator': '\n',
    'installer_extra_cmd': 'curl {OVERLAY_URL} > /lava-overlay.tar.gz\ntar -zxvf /lava-overlay.tar.gz -C /',
    'preseed_to_ramdisk': "preseed.cfg",

    # for lava-test-shell
    'distro': 'centos',
    'lava_test_sh_cmd': '/bin/bash',
    'lava_test_dir': '/lava-%s',
    'lava_test_results_part_attr': 'root_part',
    'lava_test_results_dir': '/lava-%s',
    'lava_test_shell_file': '~/.bashrc',
})
