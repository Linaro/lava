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

# pylint:disable=wrong-import-position

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="environ")

import contextlib
import environ
import os
from pathlib import Path
import yaml

from lava_server.settings.common import *
from lava_server.settings.config_file import ConfigFile

############################
# Load configuration files #
############################

# We only rely on django-environ for the neat database configuration helper,
# which handles several special and corner cases, like sqlite memory
# configurations, for one.
#
# The reason for this is its support for proxy variables makes anything else
# highly fragile. For instance, if the SECRET_KEY happens to start with a $
# character, it will try to use the rest of the key as a variable name, and
# expose it on an error message.
env = environ.Env()
environ.Env.read_env()

if os.environ.get("DATABASE_URL"):
    DATABASES = {"default": env.db()}
    INSTANCE_NAME = os.environ["INSTANCE_NAME"]
else:
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

if os.environ.get("SECRET_KEY"):
    SECRET_KEY = os.environ["SECRET_KEY"]
else:
    with contextlib.suppress(FileNotFoundError):
        SECRET_KEY = ConfigFile.load("/etc/lava-server/secret_key.conf").SECRET_KEY

if os.environ.get("ALLOWED_HOSTS"):
    ALLOWED_HOSTS += os.environ["ALLOWED_HOSTS"].split(",")

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
