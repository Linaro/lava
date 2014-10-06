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

import django

# Administrator contact, used for sending
# emergency email when something breaks
ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = [
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'lava_server.urls'

STATICFILES_MEDIA_DIRNAMES = (
    "media",
    "static",
)

STATICFILES_PREPEND_LABEL_APPS = [
]

if django.VERSION < (1, 4):
    STATICFILES_PREPEND_LABEL_APPS.append("django.contrib.admin")

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = "/media/"

# URL that handles the media served from STATIC_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://static.lawrence.com", "http://example.com/static/"
STATIC_URL = "/static/"

MOUNT_POINT = ""

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = MOUNT_POINT + "/static/admin/"

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
    'django_openid_auth',
    'django_tables2',
    'django.contrib.staticfiles',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
    # Admin docs disabled due to: https://code.djangoproject.com/ticket/6681
    # 'longerusername',
    'linaro_django_xmlrpc',
    'lava_markitup',  # Support app for MarkItUp in LAVA
    'google_analytics',
]

if django.VERSION < (1, 7):
    # Django 1.7 has built-in migration suppport
    INSTALLED_APPS += ['south']
else:
    TEST_RUNNER = 'django.test.runner.DiscoverRunner'

try:
    import devserver
    INSTALLED_APPS += ['devserver']
except ImportError:
    pass

TEMPLATE_CONTEXT_PROCESSORS = [
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
    "django.core.context_processors.static",
    "lava_server.context_processors.lava",
    "lava_server.context_processors.openid_available",
    "lava_server.context_processors.ldap_available",
]


AUTHENTICATION_BACKENDS = (
    # Uncomment CrowdRestBackend and comment OpenIDBackend to enable
    # Atlassian Crowd auth.
    # 'crowdrest.backend.CrowdRestBackend',

    # Uncomment LDAPBackend and comment OpenIDBackend to enable LDAP auth and
    # make sure LDAP auth parameters are set properly.
    # 'django_auth_ldap.backend.LDAPBackend',

    'django_openid_auth.auth.OpenIDBackend',
    'django.contrib.auth.backends.ModelBackend',
)

# Uncomment the following lines to configure LDAP auth parameters. For details
# on configuration parameters,
# see: https://pythonhosted.org/django-auth-ldap/authentication.html
# AUTH_LDAP_SERVER_URI = "ldap://yourldapservername"
# AUTH_LDAP_BIND_DN = ""
# AUTH_LDAP_BIND_PASSWORD = ""
# AUTH_LDAP_USER_DN_TEMPLATE = "uid=%(user)s,ou=users,dc=example,dc=com"

# Uncomment the following lines, if you need logging enabled for LDAP auth.
# import logging
# logger = logging.getLogger('django_auth_ldap')
# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)

OPENID_CREATE_USERS = True
OPENID_LAUNCHPAD_TEAMS_MAPPING_AUTO = False
OPENID_UPDATE_DETAILS_FROM_SREG = True
OPENID_SSO_SERVER_URL = 'https://login.ubuntu.com/'

# python-openid is too noisy, so we silence it.
from openid import oidutil
oidutil.log = lambda msg, level=0: None

RESTRUCTUREDTEXT_FILTER_SETTINGS = {"initial_header_level": 4}

# Add google analytics model.
GOOGLE_ANALYTICS_MODEL = True

ME_PAGE_ACTIONS = [
    ("django.contrib.auth.views.password_change", "Change your password"),
    ("django.contrib.auth.views.logout", "Sign out"),
]

ALLOWED_HOSTS = ['*']

SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'
