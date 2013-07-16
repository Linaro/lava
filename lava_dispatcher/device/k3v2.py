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

from time import sleep
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.device.fastboot import (
    FastbootTarget
)
from lava_dispatcher.utils import (
    connect_to_serial,
)
from lava_dispatcher.errors import (
    CriticalError,
)


class K3V2Target(FastbootTarget):

    def __init__(self, context, config):
        super(K3V2Target, self).__init__(context, config)

    def deploy_android(self, boot, system, userdata):

        boot = self._get_image(boot)
        system = self._get_image(system)
        userdata = self._get_image(userdata)

        self.fastboot.enter()
        # Need to sleep and wait for the first stage bootloaders to initialize.
        sleep(10)
        self.fastboot.flash('boot', boot)
        self.fastboot.flash('system', system)
        self.fastboot.flash('userdata', userdata)

        self.deployment_data = Target.android_deployment_data
        self.deployment_data['boot_image'] = boot

    def power_on(self):
        if not self.deployment_data.get('boot_image', False):
            raise CriticalError('Deploy action must be run first')

        # The k3v2 does not implement booting kernel from ram.
        # So instead we must flash the boot image, and reboot.
        self.fastboot.enter()
        self.fastboot('reboot')
        proc = connect_to_serial(self.context)
        proc.expect(self.context.device_config.master_str, timeout=300)

        # The k3v2 does not yet have adb support, so we do not wait for adb.
        #self._adb('wait-for-device')

        self._booted = True
        proc.sendline("")  # required to put the adb shell in a reasonable state
        proc.sendline("export PS1='%s'" % self.deployment_data['TESTER_PS1'])
        self._runner = self._get_runner(proc)

        return proc

target_class = K3V2Target
