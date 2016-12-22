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
import subprocess

from lava_dispatcher.device.master import (
    MasterImageTarget
)
from lava_dispatcher.client.base import (
    NetworkCommandRunner,
)
from lava_dispatcher.utils import (
    finalize_process,
    connect_to_serial,
    extract_overlay,
    extract_ramdisk,
    create_ramdisk,
    ensure_directory,
    append_dtb,
    create_uimage,
    is_uimage,
)
from lava_dispatcher.errors import (
    CriticalError,
)
from lava_dispatcher.downloader import (
    download_image,
)
from lava_dispatcher import deployment_data


class BootloaderTarget(MasterImageTarget):

    def __init__(self, context, config):
        super(BootloaderTarget, self).__init__(context, config)
        self._booted = False
        self._reset_boot = False
        self._in_test_shell = False
        self._default_boot_cmds = 'boot_cmds_ramdisk'
        self._lava_nfsrootfs = None
        self._uboot_boot = False
        self._ipxe_boot = False
        self._uefi_boot = False
        self._boot_tags = {}
        self._base_tmpdir, self._tmpdir = self._setup_tmpdir()

    def _get_http_url(self, path):
        prefix = self.context.config.lava_image_url
        return prefix + '/' + self._get_rel_path(path, self._base_tmpdir)

    def _set_load_addresses(self, bootz):
        meta = {}
        if not bootz and self.config.u_load_addrs and len(self.config.u_load_addrs) == 3:
            logging.info("Attempting to set uImage Load Addresses")
            self._boot_tags['{KERNEL_ADDR}'] = self.config.u_load_addrs[0]
            self._boot_tags['{RAMDISK_ADDR}'] = self.config.u_load_addrs[1]
            self._boot_tags['{DTB_ADDR}'] = self.config.u_load_addrs[2]
            # Set boot metadata
            meta['kernel-image'] = 'uImage'
            meta['kernel-addr'] = self.config.u_load_addrs[0]
            meta['initrd-addr'] = self.config.u_load_addrs[1]
            meta['dtb-addr'] = self.config.u_load_addrs[2]
            self.context.test_data.add_metadata(meta)
        elif bootz and self.config.z_load_addrs and len(self.config.z_load_addrs) == 3:
            logging.info("Attempting to set zImage Load Addresses")
            self._boot_tags['{KERNEL_ADDR}'] = self.config.z_load_addrs[0]
            self._boot_tags['{RAMDISK_ADDR}'] = self.config.z_load_addrs[1]
            self._boot_tags['{DTB_ADDR}'] = self.config.z_load_addrs[2]
            # Set boot metadata
            meta['kernel-image'] = 'zImage'
            meta['kernel-addr'] = self.config.z_load_addrs[0]
            meta['initrd-addr'] = self.config.z_load_addrs[1]
            meta['dtb-addr'] = self.config.z_load_addrs[2]
            self.context.test_data.add_metadata(meta)
        else:
            logging.debug("Undefined u_load_addrs or z_load_addrs. Three values required!")

    def _get_uboot_boot_command(self, kernel, ramdisk, dtb):
        bootz = False
        bootx = []

        if is_uimage(kernel, self.context):
            logging.info('Attempting to set boot command as bootm')
            bootx.append('bootm')
        else:
            logging.info('Attempting to set boot command as bootz')
            bootx.append('bootz')
            bootz = True

        # At minimal we have a kernel
        bootx.append('${kernel_addr_r}')

        if self.config.ramdisk_raw:
            bootx.append('-')
        elif ramdisk is not None:
            bootx.append('${initrd_addr_r}')
        elif ramdisk is None and dtb is not None:
            bootx.append('-')

        if dtb is not None:
            bootx.append('${fdt_addr_r}')

        self._set_load_addresses(bootz)

        return ' '.join(bootx)

    def _is_uboot(self):
        if self._uboot_boot:
            return True
        else:
            return False

    def _is_ipxe(self):
        if self._ipxe_boot:
            return True
        else:
            return False

    def _is_uefi(self):
        if self._uefi_boot:
            return True
        else:
            return False

    def _is_bootloader(self):
        if self._is_uboot() or self._is_ipxe() or self._is_uefi():
            return True
        else:
            return False

    def _set_boot_type(self, bootloadertype):
        if bootloadertype == "u_boot":
            self._uboot_boot = True
        elif bootloadertype == 'ipxe':
            self._ipxe_boot = True
        elif bootloadertype == 'uefi':
            self._uefi_boot = True
        else:
            raise CriticalError("Unknown bootloader type")

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs, image, bootloader, firmware, bl0, bl1,
                             bl2, bl31, rootfstype, bootloadertype, target_type, qemu_pflash=None):
        if self.__deployment_data__ is None:
            # Get deployment data
            logging.debug("Attempting to set deployment data")
            self.deployment_data = deployment_data.get(target_type)
        else:
            # Reset deployment data
            logging.debug("Attempting to reset deployment data")
            self.power_off(self.proc)
            self.__init__(self.context, self.config)
            # Get deployment data
            self.deployment_data = deployment_data.get(target_type)
        # We set the boot type
        self._set_boot_type(bootloadertype)
        # At a minimum we must have a kernel
        if kernel is None:
            raise CriticalError("No kernel image to boot")
        if self._is_uboot() or self._is_uefi() or self._is_ipxe():
            # Set the server IP (Dispatcher)
            self._boot_tags['{SERVER_IP}'] = self.context.config.lava_server_ip
            # We have been passed kernel image
            kernel = download_image(kernel, self.context,
                                    self._tmpdir, decompress=False)
            if self._is_uboot() or self._is_uefi():
                if self.config.uimage_only and not is_uimage(kernel, self.context):
                    if len(self.config.u_load_addrs) == 3:
                        if self.config.text_offset:
                            load_addr = self.config.text_offset
                        else:
                            load_addr = self.config.u_load_addrs[0]
                        kernel = create_uimage(kernel, load_addr,
                                               self._tmpdir, self.config.uimage_xip,
                                               self.config.uimage_arch)
                        logging.info('uImage created successfully')
                    else:
                        logging.error('Undefined u_load_addrs, aborting uImage creation')
            self._boot_tags['{KERNEL}'] = self._get_rel_path(kernel, self._base_tmpdir)

            if ramdisk is not None:
                # We have been passed a ramdisk
                ramdisk = download_image(ramdisk, self.context,
                                         self._tmpdir,
                                         decompress=False)
                if overlays is not None:
                    ramdisk_dir = extract_ramdisk(ramdisk, self._tmpdir,
                                                  is_uboot=self._is_uboot_ramdisk(ramdisk))
                    for overlay in overlays:
                        overlay = download_image(overlay, self.context,
                                                 self._tmpdir,
                                                 decompress=False)
                        extract_overlay(overlay, ramdisk_dir)
                    ramdisk = create_ramdisk(ramdisk_dir, self._tmpdir)
                if self._is_uboot() and not self.config.ramdisk_raw:
                    # Ensure ramdisk has u-boot header
                    if not self._is_uboot_ramdisk(ramdisk):
                        ramdisk_uboot = ramdisk + ".uboot"
                        logging.info("RAMdisk needs u-boot header.  Adding.")
                        cmd = "mkimage -A %s -T ramdisk -C none -d %s %s > /dev/null" \
                            % (self.config.uimage_arch, ramdisk, ramdisk_uboot)
                        r = subprocess.call(cmd, shell=True)
                        if r == 0:
                            ramdisk = ramdisk_uboot
                        else:
                            logging.warning("Unable to add u-boot header to ramdisk.  Tried %s", cmd)
                self._boot_tags['{RAMDISK}'] = self._get_rel_path(ramdisk, self._base_tmpdir)
            if dtb is not None:
                # We have been passed a device tree blob
                dtb = download_image(dtb, self.context,
                                     self._tmpdir, decompress=False)
                if self.config.append_dtb:
                    kernel = append_dtb(kernel, dtb, self._tmpdir)
                    logging.info('Appended dtb to kernel image successfully')
                    self._boot_tags['{KERNEL}'] = self._get_rel_path(kernel, self._base_tmpdir)
                else:
                    self._boot_tags['{DTB}'] = self._get_rel_path(dtb, self._base_tmpdir)
            if rootfs is not None:
                # We have been passed a rootfs
                rootfs = download_image(rootfs, self.context,
                                        self._tmpdir, decompress=False)
                self._boot_tags['{ROOTFS}'] = self._get_rel_path(rootfs, self._base_tmpdir)
            if nfsrootfs is not None:
                # Extract rootfs into nfsrootfs directory
                nfsrootfs = download_image(nfsrootfs, self.context,
                                           self._tmpdir,
                                           decompress=False)
                self._lava_nfsrootfs = self._setup_nfs(nfsrootfs, self._tmpdir)
                self._default_boot_cmds = 'boot_cmds_nfs'
                self._boot_tags['{NFSROOTFS}'] = self._lava_nfsrootfs
                if overlays is not None and ramdisk is None:
                    for overlay in overlays:
                        overlay = download_image(overlay, self.context,
                                                 self._tmpdir,
                                                 decompress=False)
                        extract_overlay(overlay, self._lava_nfsrootfs)
            if bootloader is not None:
                # We have been passed a bootloader
                bootloader = download_image(bootloader, self.context,
                                            self._tmpdir,
                                            decompress=False)
                self._boot_tags['{BOOTLOADER}'] = self._get_rel_path(bootloader, self._base_tmpdir)
            if firmware is not None:
                # We have been passed firmware
                firmware = download_image(firmware, self.context,
                                          self._tmpdir,
                                          decompress=False)

                self._boot_tags['{FIRMWARE}'] = self._get_rel_path(firmware, self._base_tmpdir)
            if self._is_uboot():
                self._boot_tags['{BOOTX}'] = self._get_uboot_boot_command(kernel,
                                                                          ramdisk,
                                                                          dtb)

    def deploy_linaro(self, hwpack, rfs, dtb, rootfstype, bootfstype,
                      bootloadertype, qemu_pflash=None):
        self._uboot_boot = False
        super(BootloaderTarget, self).deploy_linaro(hwpack, rfs, dtb,
                                                    rootfstype, bootfstype,
                                                    bootloadertype, qemu_pflash=qemu_pflash)

    def deploy_linaro_prebuilt(self, image, dtb, rootfstype, bootfstype, bootloadertype, qemu_pflash=None):
        self._uboot_boot = False
        if self._is_ipxe():
            if image is not None:
                self._ipxe_boot = True
                # We are not booted yet
                self._booted = False
                # We specify OE deployment data, vanilla as possible
                self.deployment_data = deployment_data.oe
                # We have been passed a image
                image = download_image(image, self.context,
                                       self._tmpdir,
                                       decompress=False)
                image_url = self._get_http_url(image)
                # We are booting an image, can be iso or whole disk
                self._boot_tags['{IMAGE}'] = image_url
            else:
                raise CriticalError("No image to boot")
        else:
            super(BootloaderTarget, self).deploy_linaro_prebuilt(image,
                                                                 dtb,
                                                                 rootfstype,
                                                                 bootfstype,
                                                                 bootloadertype,
                                                                 qemu_pflash=qemu_pflash)

    def _run_boot(self):
        self._load_test_firmware()
        self._enter_bootloader(self.proc)
        boot_cmds = self._load_boot_cmds(default=self._default_boot_cmds,
                                         boot_tags=self._boot_tags)
        # Sometimes a command must be run to clear u-boot console buffer
        if self.config.pre_boot_cmd:
            self.proc.sendline(self.config.pre_boot_cmd,
                               send_char=self.config.send_char)
        self._customize_bootloader(self.proc, boot_cmds)
        self._monitor_boot(self.proc, self.tester_ps1, self.tester_ps1_pattern)

    def _boot_linaro_image(self):
        if self.proc:
            if self.config.connection_command_terminate:
                self.proc.sendline(self.config.connection_command_terminate)
            else:
                self._politely_close_console(self.proc)
            finalize_process(self.proc)
            self.proc = None
        self.proc = connect_to_serial(self.context)
        if self._is_bootloader() and not self._booted:
            if self.config.hard_reset_command or self.config.hard_reset_command == "":
                self._hard_reboot(self.proc)
                self._run_boot()
            else:
                self._soft_reboot(self.proc)
                self._run_boot()
            self._booted = True
        elif self._is_bootloader() and self._booted:
            self.proc.sendline('export PS1="%s"'
                               % self.tester_ps1,
                               send_char=self.config.send_char)
        else:
            super(BootloaderTarget, self)._boot_linaro_image()

    def is_booted(self):
        return self._booted

    def reset_boot(self, in_test_shell=True):
        self._reset_boot = True
        self._booted = False
        self._in_test_shell = in_test_shell

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        if self._is_bootloader() and self._reset_boot:
            self._reset_boot = False
            if self._in_test_shell:
                self._in_test_shell = False
                raise Exception("Operation timed out, resetting platform!")
        if self._is_bootloader() and not self._booted:
            self.context.client.boot_linaro_image()
        if self._is_bootloader() and self._lava_nfsrootfs:
            path = '%s/%s' % (self._lava_nfsrootfs, directory)
            ensure_directory(path)
            yield path
        elif self._is_bootloader():
            pat = self.tester_ps1_pattern
            incrc = self.tester_ps1_includes_rc
            runner = NetworkCommandRunner(self, pat, incrc)
            with self._busybox_file_system(runner, directory) as path:
                yield path
        else:
            with super(BootloaderTarget, self).file_system(
                    partition, directory) as path:
                yield path


target_class = BootloaderTarget
