# Copyright 2026 Qualcomm Inc.
#
# Author: Milosz Wasilewski <milosz.wasilewski@oss.qualcomm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot, docker


def schema():
    base = {
        Required("method"): Msg("qdl", "'method' should be 'qdl'"),
        Required("firehose_program"): str,
        Required("rawprogram"): str,
        Optional("patch"): str,
        Optional("path"): str,
        Optional("storage"): str,
        Optional("debug"): bool,
        Optional("docker"): docker(),
    }
    return {**boot.schema(), **base}
