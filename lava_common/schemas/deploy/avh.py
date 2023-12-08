#
# Copyright (C) 2019 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Optional, Range, Required

from lava_common.schemas import deploy


def schema():
    extra = {
        Optional("format"): "ext4",
        Optional("root_partition"): Range(min=0),
        # AVH only supports Linux kernel in the Image format.
        Optional("type"): "image",
    }
    base = {
        Required("to"): "avh",
        Optional("options"): {
            Optional("model"): str,
            Optional("api_endpoint"): str,
            Optional("project_name"): str,
        },
        Required("images"): {Required(str, "'images' is empty"): deploy.url(extra)},
    }
    return {**deploy.schema(), **base}
