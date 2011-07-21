# Copyright (C) 2011 Linaro Limited
#
# Author: Linaro Validation Team <linaro-dev@lists.linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

from lava_dispatcher.config import Board

class BeagleBoard(Board):
    uboot_cmds = ["mmc init",
        "mmc part 0",
        "setenv bootcmd 'fatload mmc 0:3 0x80000000 uImage;"
        "fatload mmc 0:3 0x81600000 uInitrd;"
        "bootm 0x80000000 0x81600000'",
        "setenv bootargs 'console=tty0 console=ttyO2,115200n8 "
        "rootwait rw earlyprintk fixrtc nocompcache "
        "vram=12M omapfb.debug=y omapfb.mode=dvi:1280x720MR-16@60 "
        "init=/init androidboot.console=ttyO2'",
        "boot"]
    type = "beagle"
    network_interface = "eth0"


class PandaBoard(Board):
    uboot_cmds = ["mmc init",
        "mmc part 0",
        "setenv bootcmd 'fatload mmc 0:3 0x80200000 uImage;"
        "fatload mmc 0:3 0x81600000 uInitrd;"
        "bootm 0x80200000 0x81600000'",
        "setenv bootargs 'console=tty0 console=ttyO2,115200n8 "
        "rootwait rw earlyprintk fixrtc nocompcache vram=32M "
        "omapfb.vram=0:8M mem=456M@0x80000000 mem=512M@0xA0000000 "
        "omapfb.debug=y omapfb.mode=dvi:1280x720MR-16@60 "
        "init=/init androidboot.console=ttyO2'",
        "boot"]
    type = "panda"
    network_interface = "eth0"


#Here, it still needs to maintain a map from boardid to board, for there is only
#boardid in jobfile.json
BOARDS = {
        "beagle01": BeagleBoard,
        "beagle02": BeagleBoard,
        "beagle03": BeagleBoard,
        "beagle04": BeagleBoard,
        "panda01": PandaBoard,
        "panda02": PandaBoard,
        "panda03": PandaBoard,
        "panda04": PandaBoard,
        }

#Test image recognization string
TESTER_STR = "root@linaro:"
