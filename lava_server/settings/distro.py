# Django settings for django_hello project used on Debian systems.

import re
from lava_server.settings.getsettings import Settings
from lava_server.settings.production import *
from django.db.backends.signals import connection_created

# Load application settings from lava_server.settings integration package
distro_settings = Settings("lava-server")

# Use timezone
USE_TZ = True

# Load the mount point from settings file
MOUNT_POINT = distro_settings.mount_point

# Load default database from distro integration
DATABASES = {'default': distro_settings.default_database}

# Load debug settings from the configuration file
DEBUG = distro_settings.DEBUG

# Load secret key from distro integration
SECRET_KEY = distro_settings.SECRET_KEY

# Absolute filesystem path to the directory that will hold user-uploaded files.
MEDIA_ROOT = distro_settings.MEDIA_ROOT

# Absolute filesystem path to the directory that will hold archived files.
ARCHIVE_ROOT = distro_settings.ARCHIVE_ROOT

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications.
STATIC_ROOT = distro_settings.STATIC_ROOT

# URL that handles the media served from STATIC_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://static.lawrence.com", "http://example.com/static/"
STATIC_URL = distro_settings.STATIC_URL

# List of absolute pathnames used to resolve templates.
TEMPLATES = distro_settings.TEMPLATES

# Like TEMPLATE_DIRS but for static files
STATICFILES_DIRS = distro_settings.STATICFILES_DIRS

# A tuple that lists people who get code error notifications. When DEBUG=False
# and a view raises an exception, Django will e-mail these people with the
# full exception information. Each member of the tuple should be a tuple of
# (Full name, e-mail address). Example:
ADMINS = distro_settings.ADMINS

# A tuple in the same format as ADMINS that specifies who should get
# broken-link notifications when BrokenLinkEmailsMiddleware is enabled
MANAGERS = distro_settings.MANAGERS

# LOG_SIZE_LIMIT in megabytes
LOG_SIZE_LIMIT = distro_settings.LOG_SIZE_LIMIT

# URL of the login page
LOGIN_URL = distro_settings.LOGIN_URL

# URL of the page you get redirected to after logging in
LOGIN_REDIRECT_URL = distro_settings.LOGIN_REDIRECT_URL

# The email address that error messages come from, such as those sent to
# ADMINS and MANAGERS.
if distro_settings.get_setting("SERVER_EMAIL"):
    SERVER_EMAIL = distro_settings.get_setting("SERVER_EMAIL")

# Atlassian Crowd authentication config
AUTH_CROWD_SERVER_REST_URI = distro_settings.get_setting("AUTH_CROWD_SERVER_REST_URI")
if AUTH_CROWD_SERVER_REST_URI:
    # If Crowd server URL is configured, disable OpenID and
    # enable Crowd auth backend
    INSTALLED_APPS.append('crowdrest')
    AUTHENTICATION_BACKENDS = ['crowdrest.backend.CrowdRestBackend'] + \
        [x for x in AUTHENTICATION_BACKENDS if "OpenID" not in x]

    # Load credentials from a separate file
    from lava_server.settings.config_file import ConfigFile
    pathname = distro_settings._get_pathname("crowd")
    crowd_config = ConfigFile.load(pathname)
    AUTH_CROWD_APPLICATION_USER = crowd_config.AUTH_CROWD_APPLICATION_USER
    AUTH_CROWD_APPLICATION_PASSWORD = crowd_config.AUTH_CROWD_APPLICATION_PASSWORD
    if distro_settings.get_setting("AUTH_CROWD_GROUP_MAP"):
        AUTH_CROWD_GROUP_MAP = distro_settings.get_setting("AUTH_CROWD_GROUP_MAP")

AUTH_DEBIAN_SSO = distro_settings.get_setting("AUTH_DEBIAN_SSO")

# LDAP authentication config
AUTH_LDAP_SERVER_URI = distro_settings.get_setting("AUTH_LDAP_SERVER_URI")
if AUTH_LDAP_SERVER_URI:
    INSTALLED_APPS.append('ldap')
    INSTALLED_APPS.append('django_auth_ldap')
    import ldap
    from django_auth_ldap.config import (LDAPSearch, LDAPSearchUnion)

    def get_ldap_group_types():
        """Return a list of all LDAP group types supported by django_auth_ldap module"""
        import django_auth_ldap.config
        import inspect
        types = []
        for name, obj in inspect.getmembers(django_auth_ldap.config):
            if inspect.isclass(obj) and name.endswith('Type'):
                types.append(name)

        return types

    AUTHENTICATION_BACKENDS = ['django_auth_ldap.backend.LDAPBackend',
                               'django.contrib.auth.backends.ModelBackend'] + \
        AUTHENTICATION_BACKENDS

    # Load credentials
    AUTH_LDAP_BIND_DN = distro_settings.get_setting("AUTH_LDAP_BIND_DN")
    AUTH_LDAP_BIND_PASSWORD = distro_settings.get_setting(
        "AUTH_LDAP_BIND_PASSWORD")
    AUTH_LDAP_USER_DN_TEMPLATE = distro_settings.get_setting(
        "AUTH_LDAP_USER_DN_TEMPLATE")
    AUTH_LDAP_USER_ATTR_MAP = distro_settings.get_setting(
        "AUTH_LDAP_USER_ATTR_MAP")

    if distro_settings.get_setting("AUTH_LDAP_USER_SEARCH"):
        AUTH_LDAP_USER_SEARCH = eval(distro_settings.get_setting(
            "AUTH_LDAP_USER_SEARCH"))
        # AUTH_LDAP_USER_SEARCH and AUTH_LDAP_USER_DN_TEMPLATE are mutually
        # exclusive, hence,
        AUTH_LDAP_USER_DN_TEMPLATE = None

    if distro_settings.get_setting("AUTH_LDAP_GROUP_SEARCH"):
        AUTH_LDAP_GROUP_SEARCH = eval(distro_settings.get_setting(
            "AUTH_LDAP_GROUP_SEARCH"))

    if distro_settings.get_setting("AUTH_LDAP_GROUP_TYPE"):
        group_type = distro_settings.get_setting("AUTH_LDAP_GROUP_TYPE")
        # strip params from group type to get the class name
        group_class = group_type.split('(', 1)[0]
        group_types = get_ldap_group_types()
        if group_class in group_types:
            exec('from django_auth_ldap.config import ' + group_class)
            AUTH_LDAP_GROUP_TYPE = eval(group_type)

    if distro_settings.get_setting("AUTH_LDAP_USER_FLAGS_BY_GROUP"):
        AUTH_LDAP_USER_FLAGS_BY_GROUP = distro_settings.get_setting(
            "AUTH_LDAP_USER_FLAGS_BY_GROUP")

    # read any LDAP login message to use from the settings.conf
    LOGIN_MESSAGE_LDAP = distro_settings.get_setting("LOGIN_MESSAGE_LDAP", "")
elif AUTH_DEBIAN_SSO:
    MIDDLEWARE_CLASSES.append('lava_server.debian_sso.DebianSsoUserMiddleware')
    AUTHENTICATION_BACKENDS.append('lava_server.debian_sso.DebianSsoUserBackend')

USE_DEBUG_TOOLBAR = distro_settings.get_setting('USE_DEBUG_TOOLBAR', False)

if USE_DEBUG_TOOLBAR:
    INSTALLED_APPS.append('debug_toolbar')
    default_ips = ['127.0.0.1', '::1']
    default_ips.extend(distro_settings.get_setting('INTERNAL_IPS', []))
    INTERNAL_IPS = default_ips

# handling for bots which don't deal with robots.txt properly
regexes = distro_settings.get_setting('DISALLOWED_USER_AGENTS', [])
for regex in regexes:
    DISALLOWED_USER_AGENTS.append(re.compile(r'%s' % regex, re.IGNORECASE))

# read branding details
BRANDING_ALT = distro_settings.get_setting("BRANDING_ALT", "Linaro logo")
BRANDING_ICON = distro_settings.get_setting("BRANDING_ICON", 'lava-server/images/logo.png')
BRANDING_URL = distro_settings.get_setting("BRANDING_URL", 'http://www.linaro.org')
BRANDING_HEIGHT = distro_settings.get_setting("BRANDING_HEIGHT", 22)
BRANDING_WIDTH = distro_settings.get_setting("BRANDING_WIDTH", 22)
BRANDING_BUG_URL = distro_settings.get_setting("BRANDING_BUG_URL", "https://bugs.linaro.org/enter_bug.cgi?product=LAVA%20Framework")
BRANDING_SOURCE_URL = distro_settings.get_setting("BRANDING_SOURCE_URL", "https://git.linaro.org/gitweb?s=lava%2Flava")

HIDE_V1_DOCS = distro_settings.get_setting("HIDE_V1_DOCS", False)
HIDE_V2_DOCS = distro_settings.get_setting("HIDE_V2_DOCS", False)
CUSTOM_DOCS = distro_settings.get_setting("CUSTOM_DOCS", {})

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
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'lava'
        },
        'logfile': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': distro_settings.get_setting("DJANGO_LOGFILE", "/var/log/lava-server/django.log"),
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
        'lava_results_app': {
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
        },
        'publisher': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        }
    }
}

# pipeline results display
# set to false in /etc/lava-server/settings.conf to hide the Results menu
PIPELINE = distro_settings.get_setting("PIPELINE", True)

# Scheduler options
SCHEDULER_DAEMON_OPTIONS.update(distro_settings.get_setting('SCHEDULER_DAEMON_OPTIONS', {}))

# Override ZMQ events defined in lava_scheduler_app.settings
EVENT_NOTIFICATION = distro_settings.get_setting("EVENT_NOTIFICATION", EVENT_NOTIFICATION)
INTERNAL_EVENT_SOCKET = distro_settings.get_setting("INTERNAL_EVENT_SOCKET", INTERNAL_EVENT_SOCKET)
EVENT_SOCKET = distro_settings.get_setting("EVENT_SOCKET", EVENT_SOCKET)
EVENT_ADDITIONAL_SOCKETS = distro_settings.get_setting("EVENT_ADDITIONAL_SOCKETS", EVENT_ADDITIONAL_SOCKETS)
EVENT_TOPIC = distro_settings.get_setting("EVENT_TOPIC", EVENT_TOPIC)


def set_timeout(connection, **kw):
    connection.cursor().execute("SET statement_timeout to 30000")


connection_created.connect(set_timeout)
