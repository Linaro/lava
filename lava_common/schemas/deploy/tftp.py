#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Exclusive, Optional, Required

from lava_common.schemas import deploy


def schema():
    resource = deploy.url()

    base = {
        Required("to"): "tftp",
        Required("kernel", msg="needs a kernel to deploy"): deploy.url(
            {Optional("type"): Any("image", "uimage", "zimage")}
        ),
        Optional("dtb"): resource,
        Optional("modules"): resource,
        Optional("preseed"): resource,
        Optional("ramdisk"): deploy.url(
            {
                Optional("install_modules"): bool,
                Optional("install_overlay"): bool,
                Optional("header"): "u-boot",
            }
        ),
        Exclusive("nfsrootfs", "nfs"): deploy.url(
            {
                Optional("install_modules"): bool,
                Optional("install_overlay"): bool,
                Optional("prefix"): str,
            }
        ),
        Exclusive("persistent_nfs", "nfs"): {
            Required("address"): str,
            Optional("install_overlay"): bool,
        },
        Optional("tee"): resource,
    }
    return {**deploy.schema(), **base}
