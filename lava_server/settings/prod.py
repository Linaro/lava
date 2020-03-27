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

import simplejson

from lava_server.settings.common import *
from lava_server.settings.config_file import ConfigFile
from lava_server.settings.secret_key import get_secret_key

############################
# Load configuration files #
############################

# instance.conf
config = ConfigFile.load("/etc/lava-server/instance.conf")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": getattr(config, "LAVA_DB_NAME", ""),
        "USER": getattr(config, "LAVA_DB_USER", ""),
        "PASSWORD": getattr(config, "LAVA_DB_PASSWORD", ""),
        "HOST": getattr(config, "LAVA_DB_SERVER", "127.0.0.1"),
        "PORT": getattr(config, "LAVA_DB_PORT", ""),
    }
}
INSTANCE_NAME = config.LAVA_INSTANCE

# secret_key.conf
SECRET_KEY = get_secret_key("/etc/lava-server/secret_key.conf")

# settings.conf
with open("/etc/lava-server/settings.conf", "r") as f_conf:
    try:
        data = simplejson.load(f_conf)
    except simplejson.JSONDecodeError as exc:
        print("[INIT] Unable to load settings.conf")
        print(exc)
        raise Exception("Unable to load settings.conf") from exc
    for (k, v) in data.items():
        locals()[k] = v


# Update settings with custom values
for (k, v) in update(globals()).items():
    globals()[k] = v
