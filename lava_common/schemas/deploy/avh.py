# Copyright (C) 2023-present Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Optional, Range, Required

from lava_common.schemas import deploy


def schema():
    extra = {
        Optional("format"): "ext4",
        Optional("root_partition"): Range(min=0),
        # AVH only supports Linux kernel in the Image format.
        Optional("type"): "image",
    }
    pkg_extra = {**extra, Optional("storage_file"): str}
    images = {Required(str, "'images' is empty"): deploy.url(extra)}
    fw_package = deploy.url(pkg_extra)

    base = {
        Required("to"): "avh",
        Optional("options"): {
            Optional("model"): str,
            Optional("api_endpoint"): str,
            Optional("project_name"): str,
        },
    }

    return Any(
        {**deploy.schema(), **base, Required("images"): images},
        {**deploy.schema(), **base, Required("fw_package"): fw_package},
    )
