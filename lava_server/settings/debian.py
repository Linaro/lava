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
# TODO: debianize
MEDIA_ROOT = "/var/lib/launch-control/media/"

# Absolute filesystem path to the directory that will hold static, read only
# files collected from all applications. 
# TODO: debianize
STATIC_ROOT = "/var/lib/launch-control/static/"

# TODO: debianize
TEMPLATE_DIRS = (
    "/etc/launch-control/templates/",
    "/usr/share/launch-control/templates/"
)

STATICFILES_DIRS = [
    ('', "/usr/share/launch-control/htdocs"),
]
