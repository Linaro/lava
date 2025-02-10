# Copyright (C) 2017-present Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#         Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# pylint:disable=wrong-import-position

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="environ")

import base64
import contextlib
import json
import os
from pathlib import Path

import environ
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
    INSTANCE_NAME = os.environ.get("INSTANCE_NAME", INSTANCE_NAME)
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
        if conn_max_age_str := getattr(config, "CONN_MAX_AGE", None):
            DATABASES["default"]["CONN_MAX_AGE"] = int(conn_max_age_str)

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
            for k, v in yaml.safe_load(filename.read_text(encoding="utf-8")).items():
                globals()[k] = v
    except yaml.YAMLError as exc:
        print(f"[INIT] Unable to load {filename.name}: invalid yaml")
        print(exc)
        raise Exception(f"Unable to load {filename.name}") from exc

for k in os.environ:
    if k.startswith("LAVA_SETTINGS_"):
        value = env(k)
        globals()[k[len("LAVA_SETTINGS_") :]] = value
    elif k.startswith("LAVA_YAML_SETTINGS_"):
        try:
            value = yaml.safe_load(env(k))
        except yaml.YAMLError as exc:
            print(f"[INIT] Unable to parse {k}: invalid yaml")
            print(exc)
            raise Exception(f"Unable to parse {k}") from exc
        globals()[k[len("LAVA_YAML_SETTINGS_") :]] = value

if "LAVA_JSON_SETTINGS" in os.environ:
    try:
        for k, v in json.loads(
            base64.b64decode(os.environ["LAVA_JSON_SETTINGS"])
        ).items():
            globals()[k] = v
    except Exception as exc:
        print(f"[INIT] Unable to load LAVA_JSON_SETTINGS: invalid string")
        print(exc)
        raise Exception(f"Unable to load LAVA_JSON_SETTINGS") from exc

if "DATABASES" in locals() and DATABASES.get("default"):
    if db_conn_max_age_str := globals().get("DB_CONN_MAX_AGE"):
        with contextlib.suppress(ValueError):
            DATABASES["default"]["CONN_MAX_AGE"] = int(db_conn_max_age_str)
    if db_conn_health_check_str := globals().get("DB_CONN_HEALTH_CHECKS"):
        if db_conn_health_check_str in ["True", "true", "1", "yes", "on"]:
            DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
        elif db_conn_health_check_str in ["False", "false", "0", "no", "off"]:
            DATABASES["default"]["CONN_HEALTH_CHECKS"] = False

# Update settings with custom values
for k, v in update(globals()).items():
    globals()[k] = v
