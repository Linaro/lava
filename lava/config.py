"""
This is an ugly hack, the uboot commands for a given board type and the board
type of a test machine need to come from the device registry.  This is an
easy way to look it up for now though, just to show the rest of the code
around it
"""

class BOARD_CFG:
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
        "bbg":["mmc init",
            "setenv bootcmd 'fatload mmc 0:5 0x90800000 uImage; fatload mmc " \
            "0:5 0x90800000 uInitrd; bootm 0x90000000 0x90800000'",
            "setenv bootargs ' console=tty0 console=ttymxc0,115200n8 " \
            "root=LABEL=testrootfs rootwait ro'",
            "boot"],
    }

    BOARD_TYPE = {
        "panda01": "panda",
        "panda02": "panda",
        "beaglexm01": "beagle",
        "vexpress01": "vexpress",
        "vexpress02": "vexpress",
        "bbg01": "mx51evk",
        }

class LAVA_SERVER_CFG:
    IP = "192.168.1.10"
    HOSTNAME = ""


if __name__ == "__main__":
    """
    unit test by executing:
    python -m lava.config
    in lp:lava root directory
    """
    #load lava server cfg
    print "Board type map"
    print "%s %s" % (LAVA_SERVER_CFG.IP, LAVA_SERVER_CFG.HOSTNAME)

    print "\nUboot cmd map"
    for name, type in BOARD_CFG.BOARD_TYPE.items():
        print "%s: %s" %(name, type)

    for type, cmd in BOARD_CFG.BOARDS_UBOOT.items():
        print "%s: %s" %(type, cmd)

