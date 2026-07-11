# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from shlex import quote as shlex_quote
from typing import TYPE_CHECKING

from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

from . import constants
from .yaml import yaml_quote

if TYPE_CHECKING:
    from typing import Optional

    from jinja2 import BaseLoader


def qemu_guest_fs_interface(arch: str, guestfs_interface: str | None) -> str:
    """Return the default guest filesystem interface for QEMU/KVM.

    Only x86 PC machines have an IDE controller; all other machine types
    require virtio. The result can be overridden by passing a non-empty
    ``guestfs_interface`` value.
    """
    if guestfs_interface:
        return guestfs_interface
    return "ide" if arch in constants.X86_ARCHS else "virtio"


def create_device_templates_env(
    loader: BaseLoader | None = None, cache_size: int = 400
) -> JinjaSandboxEnv:
    new_env = JinjaSandboxEnv(
        loader=loader,
        autoescape=False,
        trim_blocks=True,
        cache_size=cache_size,
    )
    new_env.filters["shlex_quote"] = shlex_quote
    new_env.filters["yaml_quote"] = yaml_quote
    new_env.filters["qemu_guest_fs_interface"] = qemu_guest_fs_interface
    return new_env
