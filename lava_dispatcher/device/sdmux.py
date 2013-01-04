# Copyright (C) 2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
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
import subprocess
import sys
import time

from lava_dispatcher.errors import (
    CriticalError,
)
from lava_dispatcher.device.target import (
    Target
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
    connect_to_serial,
    ensure_directory,
    extract_targz,
    logging_system,
)


class SDMuxTarget(Target):
    """
    This adds support for the "sd mux" device. An SD-MUX device is a piece of
    hardware that allows the host and target to both connect to the same SD
    card. The control of the SD card can then be toggled between the target
    and host via software. The schematics and pictures of this device can be
    found at:
      http://people.linaro.org/~doanac/sdmux/

    Documentation for setting this up is located under doc/sdmux.rst
    """

    def __init__(self, context, config):
        super(SDMuxTarget, self).__init__(context, config)

        self.proc = None

        if not config.sdmux_id:
            raise CriticalError('Device config requires "sdmux_id"')
        if not config.power_on_cmd:
            raise CriticalError('Device config requires "power_on_cmd"')
        if not config.power_off_cmd:
            raise CriticalError('Device config requires "power_off_cmd"')

        if config.pre_connect_command:
            logging_system(config.pre_connect_command)

    def deploy_linaro(self, hwpack=None, rootfs=None):
        img = generate_image(self, hwpack, rootfs, self.scratch_dir)
        self._customize_linux(img)
        self._write_image(img)

    def deploy_linaro_prebuilt(self, image):
        img = download_image(image, self.context)
        self._customize_linux(img)
        self._write_image(img)

    def _customize_android(self, img):
        sys_part = self.config.sys_part_android_org
        with image_partition_mounted(img, sys_part) as d:
            with open('%s/etc/mkshrc' % d, 'a') as f:
                f.write('\n# LAVA CUSTOMIZATIONS\n')
                f.write('PS1="%s"\n' % self.ANDROID_TESTER_PS1)
        self.deployment_data = Target.android_deployment_data

    def deploy_android(self, boot, system, data):
        scratch = self.scratch_dir
        boot = download_image(boot, self.context, scratch, decompress=False)
        data = download_image(data, self.context, scratch, decompress=False)
        system = download_image(system, self.context, scratch, decompress=False)

        img = os.path.join(scratch, 'android.img')
        device_type = self.config.lmc_dev_arg
        generate_android_image(device_type, boot, data, system, img)
        self._customize_android(img)
        self._write_image(img)

    def _as_chunks(self, fname, bsize):
        with open(fname, 'r') as fd:
            while True:
                data = fd.read(bsize)
                if not data:
                    break
                yield data

    def _write_image(self, image):
        with self.mux_device() as device:
            logging.info("dd'ing image to device (%s)", device)
            with open(device, 'w') as of:
                written = 0
                size = os.path.getsize(image)
                # 4M chunks work well for SD cards
                for chunk in self._as_chunks(image, 4 << 20):
                    of.write(chunk)
                    written += len(chunk)
                    if written % (20 * (4 << 20)) == 0:  # only log every 80MB
                        logging.info("wrote %d of %d bytes", written, size)
                logging.info('closing %s, could take a while...', device)

    @contextlib.contextmanager
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
        muxid = self.config.sdmux_id
        source_dir = os.path.abspath(os.path.dirname(__file__))
        muxscript = os.path.join(source_dir, 'sdmux.sh')

        self.power_off(self.proc)
        self.proc = None

        try:
            deventry = subprocess.check_output([muxscript, '-d', muxid, 'on'])
            deventry = deventry.strip()
            logging.info('returning sdmux device as: %s', deventry)
            yield deventry
        except subprocess.CalledProcessError:
            raise CriticalError('Unable to access sdmux device')
        finally:
            logging.info('powering off sdmux')
            subprocess.check_call([muxscript, '-d', muxid, 'off'])

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        """
        This works in cojunction with the "mux_device" function to safely
        access a partition/directory on the sdmux filesystem
        """
        mntdir = os.path.join(self.scratch_dir, 'sdmux_mnt')
        if not os.path.exists(mntdir):
            os.mkdir(mntdir)

        with self.mux_device() as device:
            device = '%s%s' % (device, partition)
            try:
                subprocess.check_call(['mount', device, mntdir])
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
            except:
                logging.exception('Error accessing sdmux filesystem')
                raise CriticalError('Error accessing sdmux filesystem')
            finally:
                logging.info('unmounting sdmux')
                try:
                    subprocess.check_call(['umount', device])
                except subprocess.CalledProcessError:
                    logging.exception('umount failed, re-try in 5 seconds')
                    time.sleep(5)
                    if subprocess.call(['umount', device]) == 0:
                        logging.error(
                            'Unable to unmount sdmux device %s', device)

    def extract_tarball(self, tarball_url, partition, directory='/'):
        logging.info('extracting %s to target', tarball_url)
        with self.file_system(partition, directory) as mntdir:
            tb = download_image(tarball_url, self.context, decompress=False)
            extract_targz(tb, '%s/%s' % (mntdir, directory))

    def power_off(self, proc):
        super(SDMuxTarget, self).power_off(proc)
        logging_system(self.config.power_off_cmd)

    def power_on(self):
        self.proc = connect_to_serial(self.config, self.sio)

        logging.info('powering on')
        logging_system(self.config.power_on_cmd)

        return self.proc

    def get_device_version(self):
        return self.config.sdmux_version

target_class = SDMuxTarget
