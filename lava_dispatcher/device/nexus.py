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
import logging
import contextlib

from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.downloader import (
    download_image
)
from lava_dispatcher.utils import (
    logging_system,
    logging_spawn,
    mkdtemp
)
from lava_dispatcher.errors import (
    CriticalError
)

class NexusTarget(Target):

    def __init__(self, context, config):
        super(NexusTarget, self).__init__(context, config)

        if not config.hard_reset_command:
            logging.warn(
                "Setting the hard_reset_command config option "
                "is highly recommended!"
            )

        self._booted = False
        self._working_dir = None

    def deploy_android(self, boot, system, userdata):

        boot = self._get_image(boot)
        system = self._get_image(system)
        userdata = self._get_image(userdata)

        self._enter_fastboot()
        self._fastboot('erase boot')
        self._fastboot('flash system %s' % system)
        self._fastboot('flash userdata %s' % userdata)

        self.deployment_data = Target.android_deployment_data
        self.deployment_data['boot_image'] = boot

    def power_on(self):
        if not self.deployment_data.get('boot_image', False):
            raise CriticalError('Deploy action must be run first')

        self._enter_fastboot()
        self._boot_test_image()

        self._booted = True
        proc = self._adb('shell', spawn = True)
        proc.sendline("") # required to put the adb shell in a reasonable state
        proc.sendline("export PS1='%s'" % self.deployment_data['TESTER_PS1'])
        self._runner = self._get_runner(proc)

        return proc

    def power_off(self, proc):
        # We always leave the device on
        pass

    @contextlib.contextmanager
    def file_system(self, partition, directory):

        if not self._booted:
            self.power_on()

        mount_point = self._get_partition_mount_point(partition)

        host_dir = '%s/mnt/%s' % (self.working_dir, directory)
        target_dir = '%s/%s' % (mount_point, directory)

        subprocess.check_call(['mkdir', '-p', host_dir])
        self._adb('pull %s %s' % (target_dir, host_dir), ignore_failure = True)

        yield host_dir

        self._adb('push %s %s' % (host_dir, target_dir))

    def get_device_version(self):
        # this is tricky, because fastboot does not have a visible version
        # number. For now let's use just the adb version number.
        return subprocess.check_output(
            "%s version | sed 's/.* version //'" % self.config.adb_command,
            shell = True
        ).strip()

    # start of private methods

    def _enter_fastboot(self):
        if self._already_on_fastboot():
            logging.debug("Device is on fastboot - no need to hard reset")
            return
        try:
            # First we try a gentle reset
            self._adb('reboot')
        except subprocess.CalledProcessError:
            # Now a more brute force attempt. In this case the device is
            # probably hung.
            if self.config.hard_reset_command:
                logging.debug("Will hard reset the device")
                logging_system(self.config.hard_reset_command)
            else:
                logging.critical(
                    "Hard reset command not configured. "
                    "Please reset the device manually."
                )

    def _already_on_fastboot(self):
        try:
            self._fastboot('getvar all', timeout = 2)
            return True
        except subprocess.CalledProcessError:
            return False

    def _boot_test_image(self):
        # We need an extra bootloader reboot before actually booting the image
        # to avoid the phone entering charging mode and getting stuck.
        self._fastboot('reboot')
        # specifically after `fastboot reset`, we have to wait a little
        sleep(10)
        self._fastboot('boot %s' % self.deployment_data['boot_image'])
        self._adb('wait-for-device')

    def _get_partition_mount_point(self, partition):
        lookup = {
            self.config.data_part_android_org: '/data',
            self.config.sys_part_android_org: '/system',
        }
        return lookup[partition]

    def _adb(self, args, ignore_failure = False, spawn = False, timeout = 600):
        cmd = self.config.adb_command + ' ' + args
        if spawn:
            return logging_spawn(cmd, timeout = 60)
        else:
            self._call(cmd, ignore_failure, timeout)

    def _fastboot(self, args, ignore_failure = False, timeout = 600):
        self._call(self.config.fastboot_command + ' ' + args, ignore_failure, timeout)

    def _call(self, cmd, ignore_failure, timeout):
        cmd = 'timeout ' + str(timeout) + 's ' + cmd
        logging.debug("Running on the host: %s" % cmd)
        if ignore_failure:
            subprocess.call(cmd, shell = True)
        else:
            subprocess.check_call(cmd, shell = True)

    def _get_image(self, url):
        sdir = self.working_dir
        image = download_image(url, self.context, sdir, decompress=False)
        return image

    @property
    def working_dir(self):
        if (self.config.nexus_working_directory is None or
            self.config.nexus_working_directory.strip() == ''):
            return self.scratch_dir

        if self._working_dir is None:
            self._working_dir = mkdtemp(self.config.nexus_working_directory)
        return self._working_dir


target_class = NexusTarget
