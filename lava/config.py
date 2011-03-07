"""
This is an ugly hack, the uboot commands for a given board type and the board
type of a test machine need to come from the device registry.  This is an
easy way to look it up for now though, just to show the rest of the code
around it
"""

class Board(object):
    def __init__(self, name):
        self.name = name

    def change_uboot_cmds(self, uboot_cmds):
        self.uboot_cmds = uboot_cmds

class BeagleBoard(Board):
    def __init__(self, name):
        Board.__init__(self, name)
        self.uboot_cmds = ["mmc init",
            "setenv bootcmd 'fatload mmc 0:3 0x80000000 uImage; fatload mmc " \
            "0:3 0x81600000 uInitrd; bootm 0x80000000 0x81600000'",
            "setenv bootargs ' console=tty0 console=ttyO2,115200n8 " \
            "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc nocompcache "\
            "vram=12M omapfb.debug=y omapfb.mode=dvi:1280x720MR-16@60'",
            "boot"]

class PandaBoard(Board):
    def __init__(self, name):
        Board.__init__(self, name)
        self.uboot_cmds = ["mmc init",
            "setenv bootcmd 'fatload mmc 0:5 0x80200000 uImage; fatload mmc " \
            "0:5 0x81600000 uInitrd; bootm 0x80200000 0x81600000'",
            "setenv bootargs ' console=tty0 console=ttyO2,115200n8 " \
            "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc nocompcache "\
            "vram=32M omapfb.vram=0:8M mem=463M ip=none'",
            "boot"]

class Mx51evkBoard(Board):
    def __init__(self, name):
        Board.__init__(self, name)
        self.uboot_cmds = ["mmc init",
            "setenv bootcmd 'fatload mmc 0:5 0x90800000 uImage; fatload mmc " \
            "0:5 0x90800000 uInitrd; bootm 0x90000000 0x90800000'",
            "setenv bootargs ' console=tty0 console=ttymxc0,115200n8 " \
            "root=LABEL=testrootfs rootwait ro'",
            "boot"]

class VexpressBoard(Board):
    def __init__(self, name):
        Board.__init__(self, name)
        #vexpress board uboot cmds is not exact here, please check if a board
        #is available
        self.uboot_cmds = ["mmc init",
            "setenv bootcmd 'fatload mmc 0:5 0x80000000 uImage; fatload mmc " \
            "0:5 0x81600000 uInitrd; bootm 0x80000000 0x81600000'",
            "setenv bootargs ' console=tty0 console=ttyO2,115200n8 " \
            "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc nocompcache "\
            "vram=12M omapfb.debug=y omapfb.mode=dvi:1280x720MR-16@60'",
            "boot"]

#Here, it still needs to maintain a map from boardid to board, for there is only
#boardid in jobfile.json
Boards = {
        "panda01": PandaBoard("panda01"),
        "panda02": PandaBoard("panda02"),
        "beagle01": BeagleBoard("beagle01"),
        "vexpress01": VexpressBoard("vexpress01"),
        "vexpress02": VexpressBoard("vexpress02"),
        "bbg01": Mx51evkBoard("bbg01"),
        }

#Main LAVA server IP in the boards farm
LAVA_SERVER_IP = "192.168.1.10"
