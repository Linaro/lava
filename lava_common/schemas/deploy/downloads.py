#
# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Optional, Required

from lava_common.schemas import deploy, docker

postprocess_with_docker = {**docker(), Required("steps"): [str]}


def schema():
    base = {
        Required("to"): "downloads",
        Required("images"): {Required(str, "'images' is empty"): deploy.url()},
        Optional("postprocess"): {Required("docker"): postprocess_with_docker},
    }
    return {**deploy.schema(), **base}
