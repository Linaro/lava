#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
        Optional("use_cache"): bool,
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
