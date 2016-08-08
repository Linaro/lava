# Copyright (C) 2010-2013 Linaro Limited
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


# WARNING:
# Never edit this file on a production system!
# Any changes can be overwritten at any time by upgrade or any
# system management operation. All production config changes
# should happen strictly to etc/settings.conf, etc. files.
# All comments below are strictly for development usage and
# reference.

# Import application settings
from lava_scheduler_app.settings import *

import os
import imp

# Check for available modules
available_modules = list()
for module_name in ["devserver", "django_extensions", "django_openid_auth", "hijack"]:
    try:
        imp.find_module(module_name)
        available_modules.append(module_name)
    except ImportError:
        pass

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

SITE_ID = 1

DISALLOWED_USER_AGENTS = []

PROJECT_DIR = os.path.dirname(os.path.join(os.path.dirname(__file__), '..', '..'))
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(PROJECT_DIR, 'templates'),
        ],
        'OPTIONS': {
            'context_processors': [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.static",
                # LAVA context processors
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

MIDDLEWARE_CLASSES = [
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'lava_server.urls'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/
STATIC_URL = "/static/"

# General URL prefix
MOUNT_POINT = ""

# The true outer url is /lava-server/
LOGIN_REDIRECT_URL = MOUNT_POINT + "/"

# URL of the login screen, has to be hard-coded like that for Django.
# I cheat a little, using DATA_URL_PREFIX here is technically incorrect
# but it seems better than hard-coding 'lava-server' yet again.
LOGIN_URL = MOUNT_POINT + "/accounts/login/"

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    # Add LAVA applications
    'dashboard_app',
    'lava_results_app',
    'lava_scheduler_daemon',
    'lava_scheduler_app',
    # Needed applications
    'django_tables2',
    'linaro_django_xmlrpc',
    'google_analytics',
]

for module_name in available_modules:
    INSTALLED_APPS.append(module_name)

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']

if "django_openid_auth" in available_modules:
    AUTHENTICATION_BACKENDS.append('django_openid_auth.auth.OpenIDBackend')
    MIGRATION_MODULES = {
        'django_openid_auth': 'django_openid_auth.migrations'
    }

    OPENID_CREATE_USERS = True
    OPENID_LAUNCHPAD_TEAMS_MAPPING_AUTO = False
    OPENID_UPDATE_DETAILS_FROM_SREG = True
    OPENID_SSO_SERVER_URL = 'https://login.ubuntu.com/'

    # python-openid is too noisy, so we silence it.
    from openid import oidutil
    oidutil.log = lambda msg, level=0: None

# Add google analytics model.
GOOGLE_ANALYTICS_MODEL = True

ALLOWED_HOSTS = ['*']

# this is a tad ugly but the upstream package still needs something here.
KEY_VALUE_STORE_BACKEND = 'db://lava_scheduler_app_devicedictionarytable'
