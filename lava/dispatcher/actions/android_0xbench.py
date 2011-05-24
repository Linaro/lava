#!/usr/bin/python
from lava.dispatcher.actions import BaseAndroidAction
#from lava.dispatcher.client import OperationFailed
#from lava.dispatcher.android_config import TESTER_STR
import time
import pexpect
#import sys
#from datetime import datetime
#from lava.dispatcher.android_util import savebundlefile

class cmd_test_android_0xbench(BaseAndroidAction):
    def run(self):
        #Make sure in test image now
        self.client.in_test_shell()
        time.sleep(30)
        if not self.check_sys_bootup():
            # TODO: Fetch the logcat message as attached
            print "0xbench Test: sys bootup fail, aborted"
            return

        self.client.android_logcat_clear()

        package_name = 'org.zeroxlab.benchmark'
        class_name = 'org.zeroxlab.benchmark.Benchmark'
        cmd = 'am start -n %s/%s --ez math true --ez 2d true --ez 3d true \
            --ez vm true --ez autorun true' % (package_name, class_name)
        self.client.run_shell_command(cmd)

        # Do the logcat and monitor the log to know 0xbench done the test
        pattern = "Displayed org.zeroxlab.benchmark/.Report"
        try:
            self.client.android_logcat_monitor(pattern, timeout = 1200)
        except pexpect.TIMEOUT:
            print "0xbench Test: TIMEOUT Fail"

        self.client.android_logcat_stop()
