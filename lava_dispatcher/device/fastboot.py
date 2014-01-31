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
from time import sleep
import logging
import contextlib

from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.downloader import (
    download_image
)
from lava_dispatcher.utils import (
    mkdtemp,
    finalize_process,
)
from lava_dispatcher.errors import (
    CriticalError
)
from lava_dispatcher import deployment_data


def _call(context, cmd, ignore_failure, timeout):
    cmd = 'timeout ' + str(timeout) + 's ' + cmd
    context.run_command(cmd, failok=ignore_failure)


class FastBoot(object):

    def __init__(self, device):
        self.device = device
        self.context = device.context

    def __call__(self, args, ignore_failure=False, timeout=600):
        command = self.device.config.fastboot_command + ' ' + args
        command = "flock /var/lock/lava-fastboot.lck " + command
        _call(self.context, command, ignore_failure, timeout)

    def enter(self):
        if self.on():
            logging.debug("Device is on fastboot - no need to hard reset")
            return
        try:
            # First we try a gentle reset
            self.device._adb(self.device.config.soft_boot_cmd)
        except subprocess.CalledProcessError:
            # Now a more brute force attempt. In this case the device is
            # probably hung.
            if self.device.config.hard_reset_command:
                logging.debug("Will hard reset the device")
                self.context.run_command(self.device.config.hard_reset_command)
            else:
                logging.critical(
                    "Hard reset command not configured. "
                    "Please reset the device manually."
                )

    def on(self):
        try:
            self('getvar all', timeout=2)
            return True
        except subprocess.CalledProcessError:
            return False

    def erase(self, partition):
        self('erase %s' % partition)

    def flash(self, partition, image):
        self('flash %s %s' % (partition, image))

    def boot(self, image):
        # We need an extra bootloader reboot before actually booting the image
        # to avoid the phone entering charging mode and getting stuck.
        self('reboot')
        # specifically after `fastboot reset`, we have to wait a little
        sleep(10)
        self('boot %s' % image)


class FastbootTarget(Target):

    def __init__(self, context, config):
        super(FastbootTarget, self).__init__(context, config)

        if not config.hard_reset_command:
            logging.warn(
                "Setting the hard_reset_command config option "
                "is highly recommended!"
            )

        self.proc = None
        self._booted = False
        self._working_dir = None
        self.fastboot = FastBoot(self)
        self.__boot_image__ = None

    def deploy_android(self, boot, system, userdata, rootfstype,
                       bootloadertype):

        boot = self._get_image(boot)
        system = self._get_image(system)
        userdata = self._get_image(userdata)

        self.fastboot.enter()
        self.fastboot.erase('boot')
        self.fastboot.flash('system', system)
        self.fastboot.flash('userdata', userdata)

        self.deployment_data = deployment_data.android
        self.__boot_image__ = boot

    def power_on(self):
        if self.__boot_image__ is None:
            raise CriticalError('Deploy action must be run first')

        if self.proc is not None:
            logging.warning('device already powered on, powering off first')
            self.power_off(None)

        self.fastboot.enter()
        self.fastboot.boot(self.__boot_image__)
        self._adb('wait-for-device')

        self._booted = True
        self.proc = self._adb('shell', spawn=True)
        self._auto_login(self.proc)
        self.proc.sendline("")  # required to put the adb shell in a reasonable state
        self.proc.sendline("export PS1='%s'" % self.tester_ps1)

        return self.proc

    def power_off(self, proc):
        if self.config.power_off_cmd:
            self.context.run_command(self.config.power_off_cmd)
        finalize_process(self.proc)
        self.proc = None

    @contextlib.contextmanager
    def file_system(self, partition, directory):

        if not self._booted:
            self.power_on()

        mount_point = self._get_partition_mount_point(partition)

        host_dir = '%s/mnt/%s' % (self.working_dir, directory)
        target_dir = '%s/%s' % (mount_point, directory)

        subprocess.check_call(['mkdir', '-p', host_dir])
        self._adb('pull %s %s' % (target_dir, host_dir), ignore_failure=True)

        yield host_dir

        self._adb('push %s %s' % (host_dir, target_dir))

    def get_device_version(self):
        # this is tricky, because fastboot does not have a visible version
        # number. For now let's use just the adb version number.
        return subprocess.check_output(
            "%s version | sed 's/.* version //'" % self.config.adb_command,
            shell=True
        ).strip()

    # start of private methods

    def _get_partition_mount_point(self, partition):
        lookup = {
            self.config.data_part_android_org: '/data',
            self.config.sys_part_android_org: '/system',
        }
        return lookup[partition]

    def _adb(self, args, ignore_failure=False, spawn=False, timeout=600):
        cmd = self.config.adb_command + ' ' + args
        if spawn:
            return self.context.spawn(cmd, timeout=60)
        else:
            _call(self.context, cmd, ignore_failure, timeout)

    def _get_image(self, url):
        sdir = self.working_dir
        image = download_image(url, self.context, sdir, decompress=False)
        return image

    @property
    def working_dir(self):
        if self.config.shared_working_directory is None or \
                self.config.shared_working_directory.strip() == '':
            return self.scratch_dir

        if self._working_dir is None:
            self._working_dir = mkdtemp(self.config.shared_working_directory)
        return self._working_dir


target_class = FastbootTarget
