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

from lava_dispatcher.device.master import MasterImageTarget

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

    def _mcc_setup(self):
        # TODO stop autoboot, put the UEFI inside the USBMSD
        pass

    def _enter_bootloader(self):
        self._mcc_setup()
        super(VexpressTarget, self)._enter_bootloader()

    def _wait_for_master_boot(self):
        self._mcc_setup()
        super(VexpressTarget, self)._wait_for_master_boot()

target_class = VexpressTarget
