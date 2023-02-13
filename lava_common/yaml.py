# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from yaml import dump, load

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
    # sort_keys=False will break the CI because
    # some dispatcher tests check the order of dict keys
    return dump(data, *args, Dumper=SafeDumper, **kwargs)
