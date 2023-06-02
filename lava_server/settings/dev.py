# Copyright (C) 2017-present Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#         Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import os
from pathlib import Path

import yaml

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
static_root_path = PROJECT_STATE_DIR / "static"
static_root_path.mkdir(exist_ok=True)
STATIC_ROOT = str(static_root_path)

# Use device configuration files from source tree
DEVICES_PATH = str(PROJECT_SRC_DIR / "etc/dispatcher-config/devices")
DEVICE_TYPES_PATHS = [
    str(PROJECT_SRC_DIR / "etc/dispatcher-config/device-types")
] + DEVICE_TYPES_PATHS
HEALTH_CHECKS_PATH = str(PROJECT_SRC_DIR / "etc/dispatcher-config/health-checks")

# Make this unique, and don't share it with anybody.
SECRET_KEY = "00000000000000000000000000000000000000000000000000"

# Relax security settings to simplify local development
ALLOWED_HOSTS = ["*"]
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
ALLOW_VERSION_MISMATCH = False

# Any emails that would normally be sent are redirected to stdout.
# This setting is only used for django 1.2 and newer.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Do not use caching as it interfere with test
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

with contextlib.suppress(ImportError):
    from lava_server.settings.local_settings import *  # noqa

FILES = [
    Path(PROJECT_SRC_DIR) / "etc/settings.conf",
    *sorted((Path(PROJECT_SRC_DIR) / "etc/settings.d").glob("*.yaml")),
]

for filename in FILES:
    try:
        with contextlib.suppress(FileNotFoundError):
            for k, v in yaml.safe_load(filename.read_text(encoding="utf-8")).items():
                globals()[k] = v
    except yaml.YAMLError as exc:
        print(f"[INIT] Unable to load {filename.name}: invalid yaml")
        print(exc)
        raise Exception(f"Unable to load {filename.name}") from exc


# Update settings with custom values
for k, v in update(globals()).items():
    globals()[k] = v
