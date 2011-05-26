from lava.dispatcher.config import Board

class BeagleBoard(Board):
    uboot_cmds = ["mmc init",
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
        "setenv bootcmd 'fatload mmc 0:5 0x80200000 uImage;"
        "fatload mmc 0:5 0x81600000 uInitrd;"
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
        "panda01": PandaBoard,
        }

#Test image recognization string
TESTER_STR = "android# "
