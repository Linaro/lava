# Copyright (C) 2013 Linaro Limited
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

import pexpect
import os
import logging
from time import sleep
from contextlib import contextmanager

from lava_dispatcher.device.master import MasterImageTarget
from lava_dispatcher.errors import CriticalError


class VexpressTarget(MasterImageTarget):

    def __init__(self, context, config):
        super(VexpressTarget, self).__init__(context, config)

        self.test_uefi = None

        if (self.config.uefi_image_filename is None or
                self.config.vexpress_uefi_path is None or
                self.config.vexpress_uefi_backup_path is None or
                self.config.vexpress_usb_mass_storage_device is None):

            raise CriticalError(
                "Versatile Express devices must specify all "
                "of the following configuration variables: "
                "uefi_image_filename, vexpress_uefi_path, "
                "vexpress_uefi_backup_path, and "
                "vexpress_usb_mass_storage_device")

    ##################################################################
    # methods inherited from MasterImageTarget and overriden here
    ##################################################################

    def _soft_reboot(self):
        """
        The Vexpress board only displays the prompt to interrupt the MCC when
        it is power-cycled, so we must always do a hard reset in practice.

        When a soft reboot is requested, though, at least we sync the disks
        before sending the hard reset.
        """
        # Try to C-c the running process, if any
        self.proc.sendcontrol('c')
        # Flush file system buffers
        self.proc.sendline('sync')

        self._hard_reboot()

    def _enter_bootloader(self, connection):
        with self._mcc_setup() as mount_point:
            self._install_test_uefi(mount_point)

        super(VexpressTarget, self)._enter_bootloader(connection)

    def _wait_for_master_boot(self):
        with self._mcc_setup() as mount_point:
            self._restore_uefi_backup(mount_point)

        super(VexpressTarget, self)._wait_for_master_boot()

    def _deploy_android_tarballs(self, master, boot, system, data):
        super(VexpressTarget, self)._deploy_android_tarballs(master, boot,
                                                             system, data)
        # android images have boot files inside boot/ in the tarball
        uefi_on_image = os.path.join('boot', self.config.uefi_image_filename)
        self._extract_uefi_from_tarball(boot, uefi_on_image)

    def _deploy_tarballs(self, boot_tgz, root_tgz, rootfstype):
        super(VexpressTarget, self)._deploy_tarballs(boot_tgz, root_tgz,
                                                     rootfstype)
        uefi_on_image = self.config.uefi_image_filename
        self._extract_uefi_from_tarball(boot_tgz, uefi_on_image)

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
        if not os.path.exists(mount_point):
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
            pexpect.EOF, pexpect.TIMEOUT])
        if match_id != 0:
            msg = 'Unable to intercept MCC boot prompt'
            logging.error(msg)
            raise CriticalError(msg)
        self.proc.sendline("")
        self.proc.expect(['Cmd>'])

    def _mount_usbmsd(self, mount_point):
        self.proc.sendline("USB_ON")
        self.proc.expect(['Cmd>'])

        # wait a few seconds so that the kernel on the host detects the USB
        # mass storage interface exposed by the Vexpress
        sleep(5)

        usb_device = self.config.vexpress_usb_mass_storage_device

        self.context.run_command_with_retries('mount %s %s' % (usb_device, mount_point))

    def _umount_usbmsd(self, mount_point):
        self.context.run_command_with_retries('umount %s' % mount_point)

    def _leave_mcc(self):
        self.proc.sendline("reboot")

    def _extract_uefi_from_tarball(self, tarball, uefi_on_image):
        tmpdir = self.scratch_dir

        # Android boot tarballs have the UEFI binary at boot/*.bin, while
        # Ubuntu ones have it at ./*.bin
        #
        # --no-anchored matches the name inside any directory in the tarball.
        self.context.run_command_with_retries('tar --no-anchored -xaf %s -C %s %s' % (tarball, tmpdir,
                                                                                      uefi_on_image))

        uefi_on_image = os.path.join(tmpdir, uefi_on_image)
        test_uefi = os.path.join(tmpdir, 'uefi.bin')
        self.context.run_command_with_retries('mv %s %s' % (uefi_on_image, test_uefi))

        self.test_uefi = test_uefi

    def _restore_uefi_backup(self, mount_point):
        uefi_path = self.config.vexpress_uefi_path
        uefi = os.path.join(mount_point, uefi_path)
        uefi_backup_path = self.config.vexpress_uefi_backup_path
        uefi_backup = os.path.join(mount_point, uefi_backup_path)

        if os.path.exists(uefi_backup):
            # restore the uefi backup
            self.context.run_command_with_retries('cp %s %s' % (uefi_backup, uefi))
        else:
            # no existing backup yet means that this is the first time ever;
            # the uefi in there is the good one, and we backup it up.
            self.context.run_command_with_retries('cp %s %s' % (uefi, uefi_backup))

    def _install_test_uefi(self, mount_point):
        uefi_path = self.config.vexpress_uefi_path
        uefi = os.path.join(mount_point, uefi_path)
        # FIXME what if self.test_uefi is not set, or points to an unexisting
        # file?
        self.context.run_command_with_retries('cp %s %s' % (self.test_uefi, uefi))


target_class = VexpressTarget
