# Copyright (C) 2011 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
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
import subprocess
import re

from lava_dispatcher import deployment_data
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.client.lmc_utils import (
    generate_image,
    image_partition_mounted,
)
from lava_dispatcher.downloader import (
    download_image,
)
from lava_dispatcher.utils import (
    ensure_directory,
    extract_tar,
    finalize_process,
    extract_ramdisk,
    extract_modules,
    create_ramdisk
)
from lava_dispatcher.errors import (
    CriticalError
)


class QEMUTarget(Target):

    def __init__(self, context, config):
        super(QEMUTarget, self).__init__(context, config)
        self.proc = None
        self._qemu_options = None
        self._sd_image = None
        self._kernel = None
        self._ramdisk = None
        self._dtb = None
        self._firmware = None
        self._is_kernel_present = False

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, modules, rootfs, nfsrootfs,
                             bootloader, firmware, bl1, bl2, bl31, rootfstype,
                             bootloadertype, target_type):
        # Check for errors
        if rootfs is None and ramdisk is None:
            raise CriticalError("You must specify a QEMU file system image or ramdisk")
        if kernel is None:
            raise CriticalError("No kernel images to boot")

        if rootfs:
            self._sd_image = download_image(rootfs, self.context)
            self.customize_image(self._sd_image)

        self._kernel = download_image(kernel, self.context)

        if ramdisk is not None:
            ramdisk = download_image(ramdisk, self.context)
            if modules is not None:
                modules = download_image(modules, self.context,
                                         self._scratch_dir,
                                         decompress=False)
                ramdisk_dir = extract_ramdisk(ramdisk, self._scratch_dir,
                                              is_uboot=self._is_uboot_ramdisk(ramdisk))
                extract_modules(modules, ramdisk_dir)
                ramdisk = create_ramdisk(ramdisk_dir, self._scratch_dir)
            self._ramdisk = ramdisk
            if rootfs is None:
                logging.debug("Attempting to set deployment data")
                self.deployment_data = deployment_data.get(target_type)

        if dtb is not None:
            dtb = download_image(dtb, self.context)
            self._dtb = dtb

        if firmware is not None:
            firmware = download_image(firmware, self.context)
            self._firmware = firmware

    def deploy_linaro(self, hwpack, rootfs, dtb, rootfstype, bootloadertype):
        odir = self.scratch_dir
        self._sd_image = generate_image(self, hwpack, rootfs, dtb,
                                        odir, bootloadertype, rootfstype)
        self.customize_image(self._sd_image)

    def deploy_linaro_prebuilt(self, image, dtb, rootfstype, bootloadertype):
        self._sd_image = download_image(image, self.context)
        self.customize_image(self._sd_image)

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        with image_partition_mounted(self._sd_image, partition) as mntdir:
            path = '%s/%s' % (mntdir, directory)
            ensure_directory(path)
            yield path

    def extract_tarball(self, tarball_url, partition, directory='/'):
        logging.info('extracting %s to target', tarball_url)

        with image_partition_mounted(self._sd_image, partition) as mntdir:
            tb = download_image(tarball_url, self.context, decompress=False)
            extract_tar(tb, '%s/%s' % (mntdir, directory))

    def power_on(self):
        if self.proc is not None:
            logging.warning('device already powered on, powering off first')
            self.power_off(None)

        qemu_options = ''

        if self._kernel:
            qemu_options += ' -kernel %s' % self._kernel
            if self._sd_image is None:
                kernel_args = ' '.join(self._load_boot_cmds(default='boot_cmds_ramdisk'))
            else:
                kernel_args = ' '.join(self._load_boot_cmds(default='boot_cmds'))
            qemu_options += ' -append "%s"' % kernel_args

        if self._ramdisk:
            qemu_options += ' -initrd %s' % self._ramdisk

        if self._dtb:
            qemu_options += ' -dtb %s' % self._dtb

        if self._firmware:
            qemu_options += ' -bios %s' % self._firmware

        if self._sd_image:
            qemu_options += ' ' + self.config.qemu_drive_interface
            qemu_options = qemu_options.format(DISK_IMAGE=self._sd_image)

        # workaround for quoting issues with `ssh -- qemu-system-??? ...`
        if self.config.qemu_binary.startswith('ssh'):
            qemu_options = re.sub('"', '\\"', qemu_options)

        qemu_cmd = '%s %s %s' % (self.config.qemu_binary, self.config.qemu_options, qemu_options)
        logging.info('launching qemu with command %r', qemu_cmd)
        self.proc = self.context.spawn(qemu_cmd, timeout=1200)
        self._monitor_boot(self.proc, self.tester_ps1, self.tester_ps1_pattern)
        if self._ramdisk and self._sd_image is None:
            self.proc.sendline('cat /proc/net/pnp > /etc/resolv.conf',
                               send_char=self.config.send_char)

        return self.proc

    def power_off(self, proc):
        finalize_process(self.proc)
        self.proc = None

    def get_device_version(self):
        try:
            output = subprocess.check_output(
                [self.config.qemu_binary, '--version'])
            matches = re.findall('[0-9]+\.[0-9a-z.+\-:~]+', output)
            return matches[-1]
        except subprocess.CalledProcessError:
            return "unknown"


target_class = QEMUTarget
