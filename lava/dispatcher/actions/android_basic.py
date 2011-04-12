#!/usr/bin/python
from lava.dispatcher.actions import BaseAndroidAction
from lava.dispatcher.client import OperationFailed
from lava.dispatcher.android_config import MASTER_STR, TESTER_STR
import time
import pexpect
import sys
from datetime import datetime

class cmd_test_android_basic(BaseAndroidAction):
    def run(self):
        #Make sure in test image now
        self.client.in_test_shell()

        #TODO: Checking if sdcard is mounted by vold to replace sleep idle
        time.sleep(30)

        self.client.run_shell_command('mkdir /sdcard/results',
            response = TESTER_STR)
        self.client.run_shell_command('mkdir /sdcard/results/android',
            response = TESTER_STR)

        # Get board and build information
        self.client.run_shell_command('getprop ro.build.product > /sdcard/results/android/basic',
            response = TESTER_STR)
        self.client.run_shell_command('getprop ro.board.platform >> /sdcard/results/android/basic',
            response = TESTER_STR)
        self.client.run_shell_command('getprop ro.build.description >> /sdcard/results/android/basic',
            response = TESTER_STR)
        self.client.run_shell_command('getprop ro.build.fingerprint >> /sdcard/results/android/basic',
            response = TESTER_STR)
        self.client.run_shell_command('getprop ro.serialno >> /sdcard/results/android/basic',
            response = TESTER_STR)

        # Check booting completeness
        self.client.run_shell_command('getprop dev.bootcomplete >> /sdcard/results/android/basic',
            response = TESTER_STR)
        self.client.run_shell_command('getprop sys.boot_completed >> /sdcard/results/android/basic',
            response = TESTER_STR)
        #TODO: Wait for boot completed, if timeout, do logcat and save as booting fail log
        self.client.run_shell_command('getprop init.svc.adbd >> /sdcard/results/android/basic',
            response = TESTER_STR)

        adb_status = self.check_adb_status()
        cmd = 'echo "adb_status %s" >> /sdcard/results/android/basic' % str(adb_status)
        self.client.run_shell_command(cmd, response = TESTER_STR)

        cmd = 'echo %s >> /sdcard/results/android/basic' % datetime.now()
        self.client.run_shell_command(cmd, response = TESTER_STR)


    def check_adb_status(self):
        # XXX: IP could be assigned in other way in the validation farm
        try:
            self.client.run_shell_command('netcfg usb0 dhcp', response = TESTER_STR, timeout = 60)
        except:
            return False

        # Check network ip and setup adb connection
        ip_pattern = "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        cmd = "ifconfig usb0"
        self.client.proc.sendline(cmd)
        id = self.client.proc.expect([ip_pattern, pexpect.EOF])
        if id == 0:
            match_group = self.client.proc.match.groups()
            if len(match_group) > 0:
                device_ip = match_group[0]
                adb_status, dev_name = self.client.check_android_adb_network_up(device_ip)
                if adb_status == True:
                    cmd = "adb -s %s shell echo 1" % dev_name
                    self.adb_proc = pexpect.spawn(cmd, timeout=300, logfile=sys.stdout)
                    id = self.adb_proc.expect(["1", "error"], timeout=5)
                    if id == 0:
                        return True
        return False
