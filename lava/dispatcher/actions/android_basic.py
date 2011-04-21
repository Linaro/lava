#!/usr/bin/python
from lava.dispatcher.actions import BaseAndroidAction
from lava.dispatcher.client import OperationFailed
from lava.dispatcher.android_config import MASTER_STR, TESTER_STR
import time
import pexpect
import sys
from datetime import datetime
from lava.dispatcher.android_util import savebundlefile

class cmd_test_android_basic(BaseAndroidAction):
    network_interface = "eth0"

    def run(self):
        #Make sure in test image now
        self.client.in_test_shell()

        #TODO: Checking if sdcard is mounted by vold to replace sleep idle, or check the Home app status
        # Give time for Android system to boot up, then test
        time.sleep(30)
        TIMEFORMAT = '%Y-%m-%dT%H:%M:%SZ'
        starttime = datetime.utcnow()
        timestring = datetime.strftime(starttime, TIMEFORMAT)
        results = {'test_results':[]}

        # Check booting completeness
        # Transfer the result to launch-control json representation
        result_pattern = "([0-1])"
        test_case_result = {}
        test_case_result['test_case_id'] = "dev.bootcomplete"
        test_case_result['units'] = ""
        cmd = "getprop dev.bootcomplete"
        self.client.proc.sendline(cmd)
        id = self.client.proc.expect([result_pattern, pexpect.EOF], timeout = 5)
        if id == 0:
            match_group = self.client.proc.match.groups()
            test_case_result['measurement'] = match_group[0]
            if test_case_result['measurement'] == "1":
                test_case_result['result'] = "pass"
            else:
                test_case_result['result'] = "fail"
        else:
            test_case_result['measurement'] = ""
            test_case_result['result'] = "unknown"
        results['test_results'].append(test_case_result)

        test_case_result = {}
        test_case_result['test_case_id'] = "sys.boot_completed"
        test_case_result['units'] = ""
        cmd = "getprop sys.boot_completed"
        self.client.proc.sendline(cmd)
        try:
            id = self.client.proc.expect([result_pattern, pexpect.EOF], timeout = 5)
            if id == 0:
                match_group = self.client.proc.match.groups()
                test_case_result['measurement'] = match_group[0]
                if test_case_result['measurement'] == "1":
                    test_case_result['result'] = "pass"
                else:
                    test_case_result['result'] = "fail"
            else:
                test_case_result['measurement'] = ""
                test_case_result['result'] = "unknown"
        except:
            test_case_result['measurement'] = "exception"
            test_case_result['result'] = "fail"
            pass

        results['test_results'].append(test_case_result)

        result_pattern = "(running)"
        test_case_result = {}
        test_case_result['test_case_id'] = "init.svc.adbd"
        test_case_result['units'] = ""
        cmd = "getprop init.svc.adbd"
        self.client.proc.sendline(cmd)
        id = self.client.proc.expect([result_pattern, pexpect.EOF], timeout = 5)
        if id == 0:
            match_group = self.client.proc.match.groups()
            test_case_result['measurement'] = match_group[0]
            if test_case_result['measurement'] == "running":
                test_case_result['result'] = "pass"
            else:
                test_case_result['result'] = "fail"
        else:
            test_case_result['measurement'] = ""
            test_case_result['result'] = "unknown"
        results['test_results'].append(test_case_result)

        #TODO: Wait for boot completed, if timeout, do logcat and save as booting fail log

        adb_status = self.check_adb_status()
        test_case_result = {}
        test_case_result['test_case_id'] = "adb connection status"
        test_case_result['units'] = ""
        test_case_result['measurement'] = adb_status
        if adb_status:
            test_case_result['result'] = "pass"
        else:
            test_case_result['result'] = "fail"

        results['test_results'].append(test_case_result)
        savebundlefile("basic", results, timestring)

    def check_adb_status(self):
        # XXX: IP could be assigned in other way in the validation farm
        try:
            self.client.run_shell_command('netcfg %s dhcp' % \
                self.network_interface, response = TESTER_STR, timeout = 60)
        except:
            print "netcfg %s dhcp exception" % self.network_interface
            return False

        # Check network ip and setup adb connection
        ip_pattern = "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        cmd = "ifconfig %s" % self.network_interface
        self.client.proc.sendline(cmd)
        try:
            id = self.client.proc.expect([ip_pattern, pexpect.EOF], timeout = 5)
        except:
            return False
        if id == 0:
            match_group = self.client.proc.match.groups()
            if len(match_group) > 0:
                device_ip = match_group[0]
                adb_status, dev_name = self.client.check_android_adb_network_up(device_ip)
                if adb_status == True:
                    cmd = "adb -s %s shell echo 1" % dev_name
                    self.adb_proc = pexpect.spawn(cmd, timeout=5, logfile=sys.stdout)
                    id = self.adb_proc.expect(["1", "error"], timeout=5)
                    if id == 0:
                        return True
        return False
