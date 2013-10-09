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

import logging
import os
import time

from lava_dispatcher.errors import (
    CriticalError,
)
from lava_dispatcher.client.base import (
    LavaClient,
)
from lava_dispatcher.device.target import (
    get_target,
)
from lava_dispatcher.utils import (
    mk_targz,
)


class TargetBasedClient(LavaClient):
    """This is a wrapper around the lava_dispatcher.device.target class that
    provides the additional functionality that's needed by lava-dispatcher
    actions that depend on a LavaClient
    """

    def __init__(self, context, config):
        super(TargetBasedClient, self).__init__(context, config)
        self.target_device = get_target(context, config)

    def deploy_linaro_android(self, boot, system, data, rootfstype):
        self.target_device.deploy_android(boot, system, data, rootfstype)

    def deploy_linaro(self, hwpack, rootfs, image, rootfstype, bootloadertype):
        if image is None:
            if hwpack is None or rootfs is None:
                raise CriticalError(
                    "must specify both hwpack and rootfs \
                     when not specifying image")
        elif hwpack is not None or rootfs is not None:
            raise CriticalError(
                "cannot specify hwpack or rootfs when specifying image")

        if image is None:
            self.target_device.deploy_linaro(hwpack, rootfs,
                                             bootloadertype, rootfstype)
        else:
            self.target_device.deploy_linaro_prebuilt(image, bootloadertype,
                                                      rootfstype)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, rootfs,
                             bootloader, firmware, rootfstype, bootloadertype):
        self.target_device.deploy_linaro_kernel(kernel, ramdisk, dtb, rootfs,
                                                bootloader,
                                                firmware, rootfstype,
                                                bootloadertype)

    def _boot_linaro_image(self):
        if self.proc:
            logging.warning('device already powered on, powering off first')
            self._power_off_device()
        self.proc = self.target_device.power_on()

    def _boot_linaro_android_image(self):
        """Booting android or ubuntu style images don't differ much"""

        logging.info('ensuring ADB port is ready')
        adb_port = self.target_device.config.android_adb_port
        while self.context.run_command("sh -c 'netstat -an | grep %s.*TIME_WAIT'" % adb_port) == 0:
            logging.info("waiting for TIME_WAIT %s socket to finish" % adb_port)
            time.sleep(3)

        self._boot_linaro_image()

    def reliable_session(self):
        return self.tester_session()

    def retrieve_results(self, result_disk):
        self._power_off_device()

        td = self.target_device
        tar = os.path.join(td.scratch_dir, 'lava_results.tgz')
        result_dir = self.context.config.lava_result_dir
        with td.file_system(td.config.root_part, result_dir) as mnt:
            mk_targz(tar, mnt)
        return tar

    def get_test_data_attachments(self):
        '''returns attachments to go in the "lava_results" test run'''
        a = super(TargetBasedClient, self).get_test_data_attachments()
        a.extend(self.target_device.get_test_data_attachments())
        return a

    def finish(self):
        self._power_off_device()

    def _power_off_device(self):
        """
        Powers the associated device off by calling its power_off() method.

        Can be called multiple times, but only the first will be effective, all
        the others will be no-ops (unless the device is powered on again by
        calling one of the _boot* methods).
        """
        if self.proc:
            self.target_device.power_off(self.proc)
            self.proc = None
