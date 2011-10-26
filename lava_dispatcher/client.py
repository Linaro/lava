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

    def in_master_shell(self, timeout=10):
        """
        Check that we are in a shell on the master image
        """
        self.proc.sendline("")
        id = self.proc.expect([self.master_str, pexpect.TIMEOUT],
            timeout=timeout)
        if id == 1:
            raise OperationFailed

    def in_test_shell(self):
        """
        Check that we are in a shell on the test image
        """
        self.proc.sendline("")
        match_id = self.proc.expect([self.tester_str, pexpect.TIMEOUT])
        if match_id == 1:
            raise OperationFailed

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
        self.proc.expect(self.master_str)

    def boot_linaro_image(self):
        """
        Reboot the system to the test image
        """
        self.proc._boot(self.boot_cmds)
        self.in_test_shell()
        # set PS1 to include return value of last command
        # Details: system PS1 is set in /etc/bash.bashrc and user PS1 is set in
        # /root/.bashrc, it is
        # "${debian_chroot:+($debian_chroot)}\u@\h:\w\$ "
        self.proc.sendline('export PS1="$PS1 [rc=$(echo \$?)]: "')
        self.proc.expect(self.tester_str)

    def run_shell_command(self, cmd, response=None, timeout=-1):
        self.empty_pexpect_buffer()
        # return return-code if captured, else return None
        self.proc.sendline(cmd)
        start_time = time.time()
        if response:
            self.proc.expect(response, timeout=timeout)
            elapsed_time = int(time.time()-start_time)
            # if reponse is master/tester string, make rc expect timeout to be
            # 2 sec, else make it consume remained timeout
            if response in [self.master_str, self.tester_str]:
                timeout = 2
            else:
                timeout = int(timeout-elapsed_time)
        #verify return value of last command, match one number at least
        #PS1 setting is in boot_linaro_image or boot_master_image
        pattern1 = "rc=(\d+\d?\d?)"
        id = self.proc.expect([pattern1, pexpect.EOF, pexpect.TIMEOUT],
                timeout=timeout)
        if id == 0:
            rc = int(self.proc.match.groups()[0])
        else:
            rc = None
        return rc

    def run_cmd_master(self, cmd, timeout=-1):
        return self.run_shell_command(cmd, self.master_str, timeout)

    def run_cmd_tester(self, cmd, timeout=-1):
        return self.run_shell_command(cmd, self.tester_str, timeout)

    def check_network_up(self):
        lava_server_ip = self.context.lava_server_ip
        self.proc.sendline("LC_ALL=C ping -W4 -c1 %s" % lava_server_ip)
        id = self.proc.expect(["1 received", "0 received",
            "Network is unreachable"], timeout=5)
        self.proc.expect(self.master_str)
        if id == 0:
            return True
        else:
            return False

    def wait_network_up(self, timeout=120):
        now = time.time()
        while time.time() < now+timeout:
            if self.check_network_up():
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
                "awk '{print $1}'" % self.default_network_interface)
        self.proc.sendline(cmd)
        #if running from ipython, it needs another Enter, don't know why:
        #self.proc.sendline("")
        id = self.proc.expect([pattern1, pexpect.EOF,
            pexpect.TIMEOUT], timeout=5)
        logging.info("\nmatching pattern is %s" % id)
        if id == 0:
            ip = self.proc.match.groups()[0]
            logging.info("Master IP is %s" % ip)
            return ip
        else:
            return None

    def export_display(self):
        #export the display, ignore errors on non-graphical images
        self.run_cmd_tester("su - linaro -c 'DISPLAY=:0 xhost local:'")
        self.run_cmd_tester("export DISPLAY=:0")

    def get_seriallog(self):
        return self.sio.getvalue()

    def empty_pexpect_buffer(self):
        index = 0
        while (index == 0):
            index = self.proc.expect (['.+', pexpect.EOF, pexpect.TIMEOUT], timeout=1)

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
