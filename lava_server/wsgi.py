# -*- coding: utf-8 -*-
# Copyright (C) 2016-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

import os

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
        cursor.execute("SET statement_timeout TO 30000")


connection_created.connect(setup_postgres, dispatch_uid="setup_postgres")

# Create the application
application = get_wsgi_application()
