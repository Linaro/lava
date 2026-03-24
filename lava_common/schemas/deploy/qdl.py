# Copyright 2026 Qualcomm Inc.
#
# Author: Milosz Wasilewski <milosz.wasilewski@oss.qualcomm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Length, Optional, Required

from lava_common.schemas import deploy


def schema():
    base = {
        Required("to"): "qdl",
        Required("qcomflash"): Any(
            {
                Any(str): deploy.url(),
                Optional("apply-overlay"): bool,
            },
            Length(min=1),
        ),
        Optional("uniquify"): bool,
        Optional("rootfs_image"): str,
        Optional("overlay_path"): str,
    }
    return {**deploy.schema(), **base}
