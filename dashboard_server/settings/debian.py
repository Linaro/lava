# Django settings for django_hello project used on Debian systems.

from django_debian.settings import Settings
from dashboard_server.settings.production import *

# Load application settings from django-debian integration package
debian_settings = Settings("launch-control")

# Load default database from Debian integration
DATABASES = {
    'default': debian_settings.default_database
}

# Load secret key from Debian integration
SECRET_KEY = debian_settings.SECRET_KEY

# Absolute filesystem path to the directory that will hold user-uploaded files.
MEDIA_ROOT = debian_settings.MEDIA_ROOT

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = debian_settings.MEDIA_URL

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications. 
STATIC_ROOT = debian_settings.STATIC_ROOT

# URL that handles the media served from STATIC_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://static.lawrence.com", "http://example.com/static/"
STATIC_URL = debian_settings.STATIC_URL

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = debian_settings.ADMIN_MEDIA_PREFIX

# List of absolute pathnames used to resolve templates.
TEMPLATE_DIRS = debian_settings.TEMPLATE_DIRS

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications. 
# TODO: debianize
STATICFILES_DIRS = [
    ('', "/usr/share/launch-control/htdocs"),
]

# A tuple that lists people who get code error notifications. When DEBUG=False
# and a view raises an exception, Django will e-mail these people with the
# full exception information. Each member of the tuple should be a tuple of
# (Full name, e-mail address). Example:
ADMINS = debian_settings.ADMINS

# A tuple in the same format as ADMINS that specifies who should get
# broken-link notifications when SEND_BROKEN_LINK_EMAILS=True.
MANAGERS = debian_settings.MANAGERS

# Whether to send an e-mail to the MANAGERS each time somebody visits a
# Django-powered page that is 404ed with a non-empty referer (i.e., a broken
# link). This is only used if CommonMiddleware is installed (see Middleware.
# See also IGNORABLE_404_STARTS, IGNORABLE_404_ENDS and Error reporting via
# e-mail.
SEND_BROKEN_LINK_EMAILS=debian_settings.SEND_BROKEN_LINK_EMAILS
