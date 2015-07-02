# Copyright (C) 2014 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
# Derived From: dummy_drivers.py
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


import logging
import subprocess
import os

from contextlib import contextmanager
from time import sleep
from lava_dispatcher.utils import finalize_process
from lava_dispatcher.errors import CriticalError
from lava_dispatcher.downloader import download_image
from lava_dispatcher.utils import (
    mkdtemp,
    connect_to_serial,
    extract_ramdisk,
    extract_overlay,
    create_ramdisk,
    append_dtb,
    prepend_blob,
    create_multi_image,
    create_uimage,
    create_fat_boot_image,
    create_boot_image,
    create_dt_image,
)


def _call(context, cmd, ignore_failure, timeout):
    cmd = 'timeout -s SIGKILL ' + str(timeout) + 's ' + cmd
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
        try:
            # First we try a gentle reset
            self.device.adb(self.device.config.soft_boot_cmd)
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
            logging.info("Waiting for 10 seconds for connection to settle")
            sleep(10)
            self('getvar all', timeout=2)
            return True
        except subprocess.CalledProcessError:
            return False

    def erase(self, partition):
        self('erase %s' % partition)

    def format(self, partition):
        self('format %s' % partition)

    def flash(self, partition, image):
        self('flash %s %s' % (partition, image))

    def boot(self, image):
        # We need an extra bootloader reboot before actually booting the image
        # to avoid the phone entering charging mode and getting stuck.
        self('reboot')
        # specifically after `fastboot reset`, we have to wait a little
        sleep(10)
        self('boot %s' % image)


class BaseDriver(object):

    def __init__(self, device):
        self.device = device
        self.context = device.context
        self.config = device.config
        self.target_type = None
        self.scratch_dir = None
        self.fastboot = FastBoot(self)
        self._default_boot_cmds = None
        self._boot_tags = {}
        self._kernel = None
        self._ramdisk = None
        self._dtb = None
        self._working_dir = None
        self.__boot_image__ = None

    # Public Methods

    def connect(self):
        """
        """
        raise NotImplementedError("connect")

    def enter_fastboot(self):
        """
        """
        raise NotImplementedError("enter_fastboot")

    def erase_boot(self):
        self.fastboot.erase('boot')

    def get_default_boot_cmds(self):
        return self._default_boot_cmds

    def get_boot_tags(self):
        return self._boot_tags

    def boot(self, boot_cmds=None):
        logging.info("In Base Class boot()")
        if self.__boot_image__ is None:
            raise CriticalError('Deploy action must be run first')
        if self._kernel is not None:
            if self._ramdisk is not None:
                if self.config.fastboot_kernel_load_addr:
                    boot_cmds = ''.join(boot_cmds)
                    self.fastboot('boot -c "%s" -b %s %s %s' % (boot_cmds,
                                                                self.config.fastboot_kernel_load_addr,
                                                                self._kernel, self._ramdisk), timeout=10)
                else:
                    raise CriticalError('Kernel load address not defined!')
            else:
                if self.config.fastboot_kernel_load_addr:
                    boot_cmds = ''.join(boot_cmds)
                    self.fastboot('boot -c "%s" -b %s %s' % (boot_cmds,
                                                             self.config.fastboot_kernel_load_addr,
                                                             self._kernel), timeout=10)
                else:
                    raise CriticalError('Kernel load address not defined!')
        else:
            self.fastboot.boot(self.__boot_image__)

    def wait_for_adb(self):
        if self.target_type == 'android':
            self.adb('wait-for-device')
            return True
        else:
            return False

    def in_fastboot(self):
        if self.fastboot.on():
            logging.debug("Device is in fastboot mode - no need to hard reset")
            return True
        else:
            return False

    def finalize(self, proc):
        finalize_process(proc)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs,
                             image, bootloader, firmware, bl0, bl1, bl2, bl31,
                             rootfstype, bootloadertype, target_type, scratch_dir,
                             qemu_pflash=None):
        self.target_type = target_type
        self.scratch_dir = scratch_dir
        if kernel is not None:
            self._kernel = download_image(kernel, self.context,
                                          self._working_dir,
                                          decompress=False)
            if self.config.prepend_blob:
                blob = self._get_image(self.config.prepend_blob)
                self._kernel = prepend_blob(self._kernel,
                                            blob,
                                            self.working_dir)
            self._boot_tags['{SERVER_IP}'] = self.context.config.lava_server_ip
            self._boot_tags['{KERNEL}'] = os.path.basename(self._kernel)
            self._default_boot_cmds = 'boot_cmds_ramdisk'
        else:
            raise CriticalError('A kernel image is required!')
        if ramdisk is not None:
            self._ramdisk = download_image(ramdisk, self.context,
                                           self._working_dir,
                                           decompress=False)
            if overlays is not None:
                ramdisk_dir = extract_ramdisk(self._ramdisk, self.working_dir,
                                              is_uboot=False)
                for overlay in overlays:
                    overlay = download_image(overlay, self.context,
                                             self._working_dir,
                                             decompress=False)
                    extract_overlay(overlay, ramdisk_dir)
                self._ramdisk = create_ramdisk(ramdisk_dir, self.working_dir)
            self._boot_tags['{RAMDISK}'] = os.path.basename(self._ramdisk)
        if dtb is not None:
            self._dtb = download_image(dtb, self.context,
                                       self._working_dir,
                                       decompress=False)
            if self.config.append_dtb:
                self._kernel = append_dtb(self._kernel, self._dtb, self.working_dir)
                logging.info('Appended dtb to kernel image successfully')
            self._boot_tags['{DTB}'] = os.path.basename(self._dtb)
        if rootfs is not None:
            self._default_boot_cmds = 'boot_cmds_rootfs'
            rootfs = self._get_image(rootfs)
            self.fastboot.flash(self.config.rootfs_partition, rootfs)
        if self.config.multi_image_only:
            if self.config.fastboot_kernel_load_addr:
                if self.config.text_offset:
                    load_addr = self.config.text_offset
                else:
                    load_addr = self.config.fastboot_kernel_load_addr
                if self._ramdisk:
                    self._kernel = create_multi_image(self._kernel,
                                                      self._ramdisk,
                                                      load_addr,
                                                      self.working_dir)
                else:
                    self._kernel = create_uimage(self._kernel,
                                                 load_addr,
                                                 self.working_dir,
                                                 self.config.uimage_xip)
            else:
                raise CriticalError('Kernel load address not defined!')
        elif self.config.boot_fat_image_only:
            if self.config.fastboot_efi_image:
                efi = download_image(self.config.fastboot_efi_image, self.context,
                                     self._working_dir, decompress=False)
                self._kernel = create_fat_boot_image(self._kernel,
                                                     self.working_dir,
                                                     efi,
                                                     self._ramdisk,
                                                     self._dtb)
            else:
                raise CriticalError("No fastboot image provided")

        self.__boot_image__ = 'kernel'

    def deploy_android(self, images, rootfstype,
                       bootloadertype, target_type, scratch_dir):
        self.target_type = target_type
        self.scratch_dir = scratch_dir
        self.erase_boot()
        boot = None

        for image in images:
            if 'fastboot' in image:
                for command in image['fastboot']:
                    self.fastboot(command)
            if 'url' in image and 'partition' in image:
                if image['partition'] == 'boot':
                    boot = image['url']
                else:
                    self.fastboot.flash(image['partition'], self._get_image(image['url']))

        if boot is not None:
            boot = self._get_image(boot)
        else:
            raise CriticalError('A boot image is required!')

        self.__boot_image__ = boot

    def adb(self, args, ignore_failure=False, spawn=False, timeout=600):
        cmd = self.config.adb_command + ' ' + args
        if spawn:
            return self.context.spawn(cmd, timeout=60)
        else:
            _call(self.context, cmd, ignore_failure, timeout)

    def dummy_deploy(self, target_type, scratch_dir):
        self.target_type = target_type
        self.__boot_image__ = target_type
        self.scratch_dir = scratch_dir
        self.adb("shell rm -rf %s" % self.device.lava_test_dir, ignore_failure=True)

    @property
    def working_dir(self):
        if self.config.shared_working_directory is None or \
                self.config.shared_working_directory.strip() == '':
            return self.scratch_dir

        if self._working_dir is None:
            self._working_dir = mkdtemp(self.config.shared_working_directory)
        return self._working_dir

    @contextmanager
    def adb_file_system(self, partition, directory):

        mount_point = self._get_partition_mount_point(partition)

        host_dir = '%s/mnt/%s' % (self.working_dir, directory)
        target_dir = '%s/%s' % (mount_point, directory)

        subprocess.check_call(['mkdir', '-p', host_dir])
        self.adb('pull %s %s' % (target_dir, host_dir), ignore_failure=True)

        yield host_dir

        self.adb('push %s %s' % (host_dir, target_dir))

    # Private Methods

    def _get_image(self, url):
        sdir = self.working_dir
        image = download_image(url, self.context, sdir, decompress=True)
        return image

    def _get_partition_mount_point(self, partition):
        lookup = {
            self.config.data_part_android_org: '/data',
            self.config.sys_part_android_org: '/system',
        }
        return lookup[partition]


class fastboot(BaseDriver):

    def __init__(self, device):
        super(fastboot, self).__init__(device)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs,
                             image, bootloader, firmware, bl0, bl1, bl2, bl31,
                             rootfstype, bootloadertype, target_type, scratch_dir,
                             qemu_pflash=None):
        raise CriticalError('This platform does not support kernel deployment!')

    def enter_fastboot(self):
        self.fastboot.enter()

    def connect(self):
        if self.wait_for_adb():
            proc = self.adb('shell', spawn=True)
        else:
            raise CriticalError('This device only supports Android!')

        return proc


class nexus10(fastboot):

    def __init__(self, device):
        super(nexus10, self).__init__(device)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs,
                             image, bootloader, firmware, bl0, bl1, bl2, bl31, rootfstype,
                             bootloadertype, target_type, scratch_dir, qemu_pflash=None):
        raise CriticalError('This platform does not support kernel deployment!')

    def boot(self, boot_cmds=None):
        self.fastboot.flash('boot', self.__boot_image__)
        self.fastboot('reboot')


class tshark(fastboot):

    def __init__(self, device):
        super(tshark, self).__init__(device)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs,
                             image, bootloader, firmware, bl0, bl1, bl2, bl31, rootfstype,
                             bootloadertype, target_type, scratch_dir, qemu_pflash=None):
        raise CriticalError('This platform does not support kernel deployment!')

    def boot(self, boot_cmds=None):
        self.fastboot.flash('boot', self.__boot_image__)
        self.fastboot('reboot')

    def erase_boot(self):
        pass


class samsung_note(fastboot):

    def __init__(self, device):
        super(samsung_note, self).__init__(device)
        self._isbooted = True

    def boot(self, boot_cmds=None):
        pass

    def erase_boot(self):
        pass

    def on(self):
        return True

    def in_fastboot(self):
        return False

    def _get_partition_mount_point(self, partition):
        lookup = {
            self.config.data_part_android_org: '/data',
            self.config.sys_part_android_org: '/system',
        }
        return lookup[partition]

    def connect(self):
        if self.wait_for_adb():
            logging.debug("Waiting 30 seconds for OS to properly come up")
            sleep(30)
            proc = self.adb('shell', spawn=True)
        else:
            raise CriticalError('This device only supports Android!')

        return proc


class fastboot_serial(BaseDriver):

    def __init__(self, device):
        super(fastboot_serial, self).__init__(device)

    def enter_fastboot(self):
        self.fastboot.enter()

    def connect(self):
        if self.config.connection_command:
            proc = connect_to_serial(self.context)
        else:
            raise CriticalError('The connection_command is not defined!')

        return proc


class capri(fastboot_serial):

    def __init__(self, device):
        super(capri, self).__init__(device)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs,
                             image, bootloader, firmware, bl0, bl1, bl2, bl31, rootfstype,
                             bootloadertype, target_type, scratch_dir, qemu_pflash=None):
        raise CriticalError('This platform does not support kernel deployment!')

    def erase_boot(self):
        pass

    def boot(self, boot_cmds=None):
        self.fastboot.flash('boot', self.__boot_image__)
        self.fastboot('reboot')


class optimusa80(fastboot_serial):

    def __init__(self, device):
        super(optimusa80, self).__init__(device)

    def erase_boot(self):
        pass

    def boot(self, boot_cmds=None):
        if self.__boot_image__ is None:
            raise CriticalError('Deploy action must be run first')
        if self._kernel is not None:
            self.fastboot('flash recovery %s' % self._kernel)
            self.fastboot('reboot')
        else:
            self.fastboot.flash('boot', self.__boot_image__)
            self.fastboot('reboot')

    def in_fastboot(self):
        return False


class pxa1928dkb(fastboot_serial):

    def __init__(self, device):
        super(pxa1928dkb, self).__init__(device)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs,
                             image, bootloader, firmware, bl0, bl1, bl2, bl31, rootfstype,
                             bootloadertype, target_type, scratch_dir, qemu_pflash=None):
        raise CriticalError('This platform does not support kernel deployment!')

    def connect(self):
        if self.config.connection_command:
            proc = connect_to_serial(self.context)
        else:
            raise CriticalError('The connection_command is not defined!')

        return proc

    def erase_boot(self):
        pass

    def boot(self, boot_cmds=None):
        self.fastboot.flash('boot', self.__boot_image__)
        self.fastboot('reboot')


class k3v2(fastboot_serial):

    def __init__(self, device):
        super(k3v2, self).__init__(device)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs,
                             image, bootloader, firmware, bl0, bl1, bl2, bl31, rootfstype,
                             bootloadertype, target_type, scratch_dir, qemu_pflash=None):
        raise CriticalError('This platform does not support kernel deployment!')

    def enter_fastboot(self):
        self.fastboot.enter()
        # Need to sleep and wait for the first stage bootloaders to initialize.
        sleep(10)

    def boot(self, boot_cmds=None):
        self.fastboot.flash('boot', self.__boot_image__)
        self.fastboot('reboot')


class hi6220_hikey(fastboot_serial):

    def __init__(self, device):
        super(hi6220_hikey, self).__init__(device)

    def connect(self):
        if self.config.connection_command:
            proc = connect_to_serial(self.context)
        else:
            raise CriticalError('The connection_command is not defined!')

        return proc

    def erase_boot(self):
        pass

    def boot(self, boot_cmds=None):
        if self.__boot_image__ is None:
            raise CriticalError('Deploy action must be run first')
        if self._kernel is not None:
            self.fastboot.flash('boot', self._kernel)
            self.fastboot('reboot-bootloader', ignore_failure=True)
        else:
            self.fastboot.flash('boot', self.__boot_image__)
            self.fastboot('reboot-bootloader', ignore_failure=True)


class apq8016_sbc(fastboot_serial):

    def __init__(self, device):
        super(apq8016_sbc, self).__init__(device)

    def connect(self):
        if self.config.connection_command:
            proc = connect_to_serial(self.context)
        else:
            raise CriticalError('The connection_command is not defined!')

        return proc

    def erase_boot(self):
        pass

    def boot(self, boot_cmds=None):
        if self.__boot_image__ is None:
            raise CriticalError('Deploy action must be run first')
        if self._kernel is not None:
            if self.config.mkbootimg_binary:
                if self.config.dtbtool_binary:
                    if self.config.fastboot_kernel_load_addr:
                        self._dtb = create_dt_image(self.config.dtbtool_binary,
                                                    self._dtb, self.working_dir)
                        boot_cmds = ''.join(boot_cmds)
                        self._kernel = create_boot_image(self.config.mkbootimg_binary,
                                                         self._kernel,
                                                         self._ramdisk,
                                                         self._dtb,
                                                         self.config.fastboot_kernel_load_addr,
                                                         boot_cmds,
                                                         self.working_dir)
                    else:
                        raise CriticalError('Kernel load address not defined!')
                else:
                    raise CriticalError('No dtbtool binary set')
            else:
                raise CriticalError('No mkbootimg binary set')
            self.fastboot.boot(self._kernel)
        else:
            self.fastboot.boot(self.__boot_image__)
