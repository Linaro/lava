# Copyright (C) 2013 Linaro Limited
#
# Author: Tyler Baker <Tyler.Baker@linaro.org>
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
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.device.fastboot import (
    FastbootTarget
)
from lava_dispatcher.utils import (
    connect_to_serial,
)

class CapriTarget(FastbootTarget):

    def __init__(self, context, config):
        super(CapriTarget, self).__init__(context, config)
        self.proc = connect_to_serial(self.context)

    def _soft_reboot(self):
        logging.info("Perform soft reboot the system")
        self.proc.sendcontrol('c')
        self.proc.sendline(self.config.soft_boot_cmd)
        match_id = self.proc.expect(
            [pexpect.TIMEOUT, 'Restarting system.',
             'The system is going down for reboot NOW',
             'Will now restart', 'U-Boot'], timeout=120)
        if match_id == 0:
            raise OperationFailed("Soft reboot failed")

    def _hard_reboot(self):
        logging.info("Perform hard reset on the system")
        if self.config.hard_reset_command != "":
            self.context.run_command(self.config.hard_reset_command)
        else:
            self.proc.send("~$")
            self.proc.sendline("hardreset")
            self.proc.empty_buffer()

    def _enter_bootloader(self):
        if self.proc.expect(self.config.interrupt_boot_prompt) != 0:
            raise Exception("Failed to enter bootloader")
        self.proc.sendline(self.config.interrupt_boot_command)

    def _enter_fastboot(self):
        if self.fastboot.on():
            logging.debug("Device is on fastboot - no need to hard reset")
            return
        try:
            self._soft_reboot()
            self._enter_bootloader()
        except:
            logging.exception("_enter_bootloader failed")
            self._hard_reboot()
            self._enter_bootloader()
        self.proc.sendline("fastboot")


    def deploy_android(self, boot, system, userdata):

        boot = self._get_image(boot)
        system = self._get_image(system)
        userdata = self._get_image(userdata)

        self._enter_fastboot()
        self.fastboot.flash('boot', boot)
        self.fastboot.flash('system', system)
        self.fastboot.flash('userdata', userdata)

        self.deployment_data = Target.ubuntu_deployment_data
        self.deployment_data['boot_image'] = boot

    def power_on(self):
        if not self.deployment_data.get('boot_image', False):
            raise CriticalError('Deploy action must be run first')

        self._enter_fastboot()
        self.fastboot('reboot')
        self.proc.expect(self.context.device_config.master_str,
                          timeout=300)

        # The capri does not yet have adb support, so we do not wait for adb.
        #self._adb('wait-for-device')

        self._booted = True
        self.proc.sendline("") # required to put the adb shell in a reasonable state
        self.proc.sendline("export PS1='%s'" % self.deployment_data['TESTER_PS1'])
        self._runner = self._get_runner(self.proc)

        return self.proc

target_class = CapriTarget
