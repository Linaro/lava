# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
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

import warnings
import yaml


# Handle compatibility with old yaml versions
loaders = [
    ("CFullLoader", False),
    ("FullLoader", False),
    ("CLoader", True),
    ("Loader", True),
]
Loader = None
for (name, warn) in loaders:
    if hasattr(yaml, name):
        Loader = getattr(yaml, name)
        if warn:
            warnings.warn("Using unsafe yaml.%s" % name, DeprecationWarning)
        break
if Loader is None:
    raise NotImplementedError("yaml Loader is undefined")


# Handle compatibility with system without C yaml
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader


# handle compatibility for yaml.load
def yaml_load(data):
    return yaml.load(data, Loader=Loader)  # nosec


# handle compatibility for yaml.safe_load
def yaml_safe_load(data):
    return yaml.load(data, Loader=SafeLoader)
