#
# Copyright (C) 2019 Linaro Limited
#
# Author: Andrei Gansari <andrei.gansari@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Required

from lava_common.schemas import boot


def schema():
    base = {Required("method"): Msg("jlink", "'method' should be 'jlink'")}
    return {**boot.schema(), **base}
