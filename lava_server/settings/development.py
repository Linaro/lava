# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

import os

from lava_server.settings.common import *

# Top-level directory of the project.
#
# This directory MUST contain two sub-directories:
#  * templates/ - project-wide template files
#  * htdocs/    - project-wide static files
#                 (_not_ the root of the static file cache)
PROJECT_SRC_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)),
        ".."))

# Top-level directory for nonvolatile files
PRECIOUS_DIR = os.path.join(PROJECT_SRC_DIR, "precious")

# Create precious directory if needed
if not os.path.exists(PRECIOUS_DIR):
    os.makedirs(PRECIOUS_DIR)

# Top-level directory of the precious project state.
#
# In short: this is where your non-source content ends up at, this place should
# keep the database file(s), user uploaded media files as well as the cache of
# static files, if built.
PROJECT_STATE_DIR = os.path.join(PRECIOUS_DIR, "var/lib/lava-server/")

# Create state directory if needed
if not os.path.exists(PROJECT_STATE_DIR):
    os.makedirs(PROJECT_STATE_DIR)

DEBUG = True
DEBUG_PROPAGATE_EXCEPTIONS = True
TEMPLATE_DEBUG = DEBUG

# It would be good to have rails-like configuration file in the future
devel_db = os.getenv("DEVEL_DB", "pgsql")
if devel_db == "pgsql":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'devel',
            'USER': 'devel',
            'PASSWORD': 'devel',
            'HOST': 'localhost',
            'PORT': ''}}
elif devel_db == "nosql":
    raise ValueError("not yet ;-)")
else:
    raise ValueError("Invalid value of DEVEL_DB environment variable")


# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(PROJECT_STATE_DIR, "media", devel_db)

# Absolute filesystem path to the directory that will hold archived files.
ARCHIVE_ROOT = os.path.join(PROJECT_STATE_DIR, "archive", devel_db)

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications.
# Example: "/home/media/static.lawrence.com/"
STATIC_ROOT = os.path.join(PROJECT_STATE_DIR, "static")


# Make this unique, and don't share it with anybody.
SECRET_KEY = '00000000000000000000000000000000000000000000000000'

# Use templates from the checkout directory
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(PROJECT_SRC_DIR, '..', 'lava_server', 'templates'),
            os.path.join(PROJECT_SRC_DIR, '..', 'lava_scheduler_app', 'templates', 'lava_scheduler_app'),
            os.path.join(PROJECT_SRC_DIR, '..', 'dashboard_app', 'templates', 'dashboard_app'),
            os.path.join(PROJECT_SRC_DIR, '..', 'lava_results_app', 'templates', 'lava_results_app'),
            os.path.join(PROJECT_SRC_DIR, '..', 'google_analytics', 'templates', 'google_analytics'),
        ],
        'OPTIONS': {
            'context_processors': [
                # Insert your TEMPLATE_CONTEXT_PROCESSORS here
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "lava_server.context_processors.lava",
                "lava_server.context_processors.ldap_available",
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ]
        },
    },
]


# Serve static files used by lava-server from the checkout directory
STATICFILES_DIRS = [
    ('lava-server', os.path.join(PROJECT_SRC_DIR, 'lava-server'))]


# Try using devserver if available, devserver is a very useful extension that
# makes debugging applications easier. It shows a lot of interesting output,
# like SQL queries and timings for each request. It also supports
# multi-threaded or multi-process server so some degree of parallelism can be
# achieved.
try:
    import devserver
    INSTALLED_APPS += ['devserver']
except ImportError:
    pass


# Any emails that would normally be sent are redirected to stdout.
# This setting is only used for django 1.2 and newer.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# default branding details
BRANDING_ALT = "Linaro logo"
BRANDING_ICON = 'lava-server/images/logo.png'
BRANDING_URL = 'http://www.linaro.org'
BRANDING_HEIGHT = "BRANDING_HEIGHT", 22
BRANDING_WIDTH = "BRANDING_WIDTH", 22
BRANDING_BUG_URL = "https://bugs.linaro.org/enter_bug.cgi?product=LAVA%20Framework"
BRANDING_SOURCE_URL = "https://git.linaro.org/lava"

# Logging

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'lava': {
            'format': '%(levelname)s %(asctime)s %(module)s %(message)s'
        }
    },
    'handlers': {
        'logfile': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': 'django.log',
            'formatter': 'lava'
        }
    },
    'loggers': {
        'django': {
            'handlers': ['logfile'],
            # DEBUG outputs all SQL statements
            'level': 'ERROR',
            'propagate': True,
        },
        'django_auth_ldap': {
            'handlers': ['logfile'],
            'level': 'INFO',
            'propagate': True,
        },
        'dashboard_app': {
            'handlers': ['logfile'],
            'level': 'INFO',
            'propagate': True,
        },
        'lava_scheduler_app': {
            'handlers': ['logfile'],
            'level': 'INFO',
            'propagate': True,
        }
    }
}
