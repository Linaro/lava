import pexpect
import sys
from lava.dispatcher.client import LavaClient
from lava.dispatcher.android_config import BOARDS, TESTER_STR

class LavaAndroidClient(LavaClient):
    def __init__(self, hostname):
        super(LavaAndroidClient, self).__init__(hostname)
        self.board = BOARDS[hostname]

    def run_adb_shell_command(self, dev_id, cmd, response, timeout=-1):
        adb_cmd = "adb -s %s shell %s" % (dev_id, cmd)
        try:
            adb_proc = pexpect.spawn(adb_cmd, logfile=sys.stdout)
            id = adb_proc.expect([response, pexpect.EOF], timeout=timeout)
            if id == 0:
                return True
        except pexpect.TIMEOUT:
            pass
        return False

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

    def check_adb_status(self):
        # XXX: IP could be assigned in other way in the validation farm
        network_interface = self.board.network_interface 
        try:
            self.run_shell_command('netcfg %s dhcp' % \
                network_interface, response = TESTER_STR, timeout = 60)
        except:
            print "netcfg %s dhcp exception" % network_interface
            return False

        # Check network ip and setup adb connection
        ip_pattern = "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        cmd = "ifconfig %s" % network_interface
        self.proc.sendline('')
        self.proc.sendline(cmd)
        try:
            id = self.proc.expect([ip_pattern, pexpect.EOF], timeout = 60)
        except:
            print "ifconfig can not match ip pattern"
            return False
        if id == 0:
            match_group = self.proc.match.groups()
            if len(match_group) > 0:
                device_ip = match_group[0]
                adb_status, dev_name = self.android_adb_connect(device_ip)
                if adb_status == True:
                    print "dev_name = " + dev_name
                    result = self.run_adb_shell_command(dev_name, "echo 1", "1")
                    self.android_adb_disconnect(device_ip)
                    return result
        return False
