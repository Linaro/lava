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
Development settings module.

Suitable for local deployments (local = not on the open web) as well as
hacking. Uses sqlite database and slow/inefficient web server built
right into Django.
"""

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database setup
DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = os.path.join(BASE_DIR, 'database.db')

# Static files are served directly from the source tree
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
# Static files are accessible as /site_media/ URL
MEDIA_URL = '/site_media/'

# Development mode, turn on debugging
# Note: debugging sucks memory as it retains SQL history _FOREVER_
# If you _really_ want to use this for local deployment please turn
# this off.
DEBUG = True
TEMPLATE_DEBUG = DEBUG

# List of people that get emailed when the site breaks and DEBUG is off.
# Requires working email configuration
ADMINS = ()

# Secret key for doing secret stuff with cookies and session IDs
SCRET_KEY = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

# Information for urls.py that we should serve assets without the help
# of an external web server. This is only used when we cannot count on
# static media files being served by some real web server. WARNING: this
# is not secure and should _never_ be used in production environments.
# See:
# http://docs.djangoproject.com/en/1.2/howto/static-files/#the-big-fat-disclaimer)
SERVE_ASSETS_FROM_DJANGO = True
