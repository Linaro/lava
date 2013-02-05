# Copyright (C) 2013 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import pexpect

from lava_dispatcher.device.master import MasterImageTarget
from lava_dispatcher.errors import CriticalError

class VexpressTarget(MasterImageTarget):

    def _soft_reboot(self):
        """
        The Vexpress board only displays the prompt to interrupt the MCC when
        it is power-cycled, so we must always do a hard reset in practice.

        When a soft reboot is requested, though, at least we sync the disks
        before sending the hard reset.
        """
        # Try to C-c the running process, if any
        self.proc.sendcontrol('c')
        # Flush file system buffers
        self.proc.sendline('sync')

        self._hard_reboot()

    def _enter_bootloader(self):
        self._mcc_setup()
        super(VexpressTarget, self)._enter_bootloader()

    def _wait_for_master_boot(self):
        self._mcc_setup()
        super(VexpressTarget, self)._wait_for_master_boot()

    def _mcc_setup(self):
        self._enter_mcc()
        self._install_uefi_image()
        self._leave_mcc()

    def _enter_mcc(self):
        match_id = self.proc.expect([
            'Press Enter to stop auto boot...',
            pexpect.EOF, pexpect.TIMEOUT])
        if match_id != 0:
            msg = 'Unable to intercept MCC boot prompt'
            logging.error(msg)
            raise CriticalError(msg)
        self.proc.run("", ['Cmd>'])

    def _install_uefi_image(self):
        pass

    def _leave_mcc(self):
        self.proc.run("reboot")

target_class = VexpressTarget
