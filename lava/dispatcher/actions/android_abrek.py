#!/usr/bin/python
from dispatcher.actions import BaseAndroidAction
from dispatcher.client import OperationFailed
from dispatcher.android_config import MASTER_STR, TESTER_STR
import sys

class cmd_test_android_abrek(BaseAndroidAction):
    def run(self, test_name, timeout=-1):
        cmd = 'abrek run %s -o /tmp/%s.bundle' % (test_name, test_name)
        abrek_proc = pexpect.spawn(cmd, logfile=sys.stdout)
        abrek_proc.expect("ABREK TEST RUN COMPLETE")
