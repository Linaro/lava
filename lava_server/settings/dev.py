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
import os

from lava_server.settings.common import *


DEBUG = True

######################
# File system layout #
######################

# Top-level directory of the project.
PROJECT_SRC_DIR = (Path(__file__).parent.resolve() / ".." / "..").resolve()

# Top-level directory of the static files
PROJECT_STATE_DIR = Path(os.getenv("LAVA_STATE_DIR") or PROJECT_SRC_DIR / "tmp")

# Create state directory if needed
PROJECT_STATE_DIR.mkdir(parents=True, exist_ok=True)

# LAVA logs
DJANGO_LOGFILE = str(PROJECT_STATE_DIR / "django.log")

# Test database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "devel",
        "USER": "devel",
        "PASSWORD": "devel",
        "HOST": "localhost",
        "PORT": "",
    }
}

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = str(PROJECT_STATE_DIR / "media")

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications.
# Example: "/home/media/static.lawrence.com/"
STATIC_ROOT = str(PROJECT_STATE_DIR / "static")

DISPATCHER_CONFIG_PATH = str(PROJECT_SRC_DIR / "etc/lava-server/dispatcher.d")
# Use device configuration files from source tree
DEVICES_PATH = str(PROJECT_SRC_DIR / "etc/dispatcher-config/devices")
DEVICE_TYPES_PATHS = [str(PROJECT_SRC_DIR / "etc/dispatcher-config/device-types")]
HEALTH_CHECKS_PATH = str(PROJECT_SRC_DIR / "etc/dispatcher-config/health-checks")

# Make this unique, and don't share it with anybody.
SECRET_KEY = "00000000000000000000000000000000000000000000000000"

# Relax security settings to simplify local development
ALLOWED_HOSTS = ["*"]
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Any emails that would normally be sent are redirected to stdout.
# This setting is only used for django 1.2 and newer.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Do not use caching as it interfere with test
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

with contextlib.suppress(ImportError):
    from lava_server.settings.local_settings import *  # noqa

# Update settings with custom values
for (k, v) in update(globals()).items():
    globals()[k] = v
