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

import contextlib
import imp
import re

from django.conf.global_settings import *

from lava_common.version import __version__
from lava_rest_app.versions import versions as REST_VERSIONS
from lava_scheduler_app.settings import *


# List of people who get code error notifications
# https://docs.djangoproject.com/en/1.11/ref/settings/#admins
ADMINS = [("lava-server Administrator", "root@localhost")]

# Allow only the connection through the reverse proxy
ALLOWED_HOSTS = ["[::1]", "127.0.0.1", "localhost"]

# Add the LAVA authentication backend
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "lava_server.backends.GroupPermissionBackend",
]

# Add a memory based cache
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Application definition
INSTALLED_APPS = [
    # Add LAVA applications
    "lava_server",
    "lava_results_app",
    "lava_scheduler_app",
    "lava_rest_app",
    # Add LAVA dependencies
    "django_tables2",
    "linaro_django_xmlrpc",
    "rest_framework",
    "django_filters",
    "rest_framework_filters",
    # Add contrib
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",  # FIXME: should not be needed anymore
]

# List of people who get broken link notifications
# https://docs.djangoproject.com/en/1.11/ref/settings/#managers
MANAGERS = ADMINS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lava_server.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "django.template.context_processors.static",
                # LAVA context processors
                "lava_server.context_processors.lava",
                "lava_server.context_processors.ldap_available",
            ]
        },
    }
]

WSGI_APPLICATION = "lava_server.wsgi.application"

# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# URL that handles the media served from STATIC_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://static.lawrence.com", "http://example.com/static/"
# https://docs.djangoproject.com/en/1.11/howto/static-files/
STATIC_URL = "/static/"

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications.
STATIC_ROOT = "/usr/share/lava-server/static"

# Absolute filesystem path to the directory that will hold user-uploaded files.
MEDIA_ROOT = "/var/lib/lava-server/default/media/"

# Default URL after login
LOGIN_REDIRECT_URL = "/"

# Set a site ID
# FIXME: should not be needed
SITE_ID = 1

# Django System check framework settings for security.* checks.
# Silence some checks that should be explicitly configured by administrators
# on need basis.
SILENCED_SYSTEM_CHECKS = [
    "security.W004",  # silence SECURE_HSTS_SECONDS
    "security.W008",  # silence SECURE_SSL_REDIRECT
]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
HTTPS_XML_RPC = True


########################
# LAVA custom settings #
########################

# LOG_SIZE_LIMIT in megabytes
LOG_SIZE_LIMIT = 5

# logging backend
LAVA_LOG_BACKEND = "lava_scheduler_app.logutils.LogsFilesystem"

# General URL prefix
MOUNT_POINT = ""

# When rendering the logs, above this limit, the testcase urls won't be
# resolved.
TESTCASE_COUNT_LIMIT = 10000

# Branding support
BRANDING_ALT = "LAVA Software logo"
BRANDING_ICON = "lava_server/images/logo.png"
BRANDING_URL = "https://lavasoftware.org"
BRANDING_HEIGHT = 22
BRANDING_WIDTH = 22
BRANDING_BUG_URL = "https://git.lavasoftware.org/lava/lava/issues"
BRANDING_SOURCE_URL = "https://git.lavasoftware.org/lava/lava"
BRANDING_MESSAGE = ""
BRANDING_CSS = ""

# Custom documentation
CUSTOM_DOCS = {}

# Logging
DJANGO_LOGFILE = "/var/log/lava-server/django.log"

# Configuration directories
DISPATCHER_CONFIG_PATH = "/etc/lava-server/dispatcher.d"
DEVICES_PATH = "/etc/lava-server/dispatcher-config/devices"
DEVICE_TYPES_PATHS = [
    "/etc/lava-server/dispatcher-config/device-types",
    "/usr/share/lava-server/device-types",
]
HEALTH_CHECKS_PATH = "/etc/lava-server/dispatcher-config/health-checks"

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

# Default callback http timeout in seconds
CALLBACK_TIMEOUT = 5

# Default length value for all tables
DEFAULT_TABLE_LENGTH = 25

# Extra context variables when validating the job definition schema
EXTRA_CONTEXT_VARIABLES = []

# Use default instance name
INSTANCE_NAME = "default"

# Sentry project url
SENTRY_DSN = ""

# Django debug toolbar
USE_DEBUG_TOOLBAR = False

# Encryption settings
ENCRYPT = False
MASTER_CERT = "/etc/lava-dispatcher/certificates.d/master.key_secret"
MASTER_CERT_PUB = "/etc/lava-dispatcher/certificates.d/master.key"
SLAVES_CERTS = "/etc/lava-dispatcher/certificates.d/"

# Alternative logging database settings.
MONGO_DB_URI = "mongodb://user:pass@localhost:27017/"
MONGO_DB_DATABASE = "lava-logs"

ELASTICSEARCH_URI = "http://localhost:9200/"
ELASTICSEARCH_INDEX = "lava-logs"
ELASTICSEARCH_APIKEY = ""

# Send notifications to worker admins after the master is upgraded.
MASTER_UPGRADE_NOTIFY = False

# Worker in the specific network will be allowed to auto register
WORKER_AUTO_REGISTER = True
WORKER_AUTO_REGISTER_NETMASK = ["127.0.0.0/8", "::1"]

################
# DRF settings #
################

# DRF may need this to be true when used in some instances.
USE_X_FORWARDED_HOST = False
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "ALLOWED_VERSIONS": REST_VERSIONS,
    "DEFAULT_FILTER_BACKENDS": (
        "lava_server.compat.NoMarkupFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ),
    "PAGE_SIZE": 50,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "lava_rest_app.authentication.LavaTokenAuthentication",
    ),
}


##################
# Import modules #
##################

# Automatically install some applications
for module_name in ["devserver", "django_extensions", "django_openid_auth"]:
    with contextlib.suppress(ImportError):
        imp.find_module(module_name)
        INSTALLED_APPS.append(module_name)

###########
# Helpers #
###########


def update(values):
    # Add values to the local context
    ADMINS = values.get("ADMINS")
    AUTH_LDAP_GROUP_SEARCH = values.get("AUTH_LDAP_GROUP_SEARCH")
    AUTH_LDAP_GROUP_TYPE = values.get("AUTH_LDAP_GROUP_TYPE")
    AUTH_LDAP_SERVER_URI = values.get("AUTH_LDAP_SERVER_URI")
    AUTH_LDAP_USER_SEARCH = values.get("AUTH_LDAP_USER_SEARCH")
    AUTH_DEBIAN_SSO = values.get("AUTH_DEBIAN_SSO")
    AUTHENTICATION_BACKENDS = values.get("AUTHENTICATION_BACKENDS")
    DISALLOWED_USER_AGENTS = values.get("DISALLOWED_USER_AGENTS")
    DJANGO_LOGFILE = values.get("DJANGO_LOGFILE")
    INSTALLED_APPS = values.get("INSTALLED_APPS")
    INTERNAL_IPS = values.get("INTERNAL_IPS")
    LOGGING = values.get("LOGGING")
    MANAGERS = values.get("MANAGERS")
    MIDDLEWARE = values.get("MIDDLEWARE")
    MOUNT_POINT = values.get("MOUNT_POINT")
    SENTRY_DSN = values.get("SENTRY_DSN")
    USE_DEBUG_TOOLBAR = values.get("USE_DEBUG_TOOLBAR")

    # Fix mount point
    # Remove the leading slash and keep only one trailing slash
    MOUNT_POINT = (MOUNT_POINT.rstrip("/") + "/").lstrip("/")

    # Set the session cookie path according to the mount point.
    # Hence cookies from two lava servers hosted on the same domain name but with
    # different path won't override each others.
    # Keep in mind that mount point is empty by default. In this case the session
    # cookie path should be "/" (it should never be empty).
    SESSION_COOKIE_PATH = "/" + MOUNT_POINT.lstrip("/")

    # Fix ADMINS and MANAGERS variables
    # In Django >= 1.9 this is a list of tuples
    # and https://docs.djangoproject.com/en/1.9/ref/settings/#admins
    ADMINS = [tuple(v) for v in ADMINS]
    MANAGERS = [tuple(v) for v in MANAGERS]

    # LDAP authentication config
    if AUTH_LDAP_SERVER_URI:
        INSTALLED_APPS.append("ldap")
        INSTALLED_APPS.append("django_auth_ldap")
        import ldap
        from django_auth_ldap.config import LDAPSearch, LDAPSearchUnion

        def get_ldap_group_types():
            """Return a list of all LDAP group types supported by django_auth_ldap module"""
            import django_auth_ldap.config
            import inspect

            types = []
            for name, obj in inspect.getmembers(django_auth_ldap.config):
                if inspect.isclass(obj) and name.endswith("Type"):
                    types.append(name)

            return types

        AUTHENTICATION_BACKENDS.append("django_auth_ldap.backend.LDAPBackend")

        # Available variables: AUTH_LDAP_BIND_DN, AUTH_LDAP_BIND_PASSWORD,
        # AUTH_LDAP_USER_DN_TEMPLATE AUTH_LDAP_USER_ATTR_MAP
        if AUTH_LDAP_USER_SEARCH:
            AUTH_LDAP_USER_SEARCH = eval(AUTH_LDAP_USER_SEARCH.encode("utf-8"))
            # AUTH_LDAP_USER_SEARCH and AUTH_LDAP_USER_DN_TEMPLATE are mutually
            # exclusive, hence,
            AUTH_LDAP_USER_DN_TEMPLATE = None

        if AUTH_LDAP_GROUP_SEARCH:
            AUTH_LDAP_GROUP_SEARCH = eval(AUTH_LDAP_GROUP_SEARCH.encode("utf-8"))

        if AUTH_LDAP_GROUP_TYPE:
            group_type = AUTH_LDAP_GROUP_TYPE
            # strip params from group type to get the class name
            group_class = group_type.split("(", 1)[0]
            group_types = get_ldap_group_types()
            if group_class in group_types:
                exec("from django_auth_ldap.config import " + group_class)
                AUTH_LDAP_GROUP_TYPE = eval(group_type)

    elif AUTH_DEBIAN_SSO:
        MIDDLEWARE.append("lava_server.debian_sso.DebianSsoUserMiddleware")
        AUTHENTICATION_BACKENDS.append("lava_server.debian_sso.DebianSsoUserBackend")

    if USE_DEBUG_TOOLBAR:
        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
        INTERNAL_IPS.extend(["127.0.0.1", "::1"])

    # List of compiled regular expression objects representing User-Agent strings
    # that are not allowed to visit any page, systemwide. Use this for bad
    # robots/crawlers
    DISALLOWED_USER_AGENTS = [
        re.compile(r"%s" % reg, re.IGNORECASE) for reg in DISALLOWED_USER_AGENTS
    ]

    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}
        },
        "formatters": {
            "lava": {"format": "%(levelname)s %(asctime)s %(module)s %(message)s"}
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "lava",
            },
            "logfile": {
                "class": "logging.handlers.WatchedFileHandler",
                "filename": DJANGO_LOGFILE,
                "formatter": "lava",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["logfile"],
                # DEBUG outputs all SQL statements
                "level": "ERROR",
                "propagate": True,
            },
            "django_auth_ldap": {
                "handlers": ["logfile"],
                "level": "INFO",
                "propagate": True,
            },
            "lava_results_app": {
                "handlers": ["logfile"],
                "level": "INFO",
                "propagate": True,
            },
            "lava_scheduler_app": {
                "handlers": ["logfile"],
                "level": "INFO",
                "propagate": True,
            },
        },
    }

    if SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            release=f"lava@{__version__}",
        )

    # Return settings
    return {k: v for (k, v) in locals().items() if k.isupper()}
