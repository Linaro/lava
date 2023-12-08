# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from shlex import quote as shlex_quote
from typing import TYPE_CHECKING

from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

from .yaml import yaml_quote

if TYPE_CHECKING:
    from typing import Optional

    from jinja2 import BaseLoader


def create_device_templates_env(
    loader: Optional[BaseLoader] = None, cache_size: int = 400
) -> JinjaSandboxEnv:
    new_env = JinjaSandboxEnv(
        loader=loader,
        autoescape=False,
        trim_blocks=True,
        cache_size=cache_size,
    )
    new_env.filters["shlex_quote"] = shlex_quote
    new_env.filters["yaml_quote"] = yaml_quote
    return new_env
