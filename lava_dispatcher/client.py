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
from utils import string_to_list

class LavaClient(object):
    def __init__(self, machine_config, server_config):
        self.config = machine_config
        self.server_config = server_config
        self.board_class = self.config.get("machine", "board_class")
        cmd = "conmux-console %s" % self.hostname
        self.sio = SerialIO(sys.stdout)
        self.proc = pexpect.spawn(cmd, timeout=3600, logfile=self.sio)
        #serial can be slow, races do funny things if you don't increase delay
        self.proc.delaybeforesend=1

    @property
    def master_str(self):
        if self.config.has_option("machine", "MASTER_STR"):
            return self.config.get("machine", "MASTER_STR")
        else:
            return self.server_config.get("server", "MASTER_STR")
    
    @property
    def tester_str(self):
        if self.config.has_option("machine", "TESTER_STR"):
            return self.config.get("machine", "TESTER_STR")
        else:
            return self.server_config.get("server", "TESTER_STR") 

    @property
    def uboot_cmds(self):
        uboot_str = self.config.get(self.board_class, "uboot_cmds")
        return string_to_list(uboot_str)

    @property
    def board_type(self):
        return self.config.get(self.board_class, "board_type")
    
    @property
    def boot_part(self):
        return self.config.getint(self.board_class, "boot_part")
    
    @property
    def root_part(self):
        return self.config.getint(self.board_class, "root_part")    

    @property
    def hostname(self):
        return self.config.get("machine", "hostname")

    def in_master_shell(self):
        """ Check that we are in a shell on the master image
        """
        self.proc.sendline("")
        id = self.proc.expect([self.master_str, pexpect.TIMEOUT])
        if id == 1:
            raise OperationFailed

    def in_test_shell(self):
        """ Check that we are in a shell on the test image
        """
        self.proc.sendline("")
        id = self.proc.expect([self.tester_str, pexpect.TIMEOUT])
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

    def boot_linaro_image(self):
        """ Reboot the system to the test image
        """
        self.soft_reboot()
        try:
            self.enter_uboot()
        except:
            self.hard_reboot()
            self.enter_uboot()
        uboot_cmds = self.uboot_cmds
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

    def enter_uboot(self):
        self.proc.expect("Hit any key to stop autoboot")
        self.proc.sendline("")

    def soft_reboot(self):
        self.proc.sendline("reboot")

    def hard_reboot(self):
        self.proc.send("~$")
        self.proc.sendline("hardreset")

    def run_shell_command(self, cmd, response=None, timeout=-1):
        self.proc.sendline(cmd)
        if response:
            self.proc.expect(response, timeout=timeout)

    def check_network_up(self):
        lava_server_ip = self.server_config.get("server", "LAVA_SERVER_IP")
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

    def export_display(self):
        #export the display, ignore errors on non-graphical images
        self.run_shell_command("su - linaro -c 'DISPLAY=:0 xhost local:'",
            response=self.tester_str)
        self.run_shell_command("export DISPLAY=:0", response=self.tester_str)

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

