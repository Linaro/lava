# Copyright (C) 2013 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
# Derived From: dummy.py
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

import contextlib
import logging
import time
import os

from lava_dispatcher.device.target import Target
from lava_dispatcher.client.base import NetworkCommandRunner
from lava_dispatcher import deployment_data
import lava_dispatcher.device.jtag_drivers as jtags
from lava_dispatcher.errors import (
    CriticalError,
)
from lava_dispatcher.utils import (
    ensure_directory
)


class JtagTarget(Target):

    def __init__(self, context, config):
        super(JtagTarget, self).__init__(context, config)
        self.proc = None
        self._booted = False
        self._boot_tags = None
        self._default_boot_cmds = None

        driver = self.config.jtag_driver
        if driver is None:
            raise CriticalError(
                "Required configuration entry missing: jtag_driver")

        driver_class = jtags.__getattribute__(driver)

        self.driver = driver_class(self)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs, image, bootloader, firmware, bl0, bl1,
                             bl2, bl31, rootfstype, bootloadertype, target_type, qemu_pflash=None):
        # Get deployment data
        self.deployment_data = deployment_data.get(target_type)
        self._boot_tags, self._default_boot_cmds = \
            self.driver.deploy_linaro_kernel(kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs, image, bootloader, firmware,
                                             bl0, bl1, bl2, bl31, rootfstype, bootloadertype, target_type,
                                             self.scratch_dir, qemu_pflash=qemu_pflash)

    def power_on(self):
        self._boot_cmds = self._load_boot_cmds(default=self._default_boot_cmds,
                                               boot_tags=self._boot_tags)
        if self.proc is not None:
            logging.warning('Device already powered on, powering off first')
            self.power_off(self.proc)
            self.proc = None
        self.proc = self.driver.connect(self._boot_cmds)
        self._auto_login(self.proc)
        self._wait_for_prompt(self.proc, self.config.test_image_prompts,
                              self.config.boot_linaro_timeout)
        self.proc.sendline("")
        self.proc.sendline('export PS1="%s"' % self.tester_ps1,
                           send_char=self.config.send_char)
        self._booted = True
        return self.proc

    def power_off(self, proc):
        super(JtagTarget, self).power_off(proc)
        if self.config.power_off_cmd:
            self.context.run_command(self.config.power_off_cmd)
        self.driver.finalize(proc)

    @contextlib.contextmanager
    def file_system(self, partition, directory):

        # If we are using NFS
        if '{NFSROOTFS}' in self._boot_tags:
            path = self._boot_tags['{NFSROOTFS}'] + directory
            logging.info("NFSROOTFS=%s", path)
            ensure_directory(path)
            yield path
        else:
            if not self._booted:
                self.context.client.boot_linaro_image()
            pat = self.tester_ps1_pattern
            incrc = self.tester_ps1_includes_rc
            runner = NetworkCommandRunner(self, pat, incrc)
            with self._busybox_file_system(runner, directory) as path:
                yield path


target_class = JtagTarget
