import pexpect
import sys
from lava.dispatcher.client import LavaClient
from lava.dispatcher.android_config import BOARDS, TESTER_STR

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
        id = self.proc.expect(["android#", pexpect.TIMEOUT])
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
        self.proc.sendline("export PS1=\"android# \"")

    def android_logcat_clear(self):
        cmd = "logcat -c"
        self.proc.sendline(cmd)

    def _android_logcat_start(self):
        cmd = "logcat"
        self.proc.sendline(cmd)

    def android_logcat_monitor(self, pattern, timeout=-1):
        self.android_logcat_stop()
        cmd = 'logcat'
        self.proc.sendline(cmd)
        id = self.proc.expect(pattern, timeout=timeout)
        if id == 0:
            return True
        else:
            return False

    def android_logcat_stop(self):
        self.proc.sendcontrol('C')
        print "logcat cancelled"

    # adb cound be connected through network
    def android_adb_connect(self, dev_ip):
        pattern1 = "connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern2 = "already connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern3 = "unable to connect to"

        cmd = "adb connect %s" % dev_ip
        adb_proc = pexpect.spawn(cmd, timeout=300, logfile=sys.stdout)
        id = adb_proc.expect([pattern1, pattern2, pattern3, pexpect.EOF])
        if id == 0:
            dev_name = adb_proc.match.groups()[0]
            return True, dev_name
        else:
            return False, None

    def android_adb_disconnect(self, dev_ip):
        cmd = "adb disconnect %s" % dev_ip
        adb_proc = pexpect.run(cmd, timeout=300, logfile=sys.stdout)
