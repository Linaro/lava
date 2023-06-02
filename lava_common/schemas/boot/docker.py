#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("docker", "'method' should be 'docker'"),
        Required("command"): str,
        Optional("prompts"): boot.prompts(),
        Optional("downloads-namespace"): str,
    }
    return {**boot.schema(), **base}
