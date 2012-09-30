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

from lava_dispatcher.client.base import (
    CriticalError,
    LavaClient,
    )
from lava_dispatcher.device.target import (
    get_target,
    )
from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted,
    )
from lava_dispatcher.utils import (
    logging_system,
    )


class LavaFastModelClient(LavaClient):

    def __init__(self, context, config):
        super(LavaFastModelClient, self).__init__(context, config)
        self.target_device = get_target(context, config)

    def deploy_linaro_android(self, boot, system, data, rootfstype='ext4'):
        self.target_device.deploy_android(boot, system, data)

    def deploy_linaro(self, hwpack=None, rootfs=None, image=None,
                      rootfstype='ext3'):
        if image is None:
            if hwpack is None or rootfs is None:
                raise CriticalError(
                    "must specify both hwpack and rootfs when not specifying image")
        elif hwpack is not None or rootfs is not None:
            raise CriticalError(
                    "cannot specify hwpack or rootfs when specifying image")

        if image is None:
            self.target_device.deploy_linaro(hwpack, rootfs)
        else:
            self.target_device.deploy_linaro_prebuilt(image)

    def _boot_linaro_image(self):
        self.proc = self.target_device.power_on()

    def _boot_linaro_android_image(self):
        ''' booting android or ubuntu style images don't differ much'''

        logging.info('ensuring ADB port is ready')
        while logging_system("sh -c 'netstat -an | grep 5555.*TIME_WAIT'") == 0:
            logging.info("waiting for TIME_WAIT 5555 socket to finish")
            time.sleep(3)

        self._boot_linaro_image()

    def reliable_session(self):
        return self.tester_session()

    def retrieve_results(self, result_disk):
        self.target_device.power_off(self.proc)

        sdimage = self.target_device._sd_image
        tardir = os.path.dirname(sdimage)
        tarfile = os.path.join(tardir, 'lava_results.tgz')
        with image_partition_mounted(sdimage, self.config.root_part) as mnt:
            logging_system(
                'tar czf %s -C %s%s .' % (
                    tarfile, mnt, self.context.lava_result_dir))
        return 'pass', '', tarfile

    def get_test_data_attachments(self):
        '''returns attachments to go in the "lava_results" test run'''
        a = super(LavaFastModelClient, self).get_test_data_attachments()
        a.extend(self.target_device.get_test_data_attachments())
        return a
