#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import All, Length, Match, Optional, Required

from lava_common.schemas import action

# an empty name validates but is silently ignored by the dispatcher;
# LAVA_ is reserved for the job environment and PATH would break it
CREATE_SECRET_NAME = r"^(?!LAVA_|PATH\Z)[A-Za-z_][A-Za-z0-9_]*\Z"


def schema():
    return {
        **action(),
        Required("name"): str,
        Optional("create_secret"): All(str, Length(min=1), Match(CREATE_SECRET_NAME)),
    }
