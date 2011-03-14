#!/usr/bin/env python
#
# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

def find_sources():
    import os
    import sys
    base_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..")
    if os.path.exists(os.path.join(base_path, "launch_control")):
        sys.path.insert(0, base_path)

find_sources()

from django.core.management import execute_manager
try:
    import dashboard_server.settings.development as settings
except ImportError as ex:
    import sys
    sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
    sys.stderr.write("Exception details: %r\n" % ex)
    sys.exit(1)


if __name__ == "__main__":
    execute_manager(settings)
