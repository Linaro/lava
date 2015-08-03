# Copyright (C) 2012-2013 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
#         Dave Pigott <dave.pigott@linaro.org>
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
import os
import glob
import subprocess
import time
import lava_dispatcher.actions.lmp.sdmux as sdmux

from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.errors import (
    CriticalError,
    OperationFailed,
)
from lava_dispatcher.client.lmc_utils import (
    generate_android_image,
    generate_image,
    image_partition_mounted,
)
from lava_dispatcher.downloader import (
    download_image,
)
from lava_dispatcher.utils import (
    ensure_directory,
    extract_tar,
    connect_to_serial,
)
from lava_dispatcher import deployment_data


def _flush_files(mntdir):
    """
    calls to umount can fail because the files haven't completely been written
    to disk. This helps make sure that happens and eliminates a warning
    """
    for f in os.listdir('/proc/self/fd'):
        # check for existances since listdir will include an fd for itself
        if os.path.exists(f):
            path = os.path.realpath('/proc/self/fd/%s' % f)
            if path.startswith(mntdir):
                f.flush()
                os.fsync(f.fileno())
                os.close(f.fileno())


class SDMuxTarget(Target):
    """
    This adds support for the "sd mux" device. An SD-MUX device is a piece of
    hardware that allows the host and target to both connect to the same SD
    card. The control of the SD card can then be toggled between the target
    and host via software.
"""

    def __init__(self, context, config):
        super(SDMuxTarget, self).__init__(context, config)

        if not config.sdmux_usb_id:
            raise CriticalError('Device config requires "sdmux_usb_id"')

        if not config.sdmux_id:
            raise CriticalError('Device config requires "sdmux_id"')

        if not config.power_off_cmd:
            raise CriticalError('Device config requires "power_off"')

        if not config.hard_reset_command:
            raise CriticalError('Device config requires "hard_reset_command"')

        if config.pre_connect_command:
            self.context.run_command(config.pre_connect_command)

        self.proc = connect_to_serial(self.context)

    def deploy_linaro(self, hwpack, rootfs, dtb, bootloadertype, rootfstype,
                      bootfstype, qemu_pflash=None):
        img = generate_image(self, hwpack, rootfs, dtb, self.scratch_dir,
                             rootfstype, bootloadertype)
        self.customize_image(img)
        self._write_image(img)

    def deploy_linaro_prebuilt(self, image, dtb, rootfstype, bootfstype,
                               bootloadertype, qemu_pflash=None):
        img = download_image(image, self.context)
        self.customize_image(img)

        self._write_image(img)

    def _customize_android(self, img):
        self.deployment_data = deployment_data.android

        sys_part = self.config.sys_part_android_org
        with image_partition_mounted(img, sys_part) as d:
            with open('%s/etc/mkshrc' % d, 'a') as f:
                f.write('\n# LAVA CUSTOMIZATIONS\n')
                f.write('PS1="%s"\n' % self.tester_ps1)

    def deploy_android(self, images, rootfstype, bootloadertype,
                       target_type):
        scratch = self.scratch_dir

        for image in images:
            if image['partition'] == 'boot':
                boot = download_image(image['url'], self.context, scratch, decompress=False)
            elif image['parition'] == 'system':
                system = download_image(image['url'], self.context, scratch, decompress=False)
            elif image['partition'] == 'userdata':
                data = download_image(image['url'], self.context, scratch, decompress=False)
            else:
                msg = 'Unsupported partition option: %s' % image['partition']
                logging.warning(msg)
                raise CriticalError(msg)

        img = os.path.join(scratch, 'android.img')
        device_type = self.config.lmc_dev_arg
        generate_android_image(self.context, device_type, boot, data, system, img)
        self._customize_android(img)
        self._write_image(img)

    def _write_image(self, image):
        sdmux.dut_disconnect(self.config.sdmux_id)
        sdmux.host_usda(self.config.sdmux_id)

        device = self.mux_device()
        logging.info("dd'ing image to device (%s)", device)
        dd_cmd = 'dd if=%s of=%s bs=4096 conv=fsync' % (image, device)
        dd_proc = subprocess.Popen(dd_cmd, shell=True)
        dd_proc.wait()
        if dd_proc.returncode != 0:
            raise CriticalError("Failed to dd image to device (Error code %d)" % dd_proc.returncode)

        sdmux.host_disconnect(self.config.sdmux_id)

    def _run_boot(self):
        self._enter_bootloader(self.proc)
        boot_cmds = self._load_boot_cmds()
        self._customize_bootloader(self.proc, boot_cmds)
        self._monitor_boot(self.proc, self.tester_ps1, self.tester_ps1_pattern)

    def mux_device(self):
        """
        This function gives us a safe context in which to deal with the
        raw sdmux device. It will ensure that:
          * the target is powered off
          * the proper sdmux USB device is powered on

        It will then yield to the caller a dev entry like /dev/sdb
        This entry can be used safely during this context. Upon exiting,
        the USB device connect to the sdmux will be powered off so that the
        target will be able to safely access it.
        """

        syspath = "/sys/bus/usb/devices/" + self.config.sdmux_usb_id + \
            "/" + self.config.sdmux_usb_id + \
            "*/host*/target*/*:0:0:0/block/*"

        retrycount = 0
        deventry = ""

        while retrycount < self.config.sdmux_mount_retry_seconds:
            device_list = glob.glob(syspath)
            for device in device_list:
                deventry = os.path.join("/dev/", os.path.basename(device))
                break
            if deventry != "":
                break
            time.sleep(1)
            retrycount += 1

        if deventry != "":
            logging.debug('found sdmux device %s: Waiting %ds for any mounts to complete',
                          deventry, self.config.sdmux_mount_wait_seconds)
            time.sleep(self.config.sdmux_mount_wait_seconds)
            logging.debug("Unmounting %s*", deventry)
            os.system("umount %s*" % deventry)
            logging.debug('returning sdmux device as: %s', deventry)
            return deventry
        else:
            raise CriticalError('Unable to access sdmux device')

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        """
        This works in conjunction with the "mux_device" function to safely
        access a partition/directory on the sdmux filesystem
        """
        self.proc.sendline('sync')
        self.proc.expect(self.tester_ps1_pattern)
        logging.info('powering off')
        self.context.run_command(self.config.power_off_cmd)

        sdmux.dut_disconnect(self.config.sdmux_id)
        sdmux.host_usda(self.config.sdmux_id)

        mntdir = os.path.join(self.scratch_dir, 'sdmux_mnt')
        ensure_directory(mntdir)

        device = self.mux_device()
        device = '%s%s' % (device, partition)
        try:
            self.context.run_command(['mount', device, mntdir], failok=False)
            if directory[0] == '/':
                directory = directory[1:]
            path = os.path.join(mntdir, directory)
            ensure_directory(path)
            logging.info('sdmux(%s) mounted at: %s', device, path)
            yield path
        except CriticalError:
            raise
        except subprocess.CalledProcessError:
            raise CriticalError('Unable to access sdmux device')
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            logging.exception('Error accessing sdmux filesystem')
            raise CriticalError('Error accessing sdmux filesystem')
        finally:
            logging.info('unmounting sdmux')
            try:
                _flush_files(mntdir)
                self.context.run_command(['umount', device], failok=False)
            except subprocess.CalledProcessError:
                logging.exception('umount failed, re-try in 10 seconds')
                time.sleep(10)
                if self.context.run_command(['umount', device]) != 0:
                    logging.error(
                        'Unable to unmount sdmux device %s', device)

        sdmux.host_disconnect(self.config.sdmux_id)

    def extract_tarball(self, tarball_url, partition, directory='/'):
        logging.info('extracting %s to target', tarball_url)
        with self.file_system(partition, directory) as mntdir:
            tb = download_image(tarball_url, self.context, decompress=False)
            extract_tar(tb, '%s/%s' % (mntdir, directory))

    def power_off(self, proc):
        logging.info('powering off')
        self.context.run_command(self.config.power_off_cmd)
        sdmux.dut_disconnect(self.config.sdmux_id)

    def power_on(self):
        sdmux.host_disconnect(self.config.sdmux_id)
        sdmux.dut_usda(self.config.sdmux_id)
        logging.info('powering on')

        try:
            self.context.run_command(self.config.hard_reset_command)
            self._run_boot()
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            raise OperationFailed("_run_boot failed")

        return self.proc

    def get_device_version(self):
        return self.config.sdmux_version

target_class = SDMuxTarget
