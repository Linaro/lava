# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Dashboard server settings module.
"""

# CONFIGURATION
# =============
#
# To configure the server create local_settings.py and add any django
# configuration options you care about. Please look at
# local_settings.py.example to get started.
#
# DO NOT CHANGE SETTINGS BELOW
# ============================

from default_settings import *
try:
    from local_settings import *
except ImportError:
    from development_settings import *


TEMPLATE_CONTEXT_PROCESSORS = (
    # Django provided context processors
    'django.core.context_processors.auth',
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    # Launch Control provided context processors
    'dashboard_server.context_processors.login_url',
    )
