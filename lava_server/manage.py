#!/usr/bin/env python
#
# Copyright (C) 2010 Linaro Limited
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

def find_sources():
    import os
    import sys
    base_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..")
    if os.path.exists(os.path.join(base_path, "lava_server")):
        sys.path.insert(0, base_path)

find_sources()

from django.core.management import execute_manager
try:
    import lava_server.settings.development as settings
except ImportError as ex:
    import logging
    logging.exception("Unable to import application settings")
    raise SystemExit(ex)


def main():
    execute_manager(settings)

if __name__ == "__main__":
    main()
