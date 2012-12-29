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
    generate_image,
)
from lava_dispatcher.downloader import (
    download_image,
)
from lava_dispatcher.utils import (
    connect_to_serial,
    ensure_directory,
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
    """

    def __init__(self, context, config):
        super(SDMuxTarget, self).__init__(context, config)

        self.proc = None

        if config.pre_connect_command:
            logging_system(config.pre_connect_command)

    def _deploy(self, img):
        self._customize_linux(img)
        self._write_image(img)

    def deploy_linaro(self, hwpack=None, rootfs=None):
        img = generate_image(self, hwpack, rootfs, self.scratch_dir)
        self._deploy(img)

    def deploy_linaro_prebuilt(self, image):
        img = download_image(image, self.context)
        self._deploy(img)

    @staticmethod
    def _file_size(fd):
        fd.seek(0, 2)
        size = fd.tell()
        fd.seek(0)
        return size

    @staticmethod
    def _write_status(written, size):
        # only update every 40MB so we don't overflow the logfile/stdout with
        # status updates
        chunk = 40 << 20
        if written % chunk == 0:
            sys.stdout.write("\r wrote %d of %s bytes" % (written, size))
            sys.stdout.flush()
        if written == size:
            sys.stdout.write('\n')

    def _as_chunks(self, fname, bsize):
        with open(fname, 'r') as fd:
            size = self._file_size(fd)
            while True:
                data = fd.read(bsize)
                if not data:
                    break
                yield data, size

    def _write_image(self, image):
        with self.mux_device() as device:
            logging.info("dd'ing image to device (%s)", device)
            with open(device, 'w') as of:
                written = 0
                # 4M chunks work well for SD cards
                for chunk, fsize in self._as_chunks(image, 4 << 20):
                    of.write(chunk)
                    written += len(chunk)
                    self._write_status(written, fsize)
                logging.info('closing %s, could take a while...', device)

    @contextlib.contextmanager
    def mux_device(self):
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
