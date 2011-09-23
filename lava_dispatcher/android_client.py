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
import time
from lava_dispatcher.client import LavaClient, OperationFailed, NetworkError, GeneralError
import logging

from utils import string_to_list

class LavaAndroidClient(LavaClient):

    def run_adb_shell_command(self, dev_id, cmd, response, timeout= -1):
        adb_cmd = "adb -s %s shell %s" % (dev_id, cmd)
        try:
            adb_proc = pexpect.spawn(adb_cmd, logfile=sys.stdout)
            match_id = adb_proc.expect([response, pexpect.EOF], timeout=timeout)
            if match_id == 0:
                return True
        except pexpect.TIMEOUT:
            pass
        return False

    def in_test_shell(self):
        """ Check that we are in a shell on the test image
        """
        self.proc.sendline("")
        match_id = self.proc.expect([self.tester_str , pexpect.TIMEOUT])
        if match_id == 1:
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

        self.enable_adb_over_tcpip()
        self.android_adb_disconnect_over_default_nic_ip()

    def android_logcat_clear(self):
        cmd = "logcat -c"
        self.proc.sendline(cmd)

    def _android_logcat_start(self):
        cmd = "logcat"
        self.proc.sendline(cmd)

    def android_logcat_monitor(self, pattern, timeout= -1):
        self.android_logcat_stop()
        cmd = 'logcat'
        self.proc.sendline(cmd)
        match_id = self.proc.expect(pattern, timeout=timeout)
        if match_id == 0:
            return True
        else:
            return False

    def android_logcat_stop(self):
        self.proc.sendcontrol('C')
        logging.info("logcat cancelled")

    # adb cound be connected through network
    def android_adb_connect(self, dev_ip):
        pattern1 = "connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern2 = "already connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern3 = "unable to connect to"

        cmd = "adb connect %s" % dev_ip
        adb_proc = pexpect.spawn(cmd, timeout=300, logfile=sys.stdout)
        match_id = adb_proc.expect([pattern1, pattern2, pattern3, pexpect.EOF])
        if match_id == 0 or match_id == 1:
            dev_name = adb_proc.match.groups()[0]
            return dev_name
        else:
            return None

    def android_adb_disconnect(self, dev_ip):
        cmd = "adb disconnect %s" % dev_ip
        adb_proc = pexpect.run(cmd, timeout=300, logfile=sys.stdout)

    def check_adb_status(self):
        device_ip = self.get_default_nic_ip()
        if device_ip is not None:
            dev_name = self.android_adb_connect(device_ip)
            if dev_name is not None:
                logging.info("dev_name = " + dev_name)
                result = self.run_adb_shell_command(dev_name, "echo 1", "1")
                self.android_adb_disconnect(device_ip)
                return result
        return False

    def get_default_nic_ip(self):
        # XXX: IP could be assigned in other way in the validation farm
        network_interface = self.default_network_interface
        ip = None
        try:
            ip = self._get_default_nic_ip_by_ifconfig(network_interface)
        except:
            pass

        if ip is None:
            self.get_ip_via_dhcp(network_interface)
            ip = self._get_default_nic_ip_by_ifconfig(network_interface)
        return ip

    def _get_default_nic_ip_by_ifconfig(self, nic_name):
        # Check network ip and setup adb connection
        ip_pattern = "%s: ip (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) mask" % nic_name
        cmd = "ifconfig %s" % nic_name
        self.proc.sendline('')
        self.proc.sendline(cmd)
        match_id = 0
        try:
            match_id = self.proc.expect([ip_pattern, pexpect.EOF], timeout=60)
        except Exception as e:
            raise NetworkError("ifconfig can not match ip pattern for %s:%s" % (nic_name, e))

        if match_id == 0:
            match_group = self.proc.match.groups()
            if len(match_group) > 0:
                return match_group[0]
        return None

    def get_ip_via_dhcp(self, nic):
        try:
            self.run_cmd_tester('netcfg %s dhcp' % nic, timeout=60)
        except:
            raise NetworkError("netcfg %s dhcp exception" % nic)


    def android_adb_connect_over_default_nic_ip(self):
        dev_ip = self.get_default_nic_ip()
        if dev_ip is not None:
            return self.android_adb_connect(dev_ip)

    def android_adb_disconnect_over_default_nic_ip(self):
        dev_ip = self.get_default_nic_ip()
        if dev_ip is not None:
            self.android_adb_disconnect(dev_ip)

    def enable_adb_over_tcpip(self):
        self.proc.sendline('echo 0>/sys/class/android_usb/android0/enable')
        self.proc.sendline('setprop service.adb.tcp.port 5555')
        self.proc.sendline('stop adbd')
        self.proc.sendline('start adbd')

    def wait_home_screen(self):
        cmd = 'getprop init.svc.bootanim'
        for count in range(100):
            self.proc.sendline(cmd)
            match_id = self.proc.expect('stopped')
            if match_id == 0:
                return True
            time.sleep(1)
        raise GeneralError('The home screen does not displayed')

