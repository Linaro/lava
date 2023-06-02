#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Optional, Range, Required

from lava_common.schemas import deploy, docker, docker_image_format


def schema():
    base = {
        Required("to"): "docker",
        Required("image"): Any(docker_image_format, docker("name")),
        Optional("repeat"): Range(min=1),
    }
    return {**deploy.schema(), **base}
