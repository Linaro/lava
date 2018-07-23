# -*- coding: utf-8 -*-
# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
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

# Created with Django 1.8.18

import contextlib
import imp

# Import application settings
from lava_scheduler_app.settings import *


# List of people who get code error notifications
# https://docs.djangoproject.com/en/1.8/ref/settings/#admins
ADMINS = [['lava-server Administrator', 'root@localhost']]
# List of people who get broken link notifications
# https://docs.djangoproject.com/en/1.8/ref/settings/#managers
MANAGERS = ADMINS

# Allow only the connection through the reverse proxy
ALLOWED_HOSTS = ['[::1]', '127.0.0.1', 'localhost']
INTERNAL_IPS = []

# Application definition
INSTALLED_APPS = [
    # Add LAVA applications
    'lava_server',
    'dashboard_app',
    'lava_results_app',
    'lava_scheduler_app',
    # Add LAVA dependencies
    'django_tables2',
    'linaro_django_xmlrpc',
    # Add contrib
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',  # FIXME: should not be needed anymore
]

MIDDLEWARE_CLASSES = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
]

ROOT_URLCONF = 'lava_server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'django.template.context_processors.static',
                # LAVA context processors
                'lava_server.context_processors.lava',
                'lava_server.context_processors.ldap_available',
            ],
        },
    },
]

WSGI_APPLICATION = 'lava_server.wsgi.application'

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# URL that handles the media served from STATIC_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://static.lawrence.com", "http://example.com/static/"
# https://docs.djangoproject.com/en/1.8/howto/static-files/
STATIC_URL = "/static/"

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications.
STATIC_ROOT = "/usr/share/lava-server/static"

# Absolute filesystem path to the directory that will hold user-uploaded files.
MEDIA_ROOT = "/var/lib/lava-server/default/media/"

# Absolute filesystem path to the directory that will hold archived files.
ARCHIVE_ROOT = "/var/lib/lava-server/default/archive/"

# LOG_SIZE_LIMIT in megabytes
LOG_SIZE_LIMIT = 25

# Default URL after login
LOGIN_REDIRECT_URL = "/"

# Automatically install some applications
available_modules = list()
for module_name in ["devserver", "django_extensions", "django_openid_auth", "hijack"]:
    with contextlib.suppress(ImportError):
        imp.find_module(module_name)
        INSTALLED_APPS.append(module_name)

# General URL prefix
MOUNT_POINT = ""

# Do not disallow any user-agent yet
DISALLOWED_USER_AGENTS = []

# Set a site ID
# FIXME: should not be needed
SITE_ID = 1

# Django System check framework settings for security.* checks.
# Silence some checks that should be explicitly configured by administrators
# on need basis.
SILENCED_SYSTEM_CHECKS = [
    'security.W004',  # silence SECURE_HSTS_SECONDS
    'security.W008',  # silence SECURE_SSL_REDIRECT
]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
HTTPS_XML_RPC = True

# Branding support
BRANDING_ALT = "Linaro logo"
BRANDING_ICON = "lava_server/images/logo.png"
BRANDING_URL = "http://www.linaro.org"
BRANDING_HEIGHT = 22
BRANDING_WIDTH = 22
BRANDING_BUG_URL = "/static/docs/v2/development-intro.html#report-a-bug"
BRANDING_SOURCE_URL = "https://git.linaro.org/lava"
BRANDING_MESSAGE = ""

# Custom documentation
CUSTOM_DOCS = {}

# Logging
DJANGO_LOGFILE = "/var/log/lava-server/django.log"

# Django debug toolbar
USE_DEBUG_TOOLBAR = False

# Template caching
USE_TEMPLATE_CACHE = False

# LDAP support
AUTH_LDAP_SERVER_URI = None
AUTH_LDAP_BIND_DN = None
AUTH_LDAP_BIND_PASSWORD = None
AUTH_LDAP_USER_DN_TEMPLATE = None
AUTH_LDAP_USER_SEARCH = None
AUTH_LDAP_GROUP_SEARCH = None
AUTH_LDAP_GROUP_TYPE = None

# Debian SSO is of be default
AUTH_DEBIAN_SSO = None

# Remove Delete buttons in django admin interface
ALLOW_ADMIN_DELETE = True
