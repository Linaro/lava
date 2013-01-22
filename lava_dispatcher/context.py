# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
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

import atexit
import os
import sys
import tempfile

from lava_dispatcher.config import get_device_config
from lava_dispatcher.client.targetdevice import TargetBasedClient
from lava_dispatcher.test_data import LavaTestData
from lava_dispatcher.utils import rmtree


class LavaContext(object):
    def __init__(self, target, dispatcher_config, oob_file, job_data):
        self.config = dispatcher_config
        self.job_data = job_data
        # This is the file-like object to send serial output from the device
        # to.  We just send it to stdout for now, but soon we'll do something
        # cleverer.
        self.logfile_read = sys.stdout
        device_config = get_device_config(
            target, dispatcher_config.config_dir)
        self._client = TargetBasedClient(self, device_config)
        self.test_data = LavaTestData()
        self.oob_file = oob_file
        self._host_result_dir = None
        self.any_device_bundles = False

    @property
    def client(self):
        return self._client

    @property
    def any_host_bundles(self):
        return (self._host_result_dir is not None
                and len(os.listdir(self._host_result_dir)) > 0)

    @property
    def host_result_dir(self):
        if self._host_result_dir is None:
            self._host_result_dir = tempfile.mkdtemp()
            atexit.register(rmtree, self._host_result_dir)
        return self._host_result_dir

    def get_device_version(self):
        return self.client.target_device.get_device_version()
