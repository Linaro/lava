#
# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("lxc", "'method' should be 'lxc'"),
        Required("prompts"): boot.prompts(),
    }
    return {**boot.schema(), **base}
