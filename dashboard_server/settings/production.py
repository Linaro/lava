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

# Django settings for django_hello project.
from dashboard_server.settings.common import *

DEBUG = False 
TEMPLATE_DEBUG = DEBUG

# Application URL prefix defines where the application is located at
# runtime with regards to URLs. Data URL prefix does the same but for
# static and media files.
#
# Development settings use empty value to make localhost:8000 point
# to the application. Production values can use anything but this
# needs to be in sync with web server configuration. Debian
# recommends package name as the prefix so that multiple web
# applications can co-exists on one server without
# namespace clashes.
#
# Both values _MUST_ end with a slash when not empty.

# Code is served directly, WSGI mapping make it appear in "django-hello" but
# this is done externally to django URL resolver.
APP_URL_PREFIX = r""
# Data is served by external web server in "django-hello/"
DATA_URL_PREFIX = r"launch-control/"

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = "/" + DATA_URL_PREFIX + "media/"

# URL that handles the media served from STATIC_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://static.lawrence.com", "http://example.com/static/"
STATIC_URL = "/" + DATA_URL_PREFIX + "static/"

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = "/" + DATA_URL_PREFIX + "static/admin/"

# The true outer url is /launch-control/
LOGIN_REDIRECT_URL = "/" + DATA_URL_PREFIX

if DEBUG:
    raise Exception("You should not run this application with debugging in a production environment")
