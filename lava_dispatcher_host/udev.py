# Copyright (C) 2019 Linaro Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys

__udev_rules__ = """\
# udev rules installed by lava-dispatcher-host
#
# This file will be overritten by lava-dispatcher-host on upgrades. If you need
# to make customizations, please use a separate file.

ACTION=="add", ENV{{ID_FS_LABEL}}!="" \\
    RUN+="{lava_dispatcher_host} devices share $name --fs-label=%E{{ID_FS_LABEL}}"

ACTION=="add", ATTR{{serial}}!="" \\
    RUN+="{lava_dispatcher_host} devices share $name --serial-number=$attr{{serial}}"

ACTION=="add", ATTR{{idVendor}}!="", ATTR{{idProduct}}!="" \\
    RUN+="{lava_dispatcher_host} devices share $name --vendor-id=$attr{{idVendor}} --product-id=$attr{{idProduct}}"

ACTION=="add", ATTRS{{idVendor}}!="", ATTRS{{idProduct}}!="" \\
    RUN+="{lava_dispatcher_host} devices share $name --vendor-id=$attr{{idVendor}} --product-id=$attr{{idProduct}}"
"""


def get_udev_rules():
    program = sys.argv[0] + " --debug-log=/var/log/lava-dispatcher-host.log"
    return __udev_rules__.format(lava_dispatcher_host=program)
