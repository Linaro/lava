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
    extract_targz,
    finalize_process,
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
        self._is_kernel_present = False

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, rootfs, nfsrootfs,
                             bootloader, firmware, rootfstype, bootloadertype,
                             target_type):
        # Check for errors
        if rootfs is None:
            raise CriticalError("You must specify a QEMU file system image")
        if kernel is None:
            raise CriticalError("No kernel images to boot")

        # build the QEMU command line
        self._sd_image = download_image(rootfs, self.context)
        self.customize_image(self._sd_image)

        kernel = download_image(kernel, self.context)
        self._is_kernel_present = True
        self.append_qemu_options(' -kernel %s' % kernel)
        if ramdisk is not None:
            ramdisk = download_image(ramdisk, self.context)
            self.append_qemu_options(' -initrd %s' % ramdisk)
        if dtb is not None:
            dtb = download_image(dtb, self.context)
            self.append_qemu_options(' -dtb %s' % ramdisk)
        if firmware is not None:
            firmware = download_image(firmware, self.context)
            self.append_qemu_options(' -bios %s' % firmware)

    def deploy_linaro(self, hwpack, rootfs, rootfstype, bootloadertype):
        odir = self.scratch_dir
        self._sd_image = generate_image(self, hwpack, rootfs, odir,
                                        bootloadertype, rootfstype)
        self.customize_image(self._sd_image)

    def deploy_linaro_prebuilt(self, image, rootfstype, bootloadertype):
        self._sd_image = download_image(image, self.context)
        self.customize_image(self._sd_image)

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        with image_partition_mounted(self._sd_image, partition) as mntdir:
            path = '%s/%s' % (mntdir, directory)
            ensure_directory(path)
            yield path

    def extract_tarball(self, tarball_url, partition, directory='/'):
        logging.info('extracting %s to target' % tarball_url)

        with image_partition_mounted(self._sd_image, partition) as mntdir:
            tb = download_image(tarball_url, self.context, decompress=False)
            extract_targz(tb, '%s/%s' % (mntdir, directory))

    def power_on(self):
        if self.proc is not None:
            logging.warning('device already powered on, powering off first')
            self.power_off(None)

        # If the -kernel option was given, find the boot command
        # We load it here in order to get the configuration from the job
        # definition if needed
        if self._is_kernel_present:
            kernel_args = ' '.join(self._load_boot_cmds())
            self.append_qemu_options(' -append "%s"' % kernel_args)

        qemu_cmd = '%s %s %s' % (self.config.qemu_binary, self.config.qemu_options, self._qemu_options or '')
        qemu_cmd = qemu_cmd.format(DISK_IMAGE=self._sd_image)
        logging.info('launching qemu with command %r' % qemu_cmd)
        self.proc = self.context.spawn(qemu_cmd, timeout=1200)
        self._auto_login(self.proc)
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

    def append_qemu_options(self, parameter):
        if self._qemu_options is None:
            self._qemu_options = parameter
        else:
            self._qemu_options += parameter

target_class = QEMUTarget
