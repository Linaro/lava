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

class cmd_test_android_0xbench(BaseAction):
    def run(self):
        #Make sure in test image now
        self.client.in_test_shell()
        time.sleep(30)
        if not self.client.check_sys_bootup():
            # TODO: Fetch the logcat message as attached
            logging.warning("0xbench Test: sys bootup fail, aborted")
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
            logging.warning("0xbench Test: TIMEOUT Fail")
            raise
        finally:
            self.client.android_logcat_stop()
