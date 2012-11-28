# Copyright (C) 2012 Linaro Limited
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

import subprocess
import pexpect
from time import sleep
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.downloader import (
    download_image
)
from lava_dispatcher.utils import (
        logging_spawn
)

class NexusTarget(Target):

    def __init__(self, context, config):
        super(NexusTarget, self).__init__(context, config)

    def deploy_android(self, boot, system, userdata):
        sdir = self.scratch_dir

        # TODO it seems boot, system and userdata are usually .tar.gz files,
        # and I am currently assuming they are .img and flashing them directly

        boot = download_image(boot, self.context, sdir, decompress=False)
        # FIXME uncomment these two - skipping them makes testing faster
        #system = download_image(system, self.context, sdir, decompress=False)
        #userdata = download_image(userdata, self.context, sdir, decompress=False)

        self.reboot()
        sleep(10)

        self.fastboot(['erase', 'boot'])
        # FIXME uncomment these two - skipping them makes testing faster
        #self.fastboot(['erase', 'system'])
        #self.fastboot(['erase', 'userdata'])

        # FIXME uncomment these two - skipping them makes testing faster
        #self.fastboot(['flash', 'system', system])
        #self.fastboot(['flash', 'userdata', userdata])

        self.deployment_data = Target.android_deployment_data
        self.deployment_data['boot_image'] = boot

    def power_on(self):
        self.fastboot(['reboot'])
        sleep(10) # wait for the bootloader to reboot
        self.fastboot(['boot', self.deployment_data['boot_image']])
        self.adb(['wait-for-device'])
        proc = self.adb(['shell'], spawn = True)
        proc.sendline("") # required to put the adb shell in a reasonable state
        proc.sendline("export PS1='%s'" % self.deployment_data['TESTER_PS1'])
        return proc

    def reboot(self):
        # tell android to reboot. A failure probably means that the device is not
        # booted on android, and we ignore that.
        self.adb(['reboot'], ignore_failure = True)

    # TODO implement power_off

    # TODO implement file_system

    # TODO implement extract_tarball

    # TODO implement get_device_version

    # TODO implement get_test_data_attachments (??)

    def adb(self, args, ignore_failure = False, spawn = False):
        cmd = ['sudo', 'adb'] + args
        if spawn:
            return logging_spawn(" ".join(cmd), timeout = 60)
        else:
            self._call(cmd, ignore_failure)

    def fastboot(self, args, ignore_failure = False):
        self._call(['sudo', 'fastboot'] + args, ignore_failure)

    def _call(self, cmd, ignore_failure):
        if ignore_failure:
            subprocess.call(cmd)
        else:
            subprocess.check_call(cmd)

target_class = NexusTarget
