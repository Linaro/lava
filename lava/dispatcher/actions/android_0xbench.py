#!/usr/bin/python
from lava.dispatcher.actions import BaseAndroidAction
from lava.dispatcher.client import OperationFailed
from lava.dispatcher.android_config import TESTER_STR
import time
import pexpect
import sys
from datetime import datetime
from lava.dispatcher.android_util import savebundlefile

class cmd_test_android_0xbench(BaseAndroidAction):
    def run(self):
        #Make sure in test image now
        self.client.in_test_shell()
        if not self.check_sys_bootup():
            print "0xbench Test: sys bootup fail, aborted"

        self.client.android_logcat_clear()

        package_name = 'org.zeroxlab.benchmark'
        class_name = 'org.zeroxlab.benchmark.Benchmark'
        cmd = 'am start -n %s/%s --ez math true --ez autorun true' % \
            (package_name, class_name)
        self.client.run_shell_command(cmd, response = TESTER_STR, timeout = 10)

        # Do the logcat and monitor the log
        pattern = "Displayed org.zeroxlab.benchmark/.Report"
        try:
            match = self.client.android_logcat_monitor(pattern, timeout = 60)
            if match:
                print "0xbench Test: Do save the result"
            else:
                print "0xbench Test: Fail to match"
        except pexpect.TIMEOUT:
            print "0xbench Test: TIMEOUT Fail"

        self.client.android_logcat_stop()
