#!/usr/bin/python
# lc-tool - command line interface for validation dashboard
#
# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.


def find_sources():
    import os
    import sys
    base_path = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(base_path, "launch_control")):
        sys.path.append(base_path)


find_sources()

if __name__ == '__main__':
    try:
        from launch_control.commands.dispatcher import main
    except ImportError:
        print "Unable to import launch_control.commands.dispatcher"
        print "Your installation is probably faulty"
        raise
    else:
        main()
