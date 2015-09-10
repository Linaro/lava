# Copyright (C) 2013 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
# Author: Dave Pigott <dave.pigott@linaro.org>
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

import pexpect
import os
import logging
from time import sleep
from contextlib import contextmanager

from lava_dispatcher.device.bootloader import BootloaderTarget
from lava_dispatcher.utils import extract_tar, unicode_path_check
from lava_dispatcher.downloader import (
    download_image,
)
from lava_dispatcher.errors import (
    CriticalError,
    OperationFailed,
)


class VexpressTarget(BootloaderTarget):

    def __init__(self, context, config):
        super(VexpressTarget, self).__init__(context, config)

        self.test_uefi = None
        self.test_bl0 = None
        self.test_bl1 = None
        self.complete_firmware_master = None
        self.complete_firmware_test = None

        if self.config.vexpress_complete_firmware:
            if (self.config.vexpress_firmware_path_hwpack is None or
                    self.config.vexpress_firmware_path_android is None):
                raise CriticalError(
                    "Vexpress complete firmware devices must "
                    "have vexpress_firmware_path_android and "
                    "vexpress_firmware_hwpack specified")
        elif self.config.vexpress_requires_trusted_firmware:
            if (self.config.vexpress_bl1_image_filename is None or
                    self.config.vexpress_bl1_image_files is None or
                    self.config.vexpress_uefi_image_filename is None or
                    self.config.vexpress_uefi_image_files is None or
                    self.config.vexpress_bl1_path is None or
                    self.config.vexpress_bl1_backup_path is None or
                    self.config.vexpress_uefi_path is None or
                    self.config.vexpress_uefi_backup_path is None or
                    self.config.vexpress_usb_mass_storage_device is None):

                raise CriticalError(
                    "Versatile Express devices that use "
                    "trusted firmware must specify all "
                    "of the following configuration variables: "
                    "vexpress_bl1_image_filename, vexpress_bl1_image_files, "
                    "vexpress_uefi_image_filename, vexpress_uefi_image_files, "
                    "vexpress_bl1_path, vexpress_bl1_backup_path "
                    "vexpress_uefi_path, vexpress_uefi_backup_path and "
                    "vexpress_usb_mass_storage_device")

            if self.config.vexpress_requires_bl0:
                if (self.config.vexpress_bl0_path is None or
                        self.config.vexpress_bl0_backup_path is None):

                    raise CriticalError(
                        "Versatile Express devices that use "
                        "require bl0 must specify all "
                        "of the following configuration variables: "
                        "vexpress_bl0_path, vexpress_bl0_backup_path ")
        else:
            if (self.config.vexpress_uefi_image_filename is None or
                    self.config.vexpress_uefi_image_files is None or
                    self.config.vexpress_uefi_path is None or
                    self.config.vexpress_uefi_backup_path is None or
                    self.config.vexpress_usb_mass_storage_device is None):

                raise CriticalError(
                    "Versatile Express devices must specify all "
                    "of the following configuration variables: "
                    "vexpress_uefi_image_filename, vexpress_uefi_image_files, "
                    "vexpress_uefi_path, vexpress_uefi_backup_path and "
                    "vexpress_usb_mass_storage_device")

    ##################################################################
    # methods inherited from BootloaderTarget and overriden here
    ##################################################################

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs, image, bootloader, firmware, bl0, bl1,
                             bl2, bl31, rootfstype, bootloadertype, target_type, qemu_pflash=None):
        if self.config.vexpress_complete_firmware:
            if firmware is None:
                if self.config.vexpress_firmware_default is None:
                    raise CriticalError("No default board recovery image defined")
                else:
                    tarball = download_image(self.config.vexpress_firmware_default, self.context,
                                             self._tmpdir, decompress=False)
                    self._extract_compressed_firmware(tarball)
            else:
                tarball = download_image(firmware, self.context,
                                         self._tmpdir,
                                         decompress=False)
                self._extract_compressed_firmware(tarball)
            firmware = None
        else:
            if bootloader is None:
                if self.config.vexpress_uefi_default is None:
                    raise CriticalError("UEFI image is required")
                else:
                    self.test_uefi = download_image(self.config.vexpress_uefi_default, self.context,
                                                    self._tmpdir,
                                                    decompress=False)
            else:
                self.test_uefi = download_image(bootloader, self.context,
                                                self._tmpdir,
                                                decompress=False)
                bootloader = None

            if self.config.vexpress_requires_trusted_firmware:
                if bl1 is None and self.config.vexpress_requires_trusted_firmware:
                    if self.config.vexpress_bl1_default is None:
                        raise CriticalError("BL1 firmware is required")
                    else:
                        self.test_bl1 = download_image(self.config.vexpress_bl1_default, self.context,
                                                       self._tmpdir,
                                                       decompress=False)
                else:
                    self.test_bl1 = download_image(bl1, self.context,
                                                   self._tmpdir,
                                                   decompress=False)
                    bl1 = None

                if bl0 is None and self.config.vexpress_requires_bl0:
                    if self.config.vexpress_bl0_default is None:
                        raise CriticalError("BL0 firmware is required")
                    else:
                        self.test_bl0 = download_image(self.config.vexpress_bl0_default, self.context,
                                                       self._tmpdir,
                                                       decompress=False)
                else:
                    self.test_bl0 = download_image(bl0, self.context,
                                                   self._tmpdir,
                                                   decompress=False)
                    bl0 = None

        super(VexpressTarget, self).deploy_linaro_kernel(kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs, image, bootloader,
                                                         firmware, bl0, bl1, bl2, bl31, rootfstype, bootloadertype,
                                                         target_type, qemu_pflash=qemu_pflash)

    def _load_test_firmware(self):
        with self._mcc_setup() as mount_point:
            self._install_test_firmware(mount_point)

    def _load_master_firmware(self):
        with self._mcc_setup() as mount_point:
            self._restore_firmware_backup(mount_point)

    def _deploy_android_tarballs(self, master, boot, system, data):
        super(VexpressTarget, self)._deploy_android_tarballs(master, boot,
                                                             system, data)
        # for precanned images bl0 is only contained in the
        # complete firmware tarball so error if the complete
        # firmware flag is not set
        if (self.config.vexpress_requires_bl0 and
                not self.config.vexpress_complete_firmware):
                    raise CriticalError("vexpress_complete_firmware flag must be set if BL0 firmware is required")
        # android images have boot files inside boot/ in the tarball
        if self.config.vexpress_complete_firmware:
            self._extract_android_firmware(boot)
        else:
            self._extract_firmware_from_tarball(boot)

    def _deploy_tarballs(self, boot_tgz, root_tgz, rootfstype, bootfstype):
        super(VexpressTarget, self)._deploy_tarballs(boot_tgz, root_tgz,
                                                     rootfstype, bootfstype)
        # for precanned images bl0 is only contained in the
        # complete firmware tarball so error if the complete
        # firmware flag is not set
        if (self.config.vexpress_requires_bl0 and
                not self.config.vexpress_complete_firmware):
                    raise CriticalError("vexpress_complete_firmware flag must be set if BL0 firmware is required")
        if self.config.vexpress_complete_firmware:
            self._extract_uncompressed_firmware(root_tgz)
        else:
            self._extract_firmware_from_tarball(boot_tgz)

    ##################################################################
    # implementation-specific methods
    ##################################################################

    @contextmanager
    def _mcc_setup(self):
        """
        This method will manage the context for manipulating the USB mass
        storage device, and pass the mount point where the USB MSD is mounted
        to the inner block.

        Example:

            with self._mcc_setup() as mount_point:
                do_stuff_with(mount_point)


        This can be used for example to copy files from/to the USB MSD.
        Mounting and unmounting is managed by this method, so the inner block
        does not have to handle that.
        """

        mount_point = os.path.join(self.scratch_dir, 'vexpress-usb')
        if not unicode_path_check(mount_point):
            os.makedirs(mount_point)

        self._enter_mcc()
        self._mount_usbmsd(mount_point)
        try:
            yield mount_point
        finally:
            self._umount_usbmsd(mount_point)
            self._leave_mcc()

    def _enter_mcc(self):
        match_id = self.proc.expect([
            self.config.vexpress_stop_autoboot_prompt,
            pexpect.EOF, pexpect.TIMEOUT], timeout=120)
        if match_id != 0:
            msg = 'Unable to intercept MCC boot prompt'
            logging.error(msg)
            raise OperationFailed(msg)
        self.proc.sendline("")
        match_id = self.proc.expect([
            'Cmd>',
            pexpect.EOF, pexpect.TIMEOUT], timeout=120)
        if match_id != 0:
            msg = 'MCC boot prompt not found'
            logging.error(msg)
            raise OperationFailed(msg)

    def _mount_usbmsd(self, mount_point):
        self.proc.sendline("USB_ON")
        self.proc.expect(['Cmd>'])

        # wait a few seconds so that the kernel on the host detects the USB
        # mass storage interface exposed by the Vexpress
        sleep(5)

        usb_device = self.config.vexpress_usb_mass_storage_device

        # Try to mount the MMC device. If we detect a failure when mounting. Toggle
        # the USB MSD interface, and try again. If we fail again, raise an OperationFailed
        # except to retry to the boot process.
        if self.context.run_command('mount %s %s' % (usb_device, mount_point)) != 0:
            self.proc.sendline("USB_OFF")
            self.proc.expect(['Cmd>'])
            self.proc.sendline("USB_ON")
            self.proc.expect(['Cmd>'])
            sleep(5)
            if self.context.run_command('mount %s %s' % (usb_device, mount_point)) != 0:
                msg = "Failed to mount MMC on host"
                logging.exception(msg)
                raise OperationFailed(msg)

    def _umount_usbmsd(self, mount_point):
        self.context.run_command_with_retries('umount %s' % mount_point)
        self.proc.sendline("USB_OFF")
        self.proc.expect(['Cmd>'])
        self.proc.sendline("flash")
        self.proc.expect(['Flash>'])
        self.proc.sendline("eraserange %s %s" % (self.config.vexpress_flash_range_low, self.config.vexpress_flash_range_high))
        self.proc.expect(['Flash>'])
        self.proc.sendline("exit")
        self.proc.expect(['Cmd>'])

    def _leave_mcc(self):
        self.proc.sendline("reboot")

    def _extract_firmware_from_tarball(self, tarball):

        extract_tar(tarball, self.scratch_dir)

        if self.config.vexpress_requires_trusted_firmware:
            self.test_bl1 = self._copy_first_find_from_list(self.scratch_dir, self.scratch_dir,
                                                            self.config.vexpress_bl1_image_files,
                                                            self.config.vexpress_bl1_image_filename)

        self.test_uefi = self._copy_first_find_from_list(self.scratch_dir, self.scratch_dir,
                                                         self.config.vexpress_uefi_image_files,
                                                         self.config.vexpress_uefi_image_filename)

    def _extract_compressed_firmware_master(self, tarball):
        firmdir = self.scratch_dir + "/board-recovery-image-master"
        self.context.run_command('mkdir -p %s' % firmdir)
        self.context.run_command('rm -r %s/*' % firmdir)
        extract_tar(tarball, firmdir)
        self.complete_firmware_master = firmdir

    def _extract_compressed_firmware(self, tarball):
        firmdir = self.scratch_dir + "/board-recovery-image-test"
        self.context.run_command('mkdir -p %s' % firmdir)
        self.context.run_command('rm -r %s/*' % firmdir)
        extract_tar(tarball, firmdir)
        self.complete_firmware_test = firmdir

    def _extract_uncompressed_firmware(self, tarball):
        extract_tar(tarball, self.scratch_dir)
        self.complete_firmware_test = self._find_dir(self.scratch_dir, self.config.vexpress_firmware_path_hwpack)

    def _extract_android_firmware(self, tarball):
        extract_tar(tarball, self.scratch_dir)
        firmware_tarball = self._find_file(self.scratch_dir, self.config.vexpress_firmware_path_android)
        self._extract_compressed_firmware(firmware_tarball)

    def _copy_firmware_to_juno(self, firmware_dir, mount_point):
        self.context.run_command('rm -r %s/*' % mount_point)
        self.context.run_command('cp -r %s/* %s' % (firmware_dir, mount_point))

    def _restore_firmware_backup(self, mount_point):
        if self.config.vexpress_complete_firmware:
            tarball = download_image(self.config.vexpress_firmware_default, self.context,
                                     self.scratch_dir, decompress=False)
            self._extract_compressed_firmware_master(tarball)
            self._copy_firmware_to_juno(self.complete_firmware_master, mount_point)
        else:
            uefi_path = self.config.vexpress_uefi_path
            uefi = os.path.join(mount_point, uefi_path)
            uefi_backup_path = self.config.vexpress_uefi_backup_path
            uefi_backup = os.path.join(mount_point, uefi_backup_path)

            if unicode_path_check(uefi_backup):
                # restore the uefi backup
                self.context.run_command_with_retries('cp %s %s' % (uefi_backup, uefi))
            else:
                # no existing backup yet means that this is the first time ever;
                # the uefi in there is the good one, and we backup it up.
                self.context.run_command_with_retries('cp %s %s' % (uefi, uefi_backup))

            if self.config.vexpress_requires_trusted_firmware:
                bl1_path = self.config.vexpress_bl1_path
                bl1 = os.path.join(mount_point, bl1_path)
                bl1_backup_path = self.config.vexpress_bl1_backup_path
                bl1_backup = os.path.join(mount_point, bl1_backup_path)

                if unicode_path_check(bl1_backup):
                    # restore the firmware backup
                    self.context.run_command_with_retries('cp %s %s' % (bl1_backup, bl1))
                else:
                    # no existing backup yet means that this is the first time ever;
                    # the firmware in there is the good one, and we backup it up.
                    self.context.run_command_with_retries('cp %s %s' % (bl1, bl1_backup))

                if self.config.vexpress_requires_bl0:
                    bl0_path = self.config.vexpress_bl0_path
                    bl0 = os.path.join(mount_point, bl0_path)
                    bl0_backup_path = self.config.vexpress_bl0_backup_path
                    bl0_backup = os.path.join(mount_point, bl0_backup_path)

                    if unicode_path_check(bl0_backup):
                        # restore the bl0 backup
                        self.context.run_command_with_retries('cp %s %s' % (bl0_backup, bl0))
                    else:
                        # no existing backup yet means that this is the first time ever;
                        # the bl0 in there is the good one, and we backup it up.
                        self.context.run_command_with_retries('cp %s %s' % (bl0, bl0_backup))

    def _install_test_firmware(self, mount_point):
        if self.config.vexpress_complete_firmware:
            if unicode_path_check(self.complete_firmware_test):
                self._copy_firmware_to_juno(self.complete_firmware_test, mount_point)
            else:
                raise CriticalError("No path to complete firmware")
        else:
            uefi_path = self.config.vexpress_uefi_path
            uefi = os.path.join(mount_point, uefi_path)

            if unicode_path_check(self.test_uefi):
                self.context.run_command('cp %s %s' % (self.test_uefi, uefi))
            else:
                raise CriticalError("No path to uefi firmware")

            if self.config.vexpress_requires_trusted_firmware:
                bl1_path = self.config.vexpress_bl1_path
                bl1 = os.path.join(mount_point, bl1_path)

                if unicode_path_check(self.test_bl1):
                    self.context.run_command('cp %s %s' % (self.test_bl1, bl1))
                else:
                    raise CriticalError("No path to bl1 firmware")

                if self.config.vexpress_requires_bl0:
                    bl0_path = self.config.vexpress_bl0_path
                    bl0 = os.path.join(mount_point, bl0_path)

                    if unicode_path_check(self.test_bl0):
                        self.context.run_command('cp %s %s' % (self.test_bl0, bl0))
                    else:
                        raise CriticalError("No path to bl0 firmware")


target_class = VexpressTarget
