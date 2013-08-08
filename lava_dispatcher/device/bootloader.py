# Copyright (C) 2013 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
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
import contextlib
import time
import os
import pexpect

from lava_dispatcher.device.master import (
    MasterImageTarget
)
from lava_dispatcher.utils import (
    string_to_list
)
from lava_dispatcher.errors import (
    CriticalError
)
from lava_dispatcher.downloader import (
    download_image
)

class BootloaderTarget(MasterImageTarget):

    def __init__(self, context, config):
        super(BootloaderTarget, self).__init__(context, config)
        self._booted = False
        self._boot_cmds = None
        self._uboot_boot = False
        # This is the offset into the path, used to reference bootfiles
        self._offset = self.scratch_dir.index('images')

    def power_off(self, proc):
        if self._uboot_boot:
            if self.config.power_off_cmd:
                self.context.run_command(self.config.power_off_cmd)
        else:
            super(BootloaderTarget, self).power_off(proc)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, rootfs, bootloader):
         if bootloader == "u_boot":
             # We assume we will be controlling u-boot
             if kernel is not None:
                 # We have been passed kernel image, setup TFTP boot
                 self._uboot_boot = True
                 # Set the TFTP server IP (Dispatcher)
                 self._boot_cmds = "lava_server_ip=" + self.context.config.lava_server_ip + ","
                 kernel = download_image(kernel, self.context, self.scratch_dir, decompress=False)
                 # Set the TFTP bootfile path for the kernel
                 self._boot_cmds += "lava_kernel=" + kernel[self._offset::] + ","
                 if ramdisk is not None:
                     # We have been passed a ramdisk
                     ramdisk = download_image(ramdisk, self.context, self.scratch_dir, decompress=False)
                     # Set the TFTP bootfile path for the ramdisk
                     self._boot_cmds += "lava_ramdisk=" + ramdisk[self._offset::] + ","
                 if dtb is not None:
                     # We have been passed a device tree blob
                     dtb = download_image(dtb, self.context, self.scratch_dir, decompress=False)
                     # Set the bootfile path for the ramdisk
                     self._boot_cmds += "lava_dtb=" + dtb[self._offset::] + ","
                 if rootfs is not None:
                     # We have been passed a rootfs
                     rootfs = download_image(rootfs, self.context, self.scratch_dir, decompress=True)
                     self._boot_cmds += "lava_rootfs=" + dtb[self._offset::] + ","
                 else:
                     # TODO: Faking the deployment data - Ubuntu
                     self.deployment_data = self.target_map['ubuntu']
             else:
                 # This *should* never happen
                 raise CriticalError("No kernel images to boot")
         else:
             # Define other "types" of bootloaders here. UEFI? Grub?
             raise CriticalError("U-Boot is the only supported bootloader at this time")

    def _inject_boot_cmds(self):
        if isinstance(self.config.boot_cmds, basestring):
            if self.config.boot_cmds_tftp is None:
                raise CriticalError("No TFTP boot commands defined")
            else:
                self._boot_cmds = self._boot_cmds + self.config.boot_cmds_tftp
        else:
            self._boot_cmds = string_to_list(self._boot_cmds.encode('ascii')) + self.config.boot_cmds

    def _run_boot(self):
        self._enter_bootloader()
        self._inject_boot_cmds()
        self._customize_bootloader(self.proc, self._boot_cmds)
        self._wait_for_prompt(self.proc, ['\(initramfs\)', self.config.master_str],
                        self.config.boot_linaro_timeout)

    def _boot_linaro_image(self):
        if self._uboot_boot:
            if self.config.hard_reset_command:
                self._hard_reboot()
            else:
                raise CriticalError("No hard reset command defined")               
            self._run_boot()
            self.proc.sendline('export PS1="%s"' % self.deployment_data['TESTER_PS1'])
            self._booted = True
        else:
            super(BootloaderTarget, self)._boot_linaro_image()

target_class = BootloaderTarget
