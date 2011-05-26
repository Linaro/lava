#!/usr/bin/python
from lava.dispatcher.actions import BaseAndroidAction
from lava.dispatcher.client import OperationFailed
from lava.dispatcher.android_config import TESTER_STR
import time
import pexpect
import sys
from datetime import datetime
from lava.dispatcher.android_util import savebundlefile

class cmd_test_android_monkey(BaseAndroidAction):
    def run(self):
        #Make sure in test image now
        self.client.in_test_shell()
        time.sleep(30)
        if not self.check_sys_bootup():
            # TODO: Fetch the logcat message as attachment
            print "monkey run test skipped: sys bootup fail"
            return

        TIMEFORMAT = '%Y-%m-%dT%H:%M:%SZ'
        starttime = datetime.utcnow()
        timestring = datetime.strftime(starttime, TIMEFORMAT)
        results = {'test_results':[]}

        result_pattern = '## Network stats: elapsed time=(?P<measurement>\d+)ms'
        test_case_result = {}
        test_case_result['test_case_id'] = "monkey-1"
        test_case_result['units'] = "mseconds"
        cmd = 'monkey -s 1 --pct-touch 10 --pct-motion 20 --pct-nav 20 --pct-majornav 30 --pct-appswitch 20 --throttle 500 50'
        self.client.proc.sendline(cmd)
        try:
            id = self.client.proc.expect([result_pattern, pexpect.EOF], timeout = 60)
            if id == 0:
                match_group = self.client.proc.match.groups()
                test_case_result['measurement'] = int(match_group[0])
                test_case_result['result'] = "pass"
            else:
                test_case_result['result'] = "fail"
        except pexpect.TIMEOUT: 
            test_case_result['result'] = "fail"

        results['test_results'].append(test_case_result)
        savebundlefile("monkey", results, timestring)
        self.client.proc.sendline("")


class cmd_test_android_basic(BaseAndroidAction):
    def run(self):
        #Make sure in test image now
        self.client.in_test_shell()

        #TODO: Checking if sdcard is mounted by vold to replace sleep idle, or check the Home app status
        # Give time for Android system to boot up, then test
        time.sleep(60)
        TIMEFORMAT = '%Y-%m-%dT%H:%M:%SZ'
        starttime = datetime.utcnow()
        timestring = datetime.strftime(starttime, TIMEFORMAT)
        results = {'test_results':[]}

        # Check booting completeness
        # Transfer the result to launch-control json representation
        result_pattern = "([0-1])"
        test_case_result = {}
        test_case_result['test_case_id'] = "dev.bootcomplete"
        cmd = "getprop dev.bootcomplete"
        self.client.proc.sendline(cmd)
        id = self.client.proc.expect([result_pattern, pexpect.EOF], timeout = 5)
        if id == 0:
            match_group = self.client.proc.match.groups()
            test_case_result['measurement'] = int(match_group[0])
            if test_case_result['measurement'] == 1:
                test_case_result['result'] = "pass"
            else:
                test_case_result['result'] = "fail"
        else:
            test_case_result['measurement'] = ""
            test_case_result['result'] = "unknown"
        results['test_results'].append(test_case_result)

        test_case_result = {}
        test_case_result['test_case_id'] = "sys.boot_completed"
        cmd = "getprop sys.boot_completed"
        self.client.proc.sendline(cmd)
        try:
            id = self.client.proc.expect([result_pattern, pexpect.EOF], timeout = 5)
            if id == 0:
                match_group = self.client.proc.match.groups()
                test_case_result['measurement'] = int(match_group[0])
                if test_case_result['measurement'] == 1:
                    test_case_result['result'] = "pass"
                else:
                    test_case_result['result'] = "fail"
            else:
                test_case_result['result'] = "unknown"
        except:
            test_case_result['result'] = "fail"
            pass

        results['test_results'].append(test_case_result)

        result_pattern = "(running)"
        test_case_result = {}
        test_case_result['test_case_id'] = "init.svc.adbd"
        cmd = "getprop init.svc.adbd"
        self.client.proc.sendline(cmd)
        id = self.client.proc.expect([result_pattern, pexpect.EOF], timeout = 5)
        if id == 0:
            match_group = self.client.proc.match.groups()
            test_case_result['message'] = match_group[0]
            if test_case_result['message'] == "running":
                test_case_result['result'] = "pass"
            else:
                test_case_result['result'] = "fail"
        else:
            test_case_result['result'] = "unknown"
        results['test_results'].append(test_case_result)

        #TODO: Wait for boot completed, if timeout, do logcat and save as booting fail log

        adb_status = self.check_adb_status()
        test_case_result = {}
        test_case_result['test_case_id'] = "adb connection status"
        if adb_status:
            test_case_result['result'] = "pass"
        else:
            test_case_result['result'] = "fail"

        results['test_results'].append(test_case_result)
        savebundlefile("basic", results, timestring)
        self.client.proc.sendline("")

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
        self.client.proc.sendline('')
        self.client.proc.sendline(cmd)
        try:
            id = self.client.proc.expect([ip_pattern, pexpect.EOF], timeout = 60)
        except:
            print "ifconfig can not match ip pattern"
            return False
        if id == 0:
            match_group = self.client.proc.match.groups()
            if len(match_group) > 0:
                device_ip = match_group[0]
                adb_status, dev_name = self.client.android_adb_connect(device_ip)
                if adb_status == True:
                    print "dev_name = " + dev_name
                    result = self.client.run_adb_shell_command(dev_name, "echo 1", "1")
                    self.client.android_adb_disconnect(device_ip)
                    return result
        return False
