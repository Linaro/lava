#
# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Required

from lava_common.schemas import boot

from .grub import base_schema


def schema():
    base = {
        Required("method"): Msg("grub-efi", "'method' should be 'grub-efi'"),
        **base_schema(),
    }
    return {**boot.schema(), **base}
