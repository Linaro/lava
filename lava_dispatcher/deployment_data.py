# Copyright (C) 2013-2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
# Author: Neil Williams <neil.williams@linaro.org>
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


android = {
    "TESTER_PS1": "root@linaro# ",
    "TESTER_PS1_PATTERN": "root@linaro# ",
    "TESTER_PS1_INCLUDES_RC": False,
    "boot_cmds": "boot_cmds_android",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "android",
    "lava_test_sh_cmd": "/system/bin/sh",
    "lava_test_dir": "/data/local/tmp/lava-%s",
    "lava_test_results_part_attr": "data_part_android_org",
    "lava_test_results_dir": "/data/local/tmp/lava-%s",
    "lava_test_shell_file": None,
}

apertis = {
    "TESTER_PS1": r"apertis-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"apertis-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "apertis",
    "tar_flags": "--warning no-timestamp",
    "lava_test_sh_cmd": "/bin/sh",
    "lava_test_dir": "/var/lib/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/var/lib/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

archlinux = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "archlinux",
    "tar_flags": "--warning no-timestamp",
    "lava_test_sh_cmd": "/bin/bash",
    "lava_test_dir": "/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

centos = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "centos",
    "tar_flags": "--warning no-timestamp",
    "lava_test_sh_cmd": "/bin/bash",
    "lava_test_dir": "/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

centos_installer = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds",
    "line_separator": "\n",
    "installer_extra_cmd": "curl {OVERLAY_URL} > /lava-overlay.tar.gz\ntar -zxvf /lava-overlay.tar.gz -C /",
    "preseed_to_ramdisk": "preseed.cfg",
    # for lava-test-shell
    "distro": "centos",
    "lava_test_sh_cmd": "/bin/bash",
    "lava_test_dir": "/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

debian = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "debian",
    "tar_flags": "--warning no-timestamp",
    "lava_test_sh_cmd": "/bin/bash",
    "lava_test_dir": "/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

debian_installer = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds",
    "line_separator": "\n",
    "installer_extra_cmd": "cp -r /lava-* /target/ || true",
    # DEBIAN_INSTALLER preseeeding
    "locale": "debian-installer/locale=en_US",
    "keymaps": "console-keymaps-at/keymap=us keyboard-configuration/xkb-keymap=us",
    "netcfg": "netcfg/choose_interface=auto netcfg/get_hostname=debian netcfg/get_domain=",
    "base": "auto=true install noshell debug verbose BOOT_DEBUG=1 DEBIAN_FRONTEND=text ",
    "prompts": [
        "ERROR: Installation step failed",
        "ERROR: Failed to retrieve the preconfiguration file",
        "Press enter to continue",
        "reboot: Power down",
    ],
    # for lava-test-shell
    "distro": "debian",
    "lava_test_sh_cmd": "/bin/bash",
    "lava_test_dir": "/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

fedora = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "fedora",
    "tar_flags": "--warning no-timestamp",
    "lava_test_sh_cmd": "/bin/bash",
    "lava_test_dir": "/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

lede = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds_lede",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "lede",
    "lava_test_sh_cmd": "/bin/sh",
    "lava_test_dir": "/tmp/lava-%s",  # nosec - on the DUT
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/tmp/lava-results-%s",  # nosec - on the DUT
    "lava_test_shell_file": None,
}

oe = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds_oe",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "oe",
    "lava_test_sh_cmd": "/bin/sh",
    "lava_test_dir": "/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

slackware = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "slackware",
    "tar_flags": "--warning no-timestamp",
    "lava_test_sh_cmd": "/bin/bash",
    "lava_test_dir": "/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

ubuntu = {
    "TESTER_PS1": r"linaro-test [rc=$(echo \$?)]# ",
    "TESTER_PS1_PATTERN": r"linaro-test \[rc=(\d+)\]# ",
    "TESTER_PS1_INCLUDES_RC": True,
    "boot_cmds": "boot_cmds",
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "ubuntu",
    "tar_flags": "--warning no-timestamp",
    "lava_test_sh_cmd": "/bin/sh",
    "lava_test_dir": "/lava-%s",
    "lava_test_results_part_attr": "root_part",
    "lava_test_results_dir": "/lava-%s",
    "lava_test_shell_file": "~/.bashrc",
}

deployments = {
    "android": android,
    "apertis": apertis,
    "archlinux": archlinux,
    "centos": centos,
    "centos_installer": centos_installer,
    "debian": debian,
    "debian_installer": debian_installer,
    "fedora": fedora,
    "lede": lede,
    "oe": oe,
    "slackware": slackware,
    "ubuntu": ubuntu,
}


def get_deployment_data(distro):
    """
    Returns the deployment data by name
    """
    return deployments.get(distro, {})
