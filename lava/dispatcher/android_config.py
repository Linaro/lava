"""
This is an ugly hack, the uboot commands for a given board type and the board
type of a test machine need to come from the device registry.  This is an
easy way to look it up for now though, just to show the rest of the code
around it
"""

class Board:
    uboot_cmds = None
    type = None
    # boot partition number, counting from 1
    boot_part = 1
    # root partition number, counting from 1
    root_part = 2

class BeagleBoard(Board):
    uboot_cmds = ["mmc rescan 0",
        "setenv bootcmd 'fatload mmc 0:3 0x80000000 uImage;"
        "fatload mmc 0:3 0x81600000 uInitrd;"
        "bootm 0x80000000 0x81600000'",
        "setenv bootargs 'console=tty0 console=ttyO2,115200n8 "
        "rootwait rw earlyprintk fixrtc nocompcache "
        "vram=12M omapfb.debug=y omapfb.mode=dvi:1280x720MR-16@60 "
        "init=/init androidboot.console=ttyO2'",
        "boot"]
    type = "beagle"


class PandaBoard(Board):
    uboot_cmds = ["mmc rescan 0",
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
#Here, it still needs to maintain a map from boardid to board, for there is only
#boardid in jobfile.json
BOARDS = {
        "beagle01": BeagleBoard,
        "panda01": PandaBoard,
        }

#Main LAVA server IP in the boards farm
LAVA_SERVER_IP = "192.168.1.10"
LAVA_IMAGE_URL = "http://%s/images/tmp" % LAVA_SERVER_IP

#Test image recognization string
TESTER_STR = "# "
