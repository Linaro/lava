# -*- coding: utf-8 -*-
# Copyright (C) 2017-present Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#         Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
from pathlib import Path
import yaml

from lava_server.settings.common import *
from lava_server.settings.config_file import ConfigFile

############################
# Load configuration files #
############################

# instance.conf
with contextlib.suppress(FileNotFoundError):
    config = ConfigFile.load("/etc/lava-server/instance.conf")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": getattr(config, "LAVA_DB_NAME", ""),
            "USER": getattr(config, "LAVA_DB_USER", ""),
            "PASSWORD": getattr(config, "LAVA_DB_PASSWORD", ""),
            "HOST": getattr(config, "LAVA_DB_SERVER", "127.0.0.1"),
            "PORT": getattr(config, "LAVA_DB_PORT", "5432"),
        }
    }
    INSTANCE_NAME = config.LAVA_INSTANCE

# secret_key.conf
with contextlib.suppress(FileNotFoundError):
    SECRET_KEY = ConfigFile.load("/etc/lava-server/secret_key.conf").SECRET_KEY

# Load settings
FILES = [
    Path("/etc/lava-server/settings.conf"),
    Path("/etc/lava-server/settings.yaml"),
    *sorted(Path("/etc/lava-server/settings.d").glob("*.yaml")),
]

for filename in FILES:
    try:
        with contextlib.suppress(FileNotFoundError):
            for (k, v) in yaml.safe_load(filename.read_text(encoding="utf-8")).items():
                globals()[k] = v
    except yaml.YAMLError as exc:
        print(f"[INIT] Unable to load {filename.name}: invalid yaml")
        print(exc)
        raise Exception(f"Unable to load {filename.name}") from exc

# Update settings with custom values
for (k, v) in update(globals()).items():
    globals()[k] = v
