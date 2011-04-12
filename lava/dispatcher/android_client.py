import pexpect
import sys
from lava.dispatcher.client import LavaClient
from lava.dispatcher.android_config import BOARDS, LAVA_SERVER_IP, TESTER_STR, MASTER_STR

class LavaAndroidClient(LavaClient):
    def __init__(self, hostname):
        super(LavaAndroidClient, self).__init__(hostname)
        self.board = BOARDS[hostname]

    def run_adb_shell_command(self, cmd, response=None, timeout=-1):
        pass

    def in_test_shell(self):
        """ Check that we are in a shell on the test image
        """
        self.proc.sendline("")
        id = self.proc.expect([TESTER_STR, pexpect.TIMEOUT])
        if id == 1:
            raise OperationFailed

    def boot_linaro_android_image(self):
        """ Reboot the system to the test android image
        """
        self.soft_reboot()
        try:
            self.enter_uboot()
        except:
            self.hard_reboot()
            self.enter_uboot()
        uboot_cmds = self.board.uboot_cmds
        self.proc.sendline(uboot_cmds[0])
        for line in range(1, len(uboot_cmds)):
            self.proc.expect("#")
            self.proc.sendline(uboot_cmds[line])
        self.in_test_shell()

    # adb cound be connected through network
    def check_android_adb_network_up(self, dev_ip):
        pattern1 = "connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern2 = "already connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern3 = "unable to connect to"

        cmd = "adb connect %s" % dev_ip
        adb_proc = pexpect.spawn(cmd, timeout=300, logfile=sys.stdout)
        id = adb_proc.expect([pattern1, pattern2, pattern3, pexpect.EOF])
        if id ==0:
            dev_name = adb_proc.match.groups()[0]
            return True, dev_name
        else:
            return False, None

