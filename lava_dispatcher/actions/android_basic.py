#!/usr/bin/python

# Copyright (C) 2011 Linaro Limited
#
# Author: Linaro Validation Team <linaro-dev@lists.linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

from lava_dispatcher.actions import BaseAction
import time
import pexpect
import logging
from datetime import datetime
from lava_dispatcher.android_util import savebundlefile

class cmd_test_android_monkey(BaseAction):
    def run(self):
        #Make sure in test image now
        self.client.in_test_shell()
        time.sleep(30)
        if not self.client.check_sys_bootup():
            # TODO: Fetch the logcat message as attachment
            logging.warning("monkey run test skipped: sys bootup fail")
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
        savebundlefile("monkey", results, timestring, self.context.lava_result_dir)
        self.client.proc.sendline("")


class cmd_test_android_basic(BaseAction):
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
            logging.exception("getprop sys.boot_completed failed")
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

        adb_status = self.client.check_adb_status()
        test_case_result = {}
        test_case_result['test_case_id'] = "adb connection status"
        if adb_status:
            test_case_result['result'] = "pass"
        else:
            test_case_result['result'] = "fail"

        results['test_results'].append(test_case_result)
        savebundlefile("basic", results, timestring, self.context.lava_result_dir)
        self.client.proc.sendline("")
