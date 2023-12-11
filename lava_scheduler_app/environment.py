# Copyright (C) 2015-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.jinja import create_device_templates_env
from lava_server.files import File

if TYPE_CHECKING:
    from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

DEVICES_JINJA_ENV: JinjaSandboxEnv = create_device_templates_env(
    loader=File("device").loader(),
    cache_size=-1,
)


DEVICE_TYPES_JINJA_ENV: JinjaSandboxEnv = create_device_templates_env(
    loader=File("device-type").loader(),
    cache_size=-1,
)
