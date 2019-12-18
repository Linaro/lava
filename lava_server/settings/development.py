# -*- coding: utf-8 -*-
# Copyright (C) 2010-2018 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
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
import os

from lava_server.settings.common import *  # pylint: disable=unused-import


# Activate debugging
DEBUG = True
TEMPLATES[0]["OPTIONS"]["debug"] = True

USE_TZ = True

# Top-level directory of the project.
PROJECT_SRC_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)

# Top-level directory of the static files
#
# In short: this is where your non-source content ends up at, this place should
# keep the database file(s), user uploaded media files as well as the cache of
# static files, if built.
PROJECT_STATE_DIR = os.environ.get(
    "LAVA_BASE_DIR", os.path.join(PROJECT_SRC_DIR, "tmp")
)

# Create state directory if needed
os.makedirs(PROJECT_STATE_DIR, exist_ok=True)

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
MEDIA_ROOT = os.path.join(PROJECT_STATE_DIR, "media")

# Absolute filesystem path to the directory that will hold archived files.
ARCHIVE_ROOT = os.path.join(PROJECT_STATE_DIR, "archive")

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications.
# Example: "/home/media/static.lawrence.com/"
STATIC_ROOT = os.path.join(PROJECT_STATE_DIR, "static")

GLOBAL_SETTINGS_PATH = os.path.join(PROJECT_SRC_DIR, "etc/lava-server")
DISPATCHER_CONFIG_PATH = os.path.join(PROJECT_SRC_DIR, "etc/lava-server/dispatcher.d")
# Use device configuration files from source tree
DEVICES_PATH = os.path.join(PROJECT_SRC_DIR, "etc/dispatcher-config/devices")
DEVICE_TYPES_PATH = os.path.join(PROJECT_SRC_DIR, "etc/dispatcher-config/device-types")
HEALTH_CHECKS_PATH = os.path.join(
    PROJECT_SRC_DIR, "etc/dispatcher-config/health-checks"
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = "00000000000000000000000000000000000000000000000000"

# Relax security settings to simplify local development
ALLOWED_HOSTS = ["*"]
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Try using devserver if available, devserver is a very useful extension that
# makes debugging applications easier. It shows a lot of interesting output,
# like SQL queries and timings for each request. It also supports
# multi-threaded or multi-process server so some degree of parallelism can be
# achieved.
with contextlib.suppress(ImportError):
    import devserver  # pylint: disable=unused-import

    INSTALLED_APPS += ["devserver"]

USE_DEBUG_TOOLBAR = False

# Any emails that would normally be sent are redirected to stdout.
# This setting is only used for django 1.2 and newer.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# default branding details
BRANDING_ALT = "LAVA Software logo"
BRANDING_ICON = "lava_server/images/logo.png"
BRANDING_URL = "http://www.lavasoftware.org"
BRANDING_HEIGHT = 22
BRANDING_WIDTH = 22
BRANDING_BUG_URL = "https://git.lavasoftware.org/lava/lava/issues"
BRANDING_SOURCE_URL = "https://git.lavasoftware.org/lava/lava"
BRANDING_MESSAGE = ""

# Use default instance name
INSTANCE_NAME = "default"

# Logging

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
    "formatters": {
        "lava": {"format": "%(levelname)s %(asctime)s %(module)s %(message)s"}
    },
    "handlers": {
        "logfile": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": "django.log",
            "formatter": "lava",
        }
    },
    "loggers": {
        "django": {
            "handlers": ["logfile"],
            # DEBUG outputs all SQL statements
            "level": "ERROR",
            "propagate": True,
        },
        "django_auth_ldap": {
            "handlers": ["logfile"],
            "level": "INFO",
            "propagate": True,
        },
        "lava_scheduler_app": {
            "handlers": ["logfile"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Do not use caching as it interfere with test
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "lava_server.backends.GroupPermissionBackend",
]

try:
    from lava_server.settings.local_settings import *  # noqa
except ImportError:
    pass
