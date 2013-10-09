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

from lava_dispatcher.device.master import (
    MasterImageTarget
)
from lava_dispatcher.client.base import (
    NetworkCommandRunner,
)
from lava_dispatcher.utils import (
    string_to_list,
    mk_targz,
    rmtree,
)
from lava_dispatcher.errors import (
    CriticalError,
    OperationFailed,
)
from lava_dispatcher.downloader import (
    download_image,
    download_with_retry,
)
from lava_dispatcher import deployment_data

class BootloaderTarget(MasterImageTarget):

    def __init__(self, context, config):
        super(BootloaderTarget, self).__init__(context, config)
        self._booted = False
        self._boot_cmds = None
        self._lava_cmds = None
        self._uboot_boot = False
        self._ipxe_boot = False
        # This is the offset into the path, used to reference bootfiles
        self._offset = self.scratch_dir.index('images')

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, rootfs, bootloader,
                             firmware, rootfstype, bootloadertype):
        if bootloadertype == "u_boot":
            # We assume we will be controlling u-boot
            if kernel is not None:
                # We have been passed kernel image, setup TFTP boot
                self._uboot_boot = True
                # We are not booted yet
                self._booted = False
                # We specify OE deployment data, vanilla as possible
                self.deployment_data = deployment_data.oe
                # Set the TFTP server IP (Dispatcher)
                self._lava_cmds = "setenv lava_server_ip " + \
                                   self.context.config.lava_server_ip + ","
                kernel = download_image(kernel, self.context,
                                        self.scratch_dir, decompress=False)
                self._lava_cmds += "setenv lava_kernel " + \
                                    kernel[self._offset::] + ","
                if ramdisk is not None:
                    # We have been passed a ramdisk
                    ramdisk = download_image(ramdisk, self.context,
                                             self.scratch_dir,
                                             decompress=False)
                    self._lava_cmds += "setenv lava_ramdisk " + \
                                        ramdisk[self._offset::] + ","
                if dtb is not None:
                    # We have been passed a device tree blob
                    dtb = download_image(dtb, self.context,
                                         self.scratch_dir, decompress=False)
                    self._lava_cmds += "setenv lava_dtb " + dtb[self._offset::] + ","
                if rootfs is not None:
                    # We have been passed a rootfs
                    rootfs = download_image(rootfs, self.context,
                                            self.scratch_dir, decompress=False)
                    self._lava_cmds += "setenv lava_rootfs " + \
                                        rootfs[self._offset::] + ","
                if bootloader is not None:
                    # We have been passed a bootloader
                    bootloader = download_image(bootloader, self.context,
                                                self.scratch_dir,
                                                decompress=False)
                    self._lava_cmds += "setenv lava_bootloader " + \
                                        bootloader[self._offset::] + ","
                if firmware is not None:
                    # We have been passed firmware
                    firmware = download_image(firmware, self.context,
                                              self.scratch_dir,
                                              decompress=False)
                    self._lava_cmds += "setenv lava_firmware " + \
                                        firmware[self._offset::] + ","
            else:
                # This *should* never happen
                raise CriticalError("No kernel images to boot")
        elif bootloadertype == "ipxe":
            if kernel is not None:
                self._ipxe_boot = True
                # We are not booted yet
                self._booted = False
                # We specify OE deployment data, vanilla as possible
                self.deployment_data = deployment_data.oe
                self._lava_cmds = "set kernel_url %s ; " % kernel + ","
                # We are booting a kernel with ipxe, need an initrd too
                if ramdisk is not None:
                    # We have been passed a ramdisk
                    self._lava_cmds += "set initrd_url %s ; " % ramdisk + ","
                else:
                    raise CriticalError("kernel but no ramdisk")
            elif rootfs is not None:
                # We are booting an image, can be iso or whole disk
                # no image argument passed yet - code for a rainy day
                self._lava_cmds = "sanboot %s ; " % rootfs
            else:
                raise CriticalError("No kernel images to boot")
        else:
            # Define other "types" of bootloaders here. UEFI? Grub?
            raise CriticalError("Unknown bootloader type")

    def deploy_linaro(self, hwpack, rfs, bootloadertype):
        self._uboot_boot = False
        super(BootloaderTarget, self).deploy_linaro(hwpack, rfs,
                                                    bootloadertype)

    def deploy_linaro_prebuilt(self, image, bootloadertype):
        self._uboot_boot = False
        if self._ipxe_boot:
            if image is not None:
                self._ipxe_boot = True
                # We are not booted yet
                self._booted = False
                # We specify OE deployment data, vanilla as possible
                self.deployment_data = deployment_data.oe
                # We are booting an image, can be iso or whole disk
                self._lava_cmds = "sanboot %s ; " % image
            else:
                raise CriticalError("No image to boot")
        else:
            super(BootloaderTarget, self).deploy_linaro_prebuilt(image,
                                                                 bootloadertype)

    def _inject_boot_cmds(self):
        if self._is_job_defined_boot_cmds(self.config.boot_cmds):
            logging.info('Overriding boot_cmds from job file')
            self._boot_cmds = string_to_list(self._lava_cmds.encode('ascii')) \
                                             + self.config.boot_cmds
        else:
            if self.config.boot_cmds_tftp is None:
                raise CriticalError("No TFTP boot commands defined")
            else:
                logging.info('Loading boot_cmds from device configuration')
                self._boot_cmds = self._lava_cmds + self.config.boot_cmds_tftp
                self._boot_cmds = string_to_list(
                                   self._boot_cmds.encode('ascii'))

    def _run_boot(self):
        self._enter_bootloader(self.proc)
        self._inject_boot_cmds()
        self._customize_bootloader(self.proc, self._boot_cmds)
        self.proc.expect(self.config.image_boot_msg, timeout=300)
        self._wait_for_prompt(self.proc, self.config.test_image_prompts,
                              self.config.boot_linaro_timeout)

    def _boot_linaro_image(self):
        if (self._uboot_boot or self._ipxe_boot) and not self._booted:
            try:
                if self.config.hard_reset_command:
                    self._hard_reboot()
                    self._run_boot()
                else:
                    self._soft_reboot()
                    self._run_boot()
            except:
                raise OperationFailed("_run_boot failed")
            self.proc.sendline('export PS1="%s"'
                               % self.deployment_data['TESTER_PS1'])
            self._booted = True
        elif (self._uboot_boot or self._ipxe_boot) and self._booted:
            self.proc.sendline('export PS1="%s"'
                               % self.deployment_data['TESTER_PS1'])
        else:
            super(BootloaderTarget, self)._boot_linaro_image()

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        if self._uboot_boot or self._ipxe_boot:
            try:
                pat = self.deployment_data['TESTER_PS1_PATTERN']
                incrc = self.deployment_data['TESTER_PS1_INCLUDES_RC']
                runner = NetworkCommandRunner(self, pat, incrc)

                targetdir = '/%s' % directory
                runner.run('mkdir -p %s' % targetdir)
                parent_dir, target_name = os.path.split(targetdir)
                runner.run('/bin/tar -cmzf /tmp/fs.tgz -C %s %s'
                           % (parent_dir, target_name))
                runner.run('cd /tmp')  # need to be in same dir as fs.tgz

                ip = runner.get_target_ip()
                url_base = self._start_busybox_http_server(runner, ip)

                url = url_base + '/fs.tgz'
                logging.info("Fetching url: %s" % url)
                tf = download_with_retry(self.context, self.scratch_dir,
                                         url, False)

                tfdir = os.path.join(self.scratch_dir, str(time.time()))

                try:
                    os.mkdir(tfdir)
                    self.context.run_command('/bin/tar -C %s -xzf %s'
                                             % (tfdir, tf))
                    yield os.path.join(tfdir, target_name)
                finally:
                    tf = os.path.join(self.scratch_dir, 'fs.tgz')
                    mk_targz(tf, tfdir)
                    rmtree(tfdir)

                    # get the last 2 parts of tf, ie "scratchdir/tf.tgz"
                    tf = '/'.join(tf.split('/')[-2:])
                    runner.run('rm -rf %s' % targetdir)
                    self._target_extract(runner, tf, parent_dir)
            finally:
                self._stop_busybox_http_server(runner)
        else:
            with super(BootloaderTarget, self).file_system(
                    partition, directory) as path:
                yield path

target_class = BootloaderTarget
