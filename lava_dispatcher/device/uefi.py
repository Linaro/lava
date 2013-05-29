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
import re
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
            self._enter_bootloader()
        except:
            logging.exception("enter uefi failed")
            self._hard_reboot()
            self._enter_bootloader()
        self.proc.expect(self.config.bootloader_prompt, timeout=300)
        for line in range(0, len(boot_cmds)):
            parts = re.match('^(?P<action>sendline|expect)\s*(?P<command>.*)', line)
            try:
                action = parts.group('action')
                command = re.escape(parts.group('command'))
            except AttributeError as e:
                raise Exception("Badly formatted command in boot_cmds %s" % e)
            if action == "sendline":
                self.proc.send(command)
            elif action == "expect":
                self.proc.expect(command, timeout=300)
            else:
                raise Exception("Unrecognised action in boot_cmds")

target_class = UEFITarget
