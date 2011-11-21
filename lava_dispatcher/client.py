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
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import commands
import contextlib
import pexpect
import sys
import time
from cStringIO import StringIO
import traceback
from utils import string_to_list
import logging

from lava_dispatcher.connection import (
    LavaConmuxConnection,
    )


class CommandRunner(object):

    def __init__(self, connection, prompt_str, wait_for_rc=True):
        self._connection = connection
        self._prompt_str = prompt_str
        self._wait_for_rc = wait_for_rc
        self.rc = None

    def empty_pexpect_buffer(self):
        index = 0
        while index == 0:
            index = self._connection.expect(
                ['.+', pexpect.EOF, pexpect.TIMEOUT], timeout=1)

    def run(self, cmd, response=None, timeout=-1):
        self.empty_pexpect_buffer()
        self._connection.sendline(cmd)
        start = time.time()
        if response is not None:
            rv = self._connection.expect(response, timeout=timeout)
            self.match = self._connection.match
            timeout -= time.time() - start
        else:
            rv = None
            self.match = None
        self._connection.expect(self._prompt_str, timeout=timeout)
        if self._wait_for_rc:
            match_id = self._connection.expect(
                ['rc=(\d+\d?\d?)', pexpect.EOF, pexpect.TIMEOUT], timeout=2)
            if match_id == 0:
                self.rc = int(self._connection.match.groups()[0])
            else:
                self.rc = None
        return rv


class PrefixCommandRunner(CommandRunner):

    def __init__(self, prefix, connection, prompt_str):
        super(PrefixCommandRunner, self).__init__(connection, prompt_str)
        if not prefix.endswith(' '):
            prefix += ' '
        self._prefix = prefix

    def run(self, cmd, response=None, timeout=-1):
        super(PrefixCommandRunner, self).run(self._prefix + cmd)


class NetworkCommandRunner(CommandRunner):
    def __init__(self, client, prompt_str, wait_for_rc=True):
        CommandRunner.__init__(
            self, client.proc, prompt_str, wait_for_rc=wait_for_rc)
        self._client = client

    def _check_network_up(self):
        """
        Internal function for checking network one time
        """
        lava_server_ip = self._client.context.lava_server_ip
        match_id = self.run(
            "LC_ALL=C ping -W4 -c1 %s" % lava_server_ip,
            ["1 received", "0 received", "Network is unreachable"], timeout=5)
        if match_id == 0:
            return True
        else:
            return False

    def wait_network_up(self, timeout=300):
        now = time.time()
        while time.time() < now+timeout:
            if self._check_network_up():
                return
        raise NetworkError

    def get_master_ip(self):
        #get master image ip address
        try:
            self.wait_network_up()
        except:
            logging.warning(traceback.format_exc())
            return None
        #tty device uses minimal match, see pexpect wiki
        #pattern1 = ".*\n(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        pattern1 = "(\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?)"
        cmd = ("ifconfig %s | grep 'inet addr' | awk -F: '{print $2}' |"
                "awk '{print $1}'" % self._client.default_network_interface)
        match_id = self.run(
            cmd, [pattern1, pexpect.EOF, pexpect.TIMEOUT], timeout=5)
        logging.info("\nmatching pattern is %s" % match_id)
        if match_id == 0:
            ip = self.match.groups()[0]
            logging.info("Master IP is %s" % ip)
            return ip
        return None


class MasterCommandRunner(NetworkCommandRunner):
    def __init__(self, client):
        super(MasterCommandRunner, self).__init__(client, client.master_str)


class TesterCommandRunner(CommandRunner):

    def __init__(self, client, wait_for_rc=True):
        CommandRunner.__init__(
            self, client.proc, client.tester_str, wait_for_rc)

    def export_display(self):
        self.run("su - linaro -c 'DISPLAY=:0 xhost local:'")
        self.run("export DISPLAY=:0")


class AndroidTesterCommandRunner(NetworkCommandRunner):

    def __init__(self, client):
        super(AndroidTesterCommandRunner, self).__init__(
            client, client.tester_str, wait_for_rc=False)
        self.dev_name = None

    # adb cound be connected through network
    def android_adb_connect(self, dev_ip):
        pattern1 = "connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern2 = "already connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern3 = "unable to connect to"

        cmd = "adb connect %s" % dev_ip
        logging.info("Execute adb command on host: %s" % cmd)
        adb_proc = pexpect.spawn(cmd, timeout=300, logfile=sys.stdout)
        match_id = adb_proc.expect([pattern1, pattern2, pattern3, pexpect.EOF])
        if match_id in [0, 1]:
            self.dev_name = adb_proc.match.groups()[0]

    def android_adb_disconnect(self, dev_ip):
        cmd = "adb disconnect %s" % dev_ip
        logging.info("Execute adb command on host: %s" % cmd)
        pexpect.run(cmd, timeout=300, logfile=sys.stdout)

    def get_default_nic_ip(self):
        # XXX: IP could be assigned in other way in the validation farm
        network_interface = self._client.default_network_interface
        ip = None
        try:
            ip = self._get_default_nic_ip_by_ifconfig(network_interface)
        except:
            logging.exception("_get_default_nic_ip_by_ifconfig failed")
            pass

        if ip is None:
            self.get_ip_via_dhcp(network_interface)
            ip = self._get_default_nic_ip_by_ifconfig(network_interface)
        return ip

    def _get_default_nic_ip_by_ifconfig(self, nic_name):
        # Check network ip and setup adb connection
        try:
            self.wait_network_up()
        except:
            logging.warning(traceback.format_exc())
            return None
        ip_pattern = "%s: ip (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) mask" % nic_name
        match_id = 0
        try:
            match_id = self.run(
                "ifconfig %s" % nic_name, [ip_pattern, pexpect.EOF], timeout=60)
        except Exception as e:
            raise NetworkError("ifconfig can not match ip pattern for %s:%s" % (nic_name, e))

        if match_id == 0:
            match_group = self.match.groups()
            if len(match_group) > 0:
                return match_group[0]
        return None

    def get_ip_via_dhcp(self, nic):
        try:
            self.run('netcfg %s dhcp' % nic, timeout=60)
        except:
            logging.exception("netcfg %s dhcp failed" % nic)
            raise NetworkError("netcfg %s dhcp exception" % nic)

    def wait_until_attached(self):
        for count in range(3):
            if self.check_device_state():
                return
            time.sleep(1)

        raise NetworkError(
            "The android device(%s) isn't attached" % self._client.hostname)

    def check_device_state(self):
        (rc, output) = commands.getstatusoutput('adb devices')
        if rc != 0:
            return False
        expect_line = '%s\tdevice' % self.dev_name
        for line in output.splitlines():
            if line.strip() == expect_line:
                return True
        return False



class LavaClient(object):
    """
    LavaClient manipulates the target board, bootup, reset, power off the board,
    sends commands to board to execute
    """
    def __init__(self, context, config):
        self.context = context
        self.config = config
        self.sio = SerialIO(sys.stdout)
        if config.get('client_type') == 'conmux':
            self.proc = LavaConmuxConnection(config, self.sio)
        else:
            raise RuntimeError(
                "this version of lava-dispatcher only supports conmux "
                "clients, not %r" % config.get('client_type'))

    def device_option(self, option_name):
        return self.config.get(option_name)

    def device_option_int(self, option_name):
        return self.config.getint(option_name)

    @property
    def hostname(self):
        return self.device_option("hostname")

    @property
    def tester_str(self):
        return self.device_option("TESTER_STR")

    @property
    def master_str(self):
        return self.device_option("MASTER_STR")

    @property
    def boot_cmds(self):
        uboot_str = self.device_option("boot_cmds")
        return string_to_list(uboot_str)

    @property
    def device_type(self):
        return self.device_option("device_type")

    @property
    def boot_part(self):
        return self.device_option_int("boot_part")

    @property
    def root_part(self):
        return self.device_option_int("root_part")

    @property
    def default_network_interface(self):
        return self.device_option("default_network_interface")

    @property
    def lmc_dev_arg(self):
        return self.device_option("lmc_dev_arg")

    @contextlib.contextmanager
    def master_session(self):
        """A session that can be used to run commands in the master image.

        Anything that uses this will have to be done differently for images
        that are not deployed via a master image (e.g. using a JTAG to blow
        the image onto the card or testing under QEMU).
        """
        try:
            self.in_master_shell()
        except OperationFailed:
            self.boot_master_image()
        yield MasterCommandRunner(self)

    @contextlib.contextmanager
    def partition_session(self, partition):
        """A session that can be used to run commands in a given test
        partition.

        Anything that uses this will have to be done differently for images
        that are not deployed via a master image (e.g. using a JTAG to blow
        the image onto the card or testing under QEMU).
        """
        with self.master_session() as master_session:
            directory = '/mnt/' + partition
            master_session.run('mkdir -p %s' % directory)
            master_session.run('mount /dev/disk/by-label/%s %s' % (partition, directory))
            master_session.run(
                'cp -f %s/etc/resolv.conf %s/etc/resolv.conf.bak' % (
                    directory, directory))
            master_session.run('cp -L /etc/resolv.conf %s/etc' % directory)
            #eliminate warning: Can not write log, openpty() failed
            #                   (/dev/pts not mounted?), does not work
            master_session.run('mount --rbind /dev %s/dev' % directory)
            try:
                yield PrefixCommandRunner(
                    'chroot ' + directory, self.proc, self.master_str)
            finally:
                master_session.run(
                    'cp -f %s/etc/resolv.conf.bak %s/etc/resolv.conf' % (
                        directory, directory))
                cmd = ('cat /proc/mounts | awk \'{print $2}\' | grep "^%s/dev"'
                       '| sort -r | xargs umount' % directory)
                master_session.run(cmd)
                master_session.run('umount ' + directory)

    @contextlib.contextmanager
    def tester_session(self):
        try:
            self.in_test_shell()
        except OperationFailed:
            self.boot_linaro_image()
        yield TesterCommandRunner(self)

    @contextlib.contextmanager
    def android_tester_session(self):
        try:
            self.in_test_shell()
        except OperationFailed:
            self.boot_linaro_android_image()
        session = AndroidTesterCommandRunner(self)
        logging.info("adb connect over default network interface")
        dev_ip = session.get_default_nic_ip()
        if dev_ip is None:
            XXX
        session.android_adb_connect(dev_ip)
        session.wait_until_attached()
        try:
            yield session
        finally:
            session.android_adb_disconnect(dev_ip)

    def in_master_shell(self, timeout=10):
        """
        Check that we are in a shell on the master image
        """
        self.proc.sendline("")
        id = self.proc.expect([self.master_str, pexpect.TIMEOUT],
            timeout=timeout)
        if id == 1:
            raise OperationFailed
        logging.info("System is in master image now")

    def in_test_shell(self, timeout=10):
        """
        Check that we are in a shell on the test image
        """
        self.proc.sendline("")
        match_id = self.proc.expect([self.tester_str, pexpect.TIMEOUT],
                    timeout=timeout)
        if match_id == 1:
            raise OperationFailed
        logging.info("System is in test image now")

    def boot_master_image(self):
        """
        reboot the system, and check that we are in a master shell
        """
        self.proc.soft_reboot()
        try:
            self.proc.expect("Starting kernel")
            self.in_master_shell(120)
        except:
            logging.exception("in_master_shell failed")
            self.proc.hard_reboot()
            self.in_master_shell(300)
        self.proc.sendline('export PS1="$PS1 [rc=$(echo \$?)]: "')
        self.proc.expect(self.master_str, timeout=10)

    def boot_linaro_image(self):
        """
        Reboot the system to the test image
        """
        self.proc._boot(self.boot_cmds)
        self.in_test_shell(300)
        # set PS1 to include return value of last command
        # Details: system PS1 is set in /etc/bash.bashrc and user PS1 is set in
        # /root/.bashrc, it is
        # "${debian_chroot:+($debian_chroot)}\u@\h:\w\$ "
        self.proc.sendline('export PS1="$PS1 [rc=$(echo \$?)]: "')
        self.proc.expect(self.tester_str, timeout=10)

    def get_seriallog(self):
        return self.sio.getvalue()

    def empty_pexpect_buffer(self):
        index = 0
        while (index == 0):
            index = self.proc.expect (['.+', pexpect.EOF, pexpect.TIMEOUT], timeout=1)

    # Android stuff

    def boot_linaro_android_image(self):
        """Reboot the system to the test android image."""
        self.proc._boot(string_to_list(self.config.get('boot_cmds_android')))
        self.in_test_shell()
        self.proc.sendline("export PS1=\"root@linaro: \"")

        self.enable_adb_over_tcpip()

    def enable_adb_over_tcpip(self):
        logging.info("Enable adb over TCPIP")
        session = TesterCommandRunner(self, wait_for_rc=False)
        session.run('echo 0>/sys/class/android_usb/android0/enable')
        session.run('setprop service.adb.tcp.port 5555')
        session.run('stop adbd')
        session.run('start adbd')

    def wait_home_screen(self):
        cmd = 'getprop init.svc.bootanim'
        for count in range(100):
            self.proc.sendline(cmd)
            match_id = self.proc.expect('stopped')
            if match_id == 0:
                return True
            time.sleep(1)
        raise GeneralError('The home screen does not displayed')


class SerialIO(file):
    def __init__(self, logfile):
        self.serialio = StringIO()
        self.logfile = logfile

    def write(self, text):
        self.serialio.write(text)
        self.logfile.write(text)

    def close(self):
        self.serialio.close()
        self.logfile.close()

    def flush(self):
        self.logfile.flush()

    def getvalue(self):
        return self.serialio.getvalue()


class DispatcherError(Exception):
    """
    Base exception and error class for dispatcher
    """


class CriticalError(DispatcherError):
    """
    The critical error
    """


class GeneralError(DispatcherError):
    """
    The non-critical error
    """


class NetworkError(CriticalError):
    """
    This is used when a network error occurs, such as failing to bring up
    the network interface on the client
    """


class OperationFailed(GeneralError):
    """
    The exception throws when a file system or system operation fails.
    """
