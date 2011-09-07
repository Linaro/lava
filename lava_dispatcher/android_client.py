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

import pexpect
import sys
from lava_dispatcher.client import LavaClient, OperationFailed
from utils import string_to_list

class LavaAndroidClient(LavaClient):
    def __init__(self, machine_config, server_config):
        super(LavaAndroidClient, self).__init__(machine_config, server_config)
        self.board_class = \
            self.config.get("machine", "board_class") + ".Android"

    def run_adb_shell_command(self, dev_id, cmd, response, timeout=-1):
        adb_cmd = "adb -s %s shell %s" % (dev_id, cmd)
        try:
            adb_proc = pexpect.spawn(adb_cmd, logfile=sys.stdout)
            id = adb_proc.expect([response, pexpect.EOF], timeout=timeout)
            if id == 0:
                return True
        except pexpect.TIMEOUT:
            pass
        return False

    def in_test_shell(self):
        """ Check that we are in a shell on the test image
        """
        self.proc.sendline("")
        id = self.proc.expect([self.tester_str , pexpect.TIMEOUT])
        if id == 1:
            raise OperationFailed

    def boot_linaro_android_image(self):
        """ Reboot the system to the test android image
        """
        self.soft_reboot()
        try:
            self.enter_uboot()
        except:
            self.hard_reboot()
            self.enter_uboot()
        boot_cmds = string_to_list(self.config.get('boot_cmds_android'))
        self.proc.sendline(boot_cmds[0])
        for line in range(1, len(boot_cmds)):
            self.proc.expect("#")
            self.proc.sendline(boot_cmds[line])
        self.in_test_shell()
        self.proc.sendline("export PS1=\"root@linaro: \"")

    def android_logcat_clear(self):
        cmd = "logcat -c"
        self.proc.sendline(cmd)

    def _android_logcat_start(self):
        cmd = "logcat"
        self.proc.sendline(cmd)

    def android_logcat_monitor(self, pattern, timeout=-1):
        self.android_logcat_stop()
        cmd = 'logcat'
        self.proc.sendline(cmd)
        id = self.proc.expect(pattern, timeout=timeout)
        if id == 0:
            return True
        else:
            return False

    def android_logcat_stop(self):
        self.proc.sendcontrol('C')
        print "logcat cancelled"

    # adb cound be connected through network
    def android_adb_connect(self, dev_ip):
        pattern1 = "connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern2 = "already connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern3 = "unable to connect to"

        cmd = "adb connect %s" % dev_ip
        adb_proc = pexpect.spawn(cmd, timeout=300, logfile=sys.stdout)
        id = adb_proc.expect([pattern1, pattern2, pattern3, pexpect.EOF])
        if id == 0:
            dev_name = adb_proc.match.groups()[0]
            return True, dev_name
        else:
            return False, None

    def android_adb_disconnect(self, dev_ip):
        cmd = "adb disconnect %s" % dev_ip
        adb_proc = pexpect.run(cmd, timeout=300, logfile=sys.stdout)

    def check_adb_status(self):
        # XXX: IP could be assigned in other way in the validation farm
        network_interface = self.default_network_interface
        try:
            self.run_cmd_tester(
                'netcfg %s dhcp' % network_interface, timeout=60)
        except:
            print "netcfg %s dhcp exception" % network_interface
            return False

        # Check network ip and setup adb connection
        ip_pattern = "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        cmd = "ifconfig %s" % network_interface
        self.proc.sendline('')
        self.proc.sendline(cmd)
        try:
            id = self.proc.expect([ip_pattern, pexpect.EOF], timeout=60)
        except:
            print "ifconfig can not match ip pattern"
            return False
        if id == 0:
            match_group = self.proc.match.groups()
            if len(match_group) > 0:
                device_ip = match_group[0]
                adb_status, dev_name = self.android_adb_connect(device_ip)
                if adb_status == True:
                    print "dev_name = " + dev_name
                    result = self.run_adb_shell_command(dev_name, "echo 1", "1")
                    self.android_adb_disconnect(device_ip)
                    return result
        return False
