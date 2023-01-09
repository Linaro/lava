# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.
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
