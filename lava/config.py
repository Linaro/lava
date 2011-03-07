"""
This is an ugly hack, the uboot commands for a given board type and the board
type of a test machine need to come from the device registry.  This is an
easy way to look it up for now though, just to show the rest of the code
around it
"""

class BOARD_CFG:
    def __init__(self):
        self.uboot_add("bbg", ["mmc init",
            "setenv bootcmd 'fatload mmc 0:5 0x90800000 uImage; fatload mmc " \
            "0:5 0x90800000 uInitrd; bootm 0x90000000 0x90800000'",
            "setenv bootargs ' console=tty0 console=ttymxc0,115200n8 " \
            "root=LABEL=testrootfs rootwait ro'",
            "boot"])
        self.board_add("bbg01", "mx51evk")

    def uboot_add(self, boardtype, ubootcmd):
        """
        Add new board uboot cmd to BOARDS_UBOOT
        """
        self.BOARDS_UBOOT[boardtype] = ubootcmd

    def uboot_del(self, boardtype):
        """
        Delete BOARDS_UBOOT entry
        """
        del self.BOARDS_UBOOT[boardtype]

    def board_add(self, boardid, boardtype):
        """
        Add new board to BOARD_TYPE
        """
        self.BOARD_TYPE[boardid] = boardtype

    def board_del(self, boardid):
        """
        Delete board from BOARD_TYPE
        """
        del self.BOARD_TYPE[boardid]

    BOARDS_UBOOT = {
        "beagle":["mmc init",
            "setenv bootcmd 'fatload mmc 0:3 0x80000000 uImage; fatload mmc " \
            "0:3 0x81600000 uInitrd; bootm 0x80000000 0x81600000'",
            "setenv bootargs ' console=tty0 console=ttyO2,115200n8 " \
            "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc nocompcache "\
            "vram=12M omapfb.debug=y omapfb.mode=dvi:1280x720MR-16@60'",
            "boot"],
        "panda":["mmc init",
            "setenv bootcmd 'fatload mmc 0:5 0x80200000 uImage; fatload mmc " \
            "0:5 0x81600000 uInitrd; bootm 0x80200000 0x81600000'",
            "setenv bootargs ' console=tty0 console=ttyO2,115200n8 " \
            "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc nocompcache "\
            "vram=32M omapfb.vram=0:8M mem=463M ip=none'",
            "boot"],
    }

    BOARD_TYPE = {
        "panda01": "panda",
        "panda02": "panda",
        "beaglexm01": "beagle",
        "vexpress01": "vexpress",
        "vexpress02": "vexpress",
        }

class LAVA_SERVER_CFG:
    def  setip(self, ip):
        """
        set LAVA server IP
        """
        self.IP = ip

    IP = "192.168.1.10"


