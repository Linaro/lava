# Copyright (C) 2013 Linaro Limited
#
# Author: Dave Pigott <dave.pigott@linaro.org>
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

import logging
from lava_dispatcher.device.master import (
    MasterImageTarget
)

class UEFITarget(MasterImageTarget):

    def __init__(self, context, config):
        super(UEFITarget, self).__init__(context, config)

    def _boot(self, boot_cmds):
        """

        :param boot_cmds:
        :raise:
        """
        try:
            self._soft_reboot()
            self._enter_uefi()
        except:
            logging.exception("_enter_uefi failed")
            self._hard_reboot()
            self._enter_uefi()
        self.proc.expect(self.config.bootloader_prompt, timeout=300)
        for line in range(0, len(boot_cmds)):
            try:
                action = boot_cmds[line].partition(" ")[0]
                command = boot_cmds[line].partition(" ")[2]
            except IndexError as e:
                raise Exception("Badly formatted command in boot_cmds %s" % e)
            logging.debug("Action: {0}; Command: {1}".format(action, command))
            if action == "sendline":
                self.proc.sendline(command)
            elif action == "expect":
                self.proc.expect(command, timeout=300)
            else:
                raise Exception("Unrecognised action in boot_cmds")

    def _enter_uefi(self):
        if self.proc.expect(self.config.interrupt_boot_prompt) != 0:
            raise Exception("Failed to enter uefi")
        self.proc.sendline(self.config.interrupt_boot_command)


target_class = UEFITarget