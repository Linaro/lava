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

from voluptuous import Any, Optional, Required

from lava_common.schemas import action


def url(extra=None):
    if extra is None:
        extra = {}

    base_url = {
        Required("url"): str,
        Optional("headers"): dict,
        Optional("compression"): Any("bz2", "gz", "xz", "zip", "zstd", None),
        Optional("archive"): "tar",
        Optional("md5sum"): str,
        Optional("sha256sum"): str,
        Optional("sha512sum"): str,
    }
    return Any(
        {**base_url, **extra},
        {
            **base_url,
            **extra,
            Required("format"): Any("cpio.newc", "ext4", "tar"),
            Optional("partition"): int,
            Optional("sparse"): bool,
            Required("overlays"): {
                Optional("lava"): bool,
                str: {
                    **base_url,
                    Required("format"): Any("file", "tar"),
                    Required("path"): str,
                },
            },
        },
    )


def schema():
    return {**action(), Optional("os"): str, Optional("authorize"): "ssh"}
