from unittest import TestCase
from lava.config import Board, BeagleBoard, PandaBoard, Mx51ekvBoard
from lava.config import Boards, LAVA_SERVER_IP

class TestConfigData(TestCase):
    def test_beaglexm01_uboot_cmds(self):
        expected = [
            "mmc init",
            "setenv bootcmd 'fatload mmc 0:3 0x80000000 uImage; fatload mmc "
                "0:3 0x81600000 uInitrd; bootm 0x80000000 0x81600000'",
            "setenv bootargs ' console=tty0 console=ttyO2,115200n8 "
                "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc "
                "nocompcache vram=12M omapfb.debug=y "
                "omapfb.mode=dvi:1280x720MR-16@60'",
            "boot"]
        brd = Boards["beaglexm01"]
        uboot_cmds = brd.uboot_cmds
        self.assertEquals(expected, uboot_cmds)

    def test_server_ip(self):
        expected = "192.168.1.10"
        self.assertEqual(expected, LAVA_SERVER_IP)

