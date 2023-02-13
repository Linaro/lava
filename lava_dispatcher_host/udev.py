# Copyright (C) 2019 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

import sys

__udev_rules__ = """\
# udev rules installed by lava-dispatcher-host
#
# This file will be overritten by lava-dispatcher-host on upgrades. If you need
# to make customizations, please use a separate file.

ACTION=="add", ENV{{ID_FS_LABEL}}!="" \\
    RUN+="{lava_dispatcher_host} devices share --remote $name --fs-label=%E{{ID_FS_LABEL}}"

ACTION=="add", ATTR{{serial}}!="" \\
    RUN+="{lava_dispatcher_host} devices share --remote $name --serial-number=$attr{{serial}}"

ACTION=="add", ATTR{{idVendor}}!="", ATTR{{idProduct}}!="" \\
    RUN+="{lava_dispatcher_host} devices share --remote $name --vendor-id=$attr{{idVendor}} --product-id=$attr{{idProduct}}"

ACTION=="add", ATTRS{{idVendor}}!="", ATTRS{{idProduct}}!="" \\
    RUN+="{lava_dispatcher_host} devices share --remote $name --vendor-id=$attr{{idVendor}} --product-id=$attr{{idProduct}}"
"""


def get_udev_rules():
    program = sys.argv[0] + " --debug-log=/var/log/lava-dispatcher-host.log"
    return __udev_rules__.format(lava_dispatcher_host=program)
