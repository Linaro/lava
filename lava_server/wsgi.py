# Copyright (C) 2016 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

import os

from django.core.wsgi import get_wsgi_application


# Set the environment variables for Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lava_server.settings.distro")
os.environ.setdefault("DJANGO_DEBIAN_SETTINGS_TEMPLATE",
                      "/etc/lava-server/{filename}.conf")

# Create the application
application = get_wsgi_application()
