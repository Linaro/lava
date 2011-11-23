# Copyright (C) 2011 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
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

import logging
import re
import time

import pexpect


class LavaConnection(object):

    def __init__(self, device_config, sio):
        self.device_config = device_config
        self.proc = self._make_connection(sio)

    def _make_connection(self, sio):
        raise NotImplementedError(self._make_connection)

    def device_option(self, option_name):
        return self.device_config.get(option_name)

    def device_option_int(self, option_name):
        return self.device_config.getint(option_name)


    # pexpect-like interface.

    def sendline(self, *args, **kw):
        return self.proc.sendline(*args, **kw)

    def expect(self, *args, **kw):
        return self.proc.expect(*args, **kw)

    def sendcontrol(self, *args, **kw):
        return self.proc.sendcontrol(*args, **kw)

    @property
    def match(self):
        return self.proc.match


    # Extra bits.

    def _enter_uboot(self):
        self.proc.expect("Hit any key to stop autoboot")
        self.proc.sendline("")

    def soft_reboot(self):
        self.proc.sendline("reboot")
        # set soft reboot timeout 120s, or do a hard reset
        logging.info("Rebooting the system")
        id = self.proc.expect(
            ['Restarting system.', 'The system is going down for reboot NOW',
                pexpect.TIMEOUT], timeout=120)
        if id not in [0,1]:
            self.hard_reboot()

    def hard_reboot(self):
        raise NotImplementedError(self.hard_reboot)


class LavaConmuxConnection(LavaConnection):

    def _make_connection(self, sio):
        cmd = "conmux-console %s" % self.device_option("hostname")
        proc = pexpect.spawn(cmd, timeout=1200, logfile=sio)
        #serial can be slow, races do funny things if you don't increase delay
        proc.delaybeforesend=1
        return proc

    def hard_reboot(self):
        logging.info("Perform hard reset on the system")
        self.proc.send("~$")
        self.proc.sendline("hardreset")
        # XXX Workaround for snowball
        if self.device_option('device_type') == "snowball_sd":
            time.sleep(10)
            self.in_master_shell(300)
            # Intentionally avoid self.soft_reboot() to prevent looping
            self.proc.sendline("reboot")
            self.enter_uboot()

    def _boot(self, boot_cmds):
        self.soft_reboot()
        try:
            self._enter_uboot()
        except:
            logging.exception("_enter_uboot failed")
            self.hard_reboot()
            self._enter_uboot()
        self.proc.sendline(boot_cmds[0])
        bootloader_prompt = re.escape(self.device_option('bootloader_prompt'))
        for line in range(1, len(boot_cmds)):
            self.proc.expect(bootloader_prompt, timeout=300)
            self.proc.sendline(boot_cmds[line])
