import pexpect

BOARDS = {
    "beagle":["mmc init",
        "setenv bootcmd 'fatload mmc 0:3 0x80000000 uImage; fatload mmc " \
        "0:3 0x81600000 uInitrd; bootm 0x80000000 0x81600000'",
        "setenv bootargs ' console=tty0 console=ttyO2,115200n8 " \
        "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc nocompcache " \
        "vram=12M omapfb.debug=y omapfb.mode=dvi:1280x720MR-16@60'",
        "boot"],
    "panda":["mmc init",
        "setenv bootcmd 'fatload mmc 0:1 0x80200000 uImage; fatload mmc " \
        "0:1 0x81600000 uInitrd; bootm 0x80200000 0x81600000'",
        "setenv bootargs ' console=tty0 console=ttyO2,115200n8 " \
        "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc nocompcache " \
        "vram=32M omapfb.vram=0:8M mem=463M ip=none'",
        "boot"]
}

class SerialClient:
    def __init__(self, hostname, board_type):
        cmd = "console %s" % hostname
        self.proc = pexpect.spawn(cmd, timeout=300)
        #serial can be slow, races do funny things if ou don't increase delay
        self.proc.delaybeforesend=1
        #This is temporary, eventually I think this should be looked up
        self.board_type = board_type

    def in_master_shell(self):
        """ Check that we are in a shell on the master image
        """
        self.proc.sendline("")
        id = self.proc.expect(['root@master:', pexpect.TIMEOUT])
        if id == 1:
            raise OperationFailed

    def in_test_shell(self):
        """ Check that we are in a shell on the test image
        """
        self.proc.sendline("")
        id = self.proc.expect(['root@localhost:', pexpect.TIMEOUT])
        if id == 1:
            raise OperationFailed

    def boot_master_image(self):
        """ reboot the system, and check that we are in a master shell
        """
        self.soft_reboot()
        try:
            self.proc.expect("Starting kernel")
            self.in_master_shell()
        except:
            self.hard_reboot()
            try:
                self.in_master_shell()
            except:
                raise

    def boot_test_image(self):
        """ Reboot the system to the test image
        """
        self.soft_reboot()
        try:
            self.proc.expect("Starting kernel")
            self.enter_uboot()
        except:
            self.hard_reboot()
            self.enter_uboot()
        uboot_cmds = BOARDS[self.board_type]
        self.proc.sendline(uboot_cmds[0])
        for line in range(1, len(uboot_cmds)):
            self.proc.expect("#")
            self.proc.sendline(uboot_cmds[line])
        try:
            self.in_test_shell()
        except:
            raise

    def enter_uboot(self):
        id = self.proc.expect("Hit any key to stop autoboot")
        self.proc.sendline("")

    def soft_reboot(self):
        self.proc.sendline("reboot")

    def hard_reboot(self):
        self.proc.send("~$")
        self.proc.sendline("hardreset")

class OperationFailed(Exception):
    pass

