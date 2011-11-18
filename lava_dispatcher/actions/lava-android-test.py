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

import sys
import pexpect
import time
import logging
from datetime import datetime
from lava_dispatcher.actions import BaseAction
from lava_dispatcher.client import OperationFailed, NetworkError

class AndroidTestAction(BaseAction):

    def wait_devices_attached(self, dev_name):
        for count in range(3):
            if self.check_device_state(dev_name):
                return
            time.sleep(1)

        raise NetworkError("The android device(%s) isn't attached" % self.client.hostname)

    def check_device_state(self, dev_name):
        (output, rc) = pexpect.run('adb devices', timeout=None, logfile=sys.stdout, withexitstatus=True)
        if rc != 0:
            return False
        expect_line = '%s\tdevice' % dev_name
        for line in output.splitlines():
            if line.strip() == expect_line:
                return True
        return False

    def check_lava_android_test_installed(self):
        rc = pexpect.run('which lava-android-test', timeout=None, logfile=sys.stdout, withexitstatus=True)[1]
        if rc != 0:
            raise OperationFailed('lava-android-test has not been installed')

    def is_ready_for_test(self):
        self.check_lava_android_test_installed()
        dev_name = self.client.android_adb_connect_over_default_nic_ip()
        if dev_name is None:
            raise NetworkError("The android device(%s) isn't attached over tcpip" % self.client.hostname)

        self.wait_devices_attached(dev_name)
        self.client.wait_home_screen()
        return dev_name

class cmd_lava_android_test_run(AndroidTestAction):

    def test_name(self, test_name, timeout=-1):
        return super(cmd_lava_android_test_run, self).test_name() + \
               ' (%s)' % test_name

    def run(self, test_name, timeout=-1):
        #Make sure in test image now
        dev_name = self.is_ready_for_test()
        bundle_name = test_name + "-" + datetime.now().strftime("%H%M%S")
        cmd = 'lava-android-test run %s -s %s -o %s/%s.bundle' % (
                test_name, dev_name, self.context.host_result_dir, bundle_name)

        logging.info("Execute command on host: %s" % cmd)
        rc = pexpect.run(cmd, timeout=None, logfile=sys.stdout, withexitstatus=True)[1]
        if rc != 0:
            raise OperationFailed("Failed to run test case(%s) on device(%s) with return value: %s" % (test_name, dev_name, rc))

class cmd_lava_android_test_install(AndroidTestAction):
    """
    lava-test deployment to test image rootfs by chroot
    """
    def run(self, tests, option=None, timeout=2400):
        dev_name = self.is_ready_for_test()
        for test in tests:
            cmd = 'lava-android-test install %s -s %s' % (test, dev_name)
            if option is not None:
                cmd += ' -o ' + option
            logging.info("Execute command on host: %s" % cmd)
            rc = pexpect.run(cmd, timeout=None, logfile=sys.stdout, withexitstatus=True)[1]
            if rc != 0:
                raise OperationFailed("Failed to install test case(%s) on device(%s) with return value: %s" % (test, dev_name, rc))

