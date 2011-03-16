# Copyright (C) 2010, 2011 Linaro Limited
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

import os

from dashboard_server.settings.common import *


ROOT_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)),
        "..")) 

DEBUG = True
DEBUG_PROPAGATE_EXCEPTIONS = True
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
# The prefix _MUST_ end with a slash when not empty.

# Code is served directly, WSGI mapping make it appear in "django-hello" but
# this is done externally to django URL resolver.
APP_URL_PREFIX = r""
# Data is served by external web server in "django-hello/"
DATA_URL_PREFIX = r""


# XXX: this is ugly, it would be good to have rails-like configuration file in the future
devel_db = os.getenv("DEVEL_DB", "sqlite")
if devel_db == "pgsql":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'devel',
            'USER': 'devel',
            'PASSWORD': 'devel',
            'HOST': 'localhost',
            'PORT': ''
        }
    }
elif devel_db == "sqlite":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(ROOT_DIR, 'development.db'),
            'USER': '',
            'PASSWORD': '',
            'HOST': '',
            'PORT': '',
        }
    }
else:
    raise ValueError("Invalid value of DEVEL_DB environment variable")


# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(ROOT_DIR, "media", devel_db)

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications. 
# Example: "/home/media/static.lawrence.com/"
STATIC_ROOT = os.path.join(ROOT_DIR, "static")

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

if not DEBUG:
    raise Exception("You need to configure MEDIA_URL, STATIC_URL and ADMIN_MEDIA_PREFIX to point to a production web server")

# Make this unique, and don't share it with anybody.
SECRET_KEY = '00000000000000000000000000000000000000000000000000'


TEMPLATE_DIRS = (
    os.path.join(ROOT_DIR, "templates"),
)

STATICFILES_DIRS = [
    ('', os.path.join(ROOT_DIR, 'htdocs'))
]


# Login redirects back to home
LOGIN_REDIRECT_URL = '/'

# Any emails that would normally be sent are redirected to stdout. 
# This setting is only used for django 1.2 and newer.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
