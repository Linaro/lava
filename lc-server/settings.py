"""
Settings module suitable for development
"""

# CONFIGURATION
# =============
#
# To configure the server create local_settings.py and change the
# following line from `CONFIGURED = False' to `CONFIGURED = True'.
#
# Look at default_settings.py for explanation on what can be changed.
#
# When this is False a very simple configuration is created that allows
# you to run the server directly from the development environment.
CONFIGURED = False

# DO NOT CHANGE SETTINGS BELOW
# ============================
from default_settings import *

if not CONFIGURED:
    DATABASE_ENGINE = 'sqlite3'
    DATABASE_NAME = os.path.join(BASE_DIR, 'database.db')
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")
    MEDIA_URL = '/site_media/'
    DEBUG = True
    TEMPLATE_DEBUG = DEBUG
    ADMINS = ()
    SECRET_KEY = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    try:
        # You still might want this to configure email and
        # administration stuff. I do this for development 
        from local_settings import *
    except ImportError:
        pass
else:
    from local_settings import *
