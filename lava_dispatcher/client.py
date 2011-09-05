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

from lava_dispatcher.config import (
    BOARDS,
    LAVA_SERVER_IP,
    MASTER_STR,
    TESTER_STR,
    )


class LavaClient(object):
    def __init__(self, hostname):
        cmd = "conmux-console %s" % hostname
        self.sio = SerialIO(sys.stdout)
        self.proc = pexpect.spawn(cmd, timeout=3600, logfile=self.sio)
        #serial can be slow, races do funny things if you don't increase delay
        self.proc.delaybeforesend=1
        self.hostname = hostname
        # will eventually come from the database
        self.board = BOARDS[hostname]

    def in_master_shell(self):
        """ Check that we are in a shell on the master image
        """
        self.proc.sendline("")
        id = self.proc.expect([MASTER_STR, pexpect.TIMEOUT])
        if id == 1:
            raise OperationFailed

    def in_test_shell(self):
        """ Check that we are in a shell on the test image
        """
        self.proc.sendline("")
        id = self.proc.expect([TESTER_STR, pexpect.TIMEOUT])
        if id == 1:
            raise OperationFailed

    def boot_master_image(self):
        """ reboot the system, and check that we are in a master shell
        """
        self.soft_reboot()
        try:
            self.proc.expect("Starting kernel")
            self.in_master_shell()
        except:
            self.hard_reboot()
            try:
                self.in_master_shell()
            except:
                raise
        self.proc.sendline('export PS1="[rc=$(echo \$?)] $PS1"')

    def boot_linaro_image(self):
        """ Reboot the system to the test image
        """
        self.soft_reboot()
        try:
            self.enter_uboot()
        except:
            self.hard_reboot()
            self.enter_uboot()
        uboot_cmds = self.board.uboot_cmds
        self.proc.sendline(uboot_cmds[0])
        for line in range(1, len(uboot_cmds)):
            if self.board.type in ["mx51evk", "mx53loco"]:
                self.proc.expect(">", timeout=300)
            elif self.board.type == "snowball_sd":
                self.proc.expect("\$", timeout=300)
            else:
                self.proc.expect("#", timeout=300)
            self.proc.sendline(uboot_cmds[line])
        self.in_test_shell()
        # set PS1 to include return value of last command
        # Details: system PS1 is set in /etc/bash.bashrc and user PS1 is set in
        # /root/.bashrc, it is
        # "${debian_chroot:+($debian_chroot)}\u@\h:\w\$ "
        self.proc.sendline('export PS1="[rc=$(echo \$?)] $PS1"')

    def enter_uboot(self):
        self.proc.expect("Hit any key to stop autoboot")
        self.proc.sendline("")

    def soft_reboot(self):
        self.proc.sendline("reboot")

    def hard_reboot(self):
        self.proc.send("~$")
        self.proc.sendline("hardreset")

    def run_shell_command(self, cmd, response=None, timeout=-1):
        # return return-code if captured, else return None
        self.proc.sendline(cmd)
        #verify return value of last command, match one number at least
        #PS1 setting is in boot_linaro_image or boot_master_image
        pattern1 = "\[rc=(\d+\d?\d?)\]"
        id = self.proc.expect([pattern1], timeout=timeout)
        if id == 0:
            rc = int(self.proc.match.groups()[0])
        else:
            rc = None
        if response:
            self.proc.expect(response, timeout=5)
        return rc

    def run_shell_command_without_rc(self, cmd, response=None, timeout=-1):
        self.proc.sendline(cmd)
        if response:
            self.proc.expect(response, timeout=timeout)

    def check_network_up(self):
        self.proc.sendline("LC_ALL=C ping -W4 -c1 %s" % LAVA_SERVER_IP)
        id = self.proc.expect(["1 received", "0 received",
            "Network is unreachable"], timeout=5)
        self.proc.expect(MASTER_STR)
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
        self.wait_network_up()
        #tty device uses minimal match, see pexpect wiki
        #pattern1 = ".*\n(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        pattern1 = "(\d+\d?\d?\.\d+\d?\d?\.\d+\d?\d?\.\d+\d?\d?)"
        cmd = ("ifconfig %s | grep 'inet addr' | awk -F: '{print $2}' |"
                "awk '{print $1}'" % self.board.default_network_interface)
        self.proc.sendline(cmd)
        #if running from ipython, it needs another Enter, don't know why:
        #self.proc.sendline("")
        id = self.proc.expect([pattern1, pexpect.EOF,
            pexpect.TIMEOUT], timeout=5)
        if id == 0:
            ip = self.proc.match.groups()[0]
            print "Master IP is %s" % ip
            return ip
        else:
            return None

    def export_display(self):
        #export the display, ignore errors on non-graphical images
        self.run_shell_command("su - linaro -c 'DISPLAY=:0 xhost local:'",
            response=TESTER_STR)
        self.run_shell_command("export DISPLAY=:0", response=TESTER_STR)

    def get_seriallog(self):
        return self.sio.getvalue()


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
    pass

