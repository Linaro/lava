#!/usr/bin/python

# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
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
from datetime import datetime
from lava_dispatcher.actions import BaseAction
from lava_dispatcher.client import OperationFailed, NetworkError

class AndroidTestAction(BaseAction):

    def wait_devices_attached(self, dev_name):
        count = 0
        while not self.check_device_state(dev_name):
            if count == 3:
                raise NetworkError("The android device(%s) isn't attached" % self.client.hostname)
            time.sleep(1)
            count = count + 1

    def check_device_state(self, dev_name):
        (output, rc) = pexpect.run('adb devices', timeout=None, logfile=sys.stdout, withexitstatus=True)
        if rc != 0:
            return False
        expect_line = '%s\tdevice' % dev_name
        for line in output.splitlines():
            if line.strip() == expect_line:
                return True
        return False

    def is_ready_for_test(self):
        (ret, dev_name) = self.client.android_adb_connect_over_default_nic_ip()
        if not ret:
            raise NetworkError("The android device(%s) isn't attached over tcpip" % self.client.hostname)

        self.wait_devices_attached(dev_name)
        self.client.wait_home_screen()
        return dev_name

class cmd_enable_adb_over_tcpip(AndroidTestAction):
    def run(self):
        self.client.enable_adb_over_tcpip()

class cmd_lava_android_test_run(AndroidTestAction):
    def run(self, test_name, timeout= -1):
        #Make sure in test image now
        dev_name = self.is_ready_for_test()
        bundle_name = test_name + "-" + datetime.now().strftime("%H%M%S")
        cmd = 'lava-android-test run %s -s %s -o /tmp/%s/%s.bundle' % (
                test_name, dev_name, self.context.lava_result_dir, bundle_name)

        rc = pexpect.run(cmd, timeout=None, logfile=sys.stdout, withexitstatus=True)[1]
        if rc != 0:
            raise OperationFailed("Failed to run test case(%s) on device(%s) with return value: %s" % (test_name, dev_name, rc))

class cmd_lava_android_test_install(AndroidTestAction):
    """
    lava-test deployment to test image rootfs by chroot
    """
    def run(self, tests, timeout=2400):
        dev_name = self.is_ready_for_test()
        for test in tests:
            cmd = 'lava-android-test install %s -s %s' % (test, dev_name)
            rc = pexpect.run(cmd, timeout=None, logfile=sys.stdout, withexitstatus=True)[1]
            if rc != 0:
                raise OperationFailed("Failed to install test case(%s) on device(%s) with return value: %s" % (test, dev_name, rc))

class cmd_install_lava_android_test(BaseAction):
    def run(self, timeout= -1):

        rc = pexpect.run('which lava-android-test', timeout=None, logfile=sys.stdout, withexitstatus=True)[1]
        if rc == 0:
            return
        else:
            raise OperationFailed('lava-android-test has not been installed')

#        cur_dir = os.getcwd()
#        tmp_dir = mkdtemp(prefix = 'lava_android_test', dir = '/tmp')
#        os.chmod(tmp_dir, 0755)
#        os.chdir(tmp_dir)
#        try:
#            rc = pexpect.run("bzr branch lp:~liuyq0307/lava-android-test/improve", timeout = None, logfile = sys.stdout, withexitstatus = True)[1]
#            if rc != 0:
#                raise OperationFailed("Failed to checkout branch of lava-android-test for install_lava_android_test: %d" % (rc))
#
#            os.chdir(os.path.join(tmp_dir, 'lava-android-test'))
#
#            rc = pexpect.run("python ./setup.py install develop --user", timeout = None, logfile = sys.stdout, withexitstatus = True)[1]
#            if rc != 0:
#                raise OperationFailed("Failed to install lava-android-test: %d" % (rc))
#        finally:
#            os.chdir(cur_dir)
#            shutil.rmtree(tmp_dir)

class cmd_adb_kill_server(BaseAction):

    def run(self, timeout= -1):

        kill_server = 'adb kill-server'
        rc = pexpect.run(kill_server, timeout=None, logfile=sys.stdout, withexitstatus=True)[1]
        if rc == 0:
            return
        else:
            raise OperationFailed("Failed to excute command(%s):%d" % (kill_server, rc))
