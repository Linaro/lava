# Copyright (C) 2013-2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


android = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "android",
}

apertis = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "apertis",
    "tar_flags": "--warning no-timestamp",
}

archlinux = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "archlinux",
    "tar_flags": "--warning no-timestamp",
}

centos = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "centos",
    "tar_flags": "--warning no-timestamp",
}

centos_installer = {
    "line_separator": "\n",
    "installer_extra_cmd": "curl {OVERLAY_URL} > /lava-overlay.tar.gz\ntar -zxvf /lava-overlay.tar.gz -C /",
    "preseed_to_ramdisk": "preseed.cfg",
    # for lava-test-shell
    "distro": "centos",
}

debian = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "debian",
    "tar_flags": "--warning no-timestamp",
}

debian_installer = {
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
}

fedora = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "fedora",
    "tar_flags": "--warning no-timestamp",
}

lede = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "lede",
}

oe = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "oe",
}

qnx = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "qnx",
    "tar_flags": "--warning no-timestamp",
}

slackware = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "slackware",
    "tar_flags": "--warning no-timestamp",
}

ubuntu = {
    "line_separator": "\n",
    # for lava-test-shell
    "distro": "ubuntu",
    "tar_flags": "--warning no-timestamp",
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
    "qnx": qnx,
    "slackware": slackware,
    "ubuntu": ubuntu,
}


def get_deployment_data(distro):
    """
    Returns the deployment data by name
    """
    return deployments.get(distro, {})
