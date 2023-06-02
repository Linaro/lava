#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Optional, Required

from lava_common.schemas import deploy


def schema():
    resource = deploy.url()

    base = {
        Required("to"): "nbd",
        Required("kernel", msg="needs a kernel to deploy"): deploy.url(
            {Optional("type"): Any("image", "uimage", "zimage")}
        ),
        Required("nbdroot"): resource,
        Required("initrd"): resource,
        Optional("dtb"): resource,
    }
    return {**deploy.schema(), **base}
