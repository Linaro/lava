# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from contextvars import ContextVar
from io import StringIO
from typing import TYPE_CHECKING

from yaml import dump, load

if TYPE_CHECKING:
    from typing import Union  # For Python 3.9 compatibility

# Handle compatibility with system without C yaml
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

try:
    from yaml import CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeDumper


def yaml_safe_load(data):
    return load(data, Loader=SafeLoader)


def yaml_safe_dump(data, *args, **kwargs):
    # Preserve key order by default
    kwargs["sort_keys"] = kwargs.get("sort_keys", False)
    return dump(data, *args, Dumper=SafeDumper, **kwargs)


yaml_quote_dumper: ContextVar[tuple[StringIO, SafeDumper]] = ContextVar(
    "yaml_quote_dumper"
)


def _get_largest_width_possible() -> int:
    # A largest value that both C and Python implementation accept
    from ctypes import c_uint

    return c_uint(-1).value // 2


def yaml_quote(obj: Union[str, int, float, dict, list]) -> str:
    try:
        stream, yaml_dumper = yaml_quote_dumper.get()
    except LookupError:
        stream = StringIO()
        yaml_dumper = SafeDumper(
            stream,
            default_flow_style=True,  # Output in a single line
            width=_get_largest_width_possible(),  # Disable automatic line breaks
            default_style='"',  # Use "double quoted" scalar type
            explicit_start=True,  # Always output "--- " YAML document start
            explicit_end=False,  # Do not output "\n..." at the end
        )
        yaml_dumper.open()  # Start accepting any objects
        yaml_quote_dumper.set((stream, yaml_dumper))
    else:
        # Clean-up existing stream
        stream.seek(0)
        stream.truncate(0)

    yaml_dumper.represent(obj)
    return stream.getvalue()[4:-1]  # Skip "--- " and newline
