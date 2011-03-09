import pexpect
import sys
import time

"""
This is an ugly hack, the uboot commands for a given board type and the board
type of a test machine need to come from the device registry.  This is an
easy way to look it up for now though, just to show the rest of the code
around it
"""
BOARDS = {
    "beagle":["mmc init",
        "setenv bootcmd 'fatload mmc 0:3 0x80000000 uImage; fatload mmc " \
        "0:3 0x81600000 uInitrd; bootm 0x80000000 0x81600000'",
        "setenv bootargs ' console=tty0 console=ttyO2,115200n8 " \
        "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc nocompcache " \
        "vram=12M omapfb.debug=y omapfb.mode=dvi:1280x720MR-16@60'",
        "boot"],
    "panda":["mmc init",
        "setenv bootcmd 'fatload mmc 0:5 0x80200000 uImage; fatload mmc " \
        "0:5 0x81600000 uInitrd; bootm 0x80200000 0x81600000'",
        "setenv bootargs ' console=tty0 console=ttyO2,115200n8 " \
        "root=LABEL=testrootfs rootwait ro earlyprintk fixrtc nocompcache " \
        "vram=32M omapfb.vram=0:8M mem=463M ip=none'",
        "boot"]
}

BOARD_TYPE = {
    "panda01": "panda",
    "panda02": "panda",
    "beaglexm01": "beagle",
    "vexpress01": "vexpress",
    "vexpress02": "vexpress"
    }

class LavaClient:
    def __init__(self, hostname):
        cmd = "conmux-console %s" % hostname
        self.proc = pexpect.spawn(cmd, timeout=300, logfile=sys.stdout)
        #serial can be slow, races do funny things if you don't increase delay
        self.proc.delaybeforesend=1
        #This is temporary, eventually this should come from the db
        self.board_type = BOARD_TYPE[hostname]

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

    def boot_linaro_image(self):
        """ Reboot the system to the test image
        """
        self.soft_reboot()
        try:
            self.enter_uboot()
        except:
            self.hard_reboot()
            self.enter_uboot()
        uboot_cmds = BOARDS[self.board_type]
        self.proc.sendline(uboot_cmds[0])
        for line in range(1, len(uboot_cmds)):
            self.proc.expect("#")
            self.proc.sendline(uboot_cmds[line])
        self.in_test_shell()

    def enter_uboot(self):
        self.proc.expect("Hit any key to stop autoboot")
        self.proc.sendline("")

    def soft_reboot(self):
        self.proc.sendline("reboot")

    def hard_reboot(self):
        self.proc.send("~$")
        self.proc.sendline("hardreset")

    def run_shell_command(self, cmd, response=None, timeout=-1):
        self.proc.sendline(cmd)
        if response:
            id = self.proc.expect(response, timeout=timeout)
            if id == 0:
                return True
            else:
                return False
        return True

    def check_network_up(self):
        self.proc.sendline("LC_ALL=C ping -W4 -c1 192.168.1.10")
        id = self.proc.expect(["1 received", "0 received"], timeout=5)
        if id == 0:
            return True
        else:
            return False

    def wait_network_up(self, timeout=60):
        now = time.time()
        while time.time() < now+timeout:
            if self.check_network_up():
                return
        raise NetworkError


class NetworkError(Exception):
    """
    This is used when a network error occurs, such as failing to bring up
    the network interface on the client
    """


class OperationFailed(Exception):
    pass

