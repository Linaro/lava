# Copyright (C) 2015-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

from lava_common.jinja import create_device_templates_env
from lava_server.files import File

if TYPE_CHECKING:
    from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

devices_jinja_env: ContextVar[JinjaSandboxEnv] = ContextVar("devices_jinja_env")


def devices():
    try:
        return devices_jinja_env.get()
    except LookupError:
        devices_env = create_device_templates_env(
            loader=File("device").loader(),
            cache_size=-1,
        )
        devices_jinja_env.set(devices_env)
        return devices_env


device_types_jinja_env: ContextVar[JinjaSandboxEnv] = ContextVar(
    "device_types_jinja_env"
)


def device_types():
    try:
        return device_types_jinja_env.get()
    except LookupError:
        device_types_env = create_device_templates_env(
            loader=File("device-type").loader(),
            cache_size=-1,
        )
        device_types_jinja_env.set(device_types_env)
        return device_types_env
