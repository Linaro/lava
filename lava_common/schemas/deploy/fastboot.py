#
# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Optional, Range, Required

from lava_common.schemas import deploy, docker


def schema():
    extra = {
        Optional("apply-overlay"): bool,
        Optional("root_partition"): Range(min=0),
        Optional("sparse"): bool,
        Optional("reboot"): Any(
            "hard-reset",
            "fastboot-reboot",
            "fastboot-reboot-bootloader",
            "fastboot-reboot-fastboot",
        ),
    }

    base = {
        Required("to"): "fastboot",
        Required("images"): {Required(str, "'images' is empty"): deploy.url(extra)},
        Optional("docker"): docker(),
        Optional("connection"): "lxc",  # FIXME: other possible values?
    }
    return {**deploy.schema(), **base}
