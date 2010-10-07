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

# Example configuration
#
# Use this as a starting point for your own configuration. Make sure to
# rename this file to local_settings.py and edit settings.py to have
# CONFIGURED = True (read the comments there to understand more)
import os
import django

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure to reflect your database engine
DATABASE_ENGINE = ''
DATABASE_NAME = ''
DATABASE_USER = ''
DATABASE_PASSWORD = ''
DATABASE_HOST = ''
DATABASE_PORT = ''

# Secret key, don't share it 
SECRET_KEY = ''

# Lesser configuration variables:

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Warsaw'

# Administrator contact, used for sending
# emergency email when something breaks
ADMINS = (
    #( 'Your name', 'email@example.org'),
    )

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Turn off application debugging
DEBUG = False

# Turn on to enable template debugging.
TEMPLATE_DEBUG = False

MANAGERS = ADMINS

ROOT_URLCONF = 'dashboard_server.urls'

SITE_ID = 1

LOGIN_URL = '/dashboard/openid/login/'
LOGIN_REDIRECT_URL = '/dashboard'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'templates'),
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
)

# This is an attempt to maintain CSRF support for both django 1.1 and
# 1.2. In 1.1 we explicitly use the contrib package in 1.2 we use the
# legacy package. This has a small performance hit as the legacy
# middleware in 1.2 rewrites the whole response. Once we drop support
# for 1.1 we can remove this section.
if django.VERSION[:2] == (1, 1):
    MIDLEWARE_CLASSES = MIDDLEWARE_CLASSES + (
        'django.contrib.csrf.middleware.CsrfMiddleware',
    )
elif django.VERSION[:2] == (1, 2):
    MIDDLEWARE_CLASSES = MIDDLEWARE_CLASSES + (
        'django.middleware.csrf.CsrfMiddleware',
    )

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.markup',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.databrowse',
    'django.contrib.humanize',
    'django_openid_auth',
    'dashboard_app',
)

AUTHENTICATION_BACKENDS = (
    'django_openid_auth.auth.OpenIDBackend',
    'django.contrib.auth.backends.ModelBackend',
)

OPENID_CREATE_USERS = True
OPENID_UPDATE_DETAILS_FROM_SREG = True
OPENID_SSO_SERVER_URL = 'https://login.launchpad.net/'

SERVE_ASSETS_FROM_DJANGO = False
