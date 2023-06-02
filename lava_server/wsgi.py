# Copyright (C) 2016-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.db.backends.signals import connection_created

# Set the environment variables for Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lava_server.settings.prod")


# Set the postgresql connection timeout
# The timeout is only used when running through wsgi.  This way, command line
# commands are not affected by the timeout.
def setup_postgres(connection, **kwargs):
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute("SET statement_timeout TO %s", (settings.STATEMENT_TIMEOUT,))


connection_created.connect(setup_postgres, dispatch_uid="setup_postgres")

# Create the application
application = get_wsgi_application()
