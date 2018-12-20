# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from voluptuous import Any, Exclusive, Optional, Required

from lava_common.schemas import deploy


def schema(live=False):
    resource = deploy.url()
    resource_ext = {
        **resource,
        Optional("install_modules"): bool,
        Optional("install_overlay"): bool,
    }

    base = {
        Required("to"): "tftp",
        Required("kernel", msg="needs a kernel to deploy"): {
            **resource,
            Optional("type"): Any("image", "uimage", "zimage"),
        },
        Optional("dtb"): resource,
        Optional("modules"): resource,
        Optional("preseed"): resource,
        Optional("ramdisk"): {**resource_ext, Optional("header"): "u-boot"},
        Exclusive("nfsrootfs", "nfs"): {**resource_ext, Optional("prefix"): str},
        Exclusive("persistent_nfs", "nfs"): {
            Required("address"): str,
            Optional("install_overlay"): bool,
        },
    }
    return {**deploy.schema(live), **base}
