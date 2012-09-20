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

import os
import tempfile

from lava_dispatcher.config import get_device_config
from lava_dispatcher.client.fastmodel import LavaFastModelClient
from lava_dispatcher.client.master import LavaMasterImageClient
from lava_dispatcher.client.qemu import LavaQEMUClient
from lava_dispatcher.test_data import LavaTestData

available_clients = {
    'master': LavaMasterImageClient,
    'qemu': LavaQEMUClient,
    'fastmodel': LavaFastModelClient,
}

class LavaContext(object):
    def __init__(self, target, dispatcher_config, oob_file, job_data):
        self.config = dispatcher_config
        self.job_data = job_data
        device_config = get_device_config(
            target, dispatcher_config.config_dir)
        self._client = LavaContext.instantiate_client(self, device_config)
        self.test_data = LavaTestData()
        self.oob_file = oob_file
        self._host_result_dir = None
        self.any_device_bundles = False

    @classmethod
    def instantiate_client(cls, context, device_config):
        client_type = device_config.get('client_type')
        client_class = cls.get_client_class(client_type)
        return client_class(context, device_config)

    @classmethod
    def get_client_class(cls, client_type):
        if client_type == 'conmux':
            client_type = 'master'
        try:
            return available_clients[client_type]
        except KeyError as err:
            clients = available_clients.keys()
            types_list = ', '.join(clients[:-1]) + ' and ' + clients[-1]
            raise RuntimeError(
                "this version of lava-dispatcher only supports %s "
                "clients, not %r" % (types_list, client_type))

    @property
    def client(self):
        return self._client

    @property
    def device_version(self):
        return self._client.device_version

    @property
    def lava_server_ip(self):
        return self.config.get("LAVA_SERVER_IP")

    @property
    def lava_proxy(self):
        return self.config.get("LAVA_PROXY", None)

    @property
    def lava_cookies(self):
        return self.config.get("LAVA_COOKIES", None)

    @property
    def lava_image_tmpdir(self):
        return self.config.get("LAVA_IMAGE_TMPDIR")

    @property
    def lava_image_url(self):
        return self.config.get("LAVA_IMAGE_URL")

    @property
    def any_host_bundles(self):
        return (self._host_result_dir is not None
                and len(os.listdir(self._host_result_dir)) > 0)

    @property
    def host_result_dir(self):
        if self._host_result_dir is None:
            self._host_result_dir = tempfile.mkdtemp()
        return self._host_result_dir

    @property
    def lava_result_dir(self):
        return self.config.get("LAVA_RESULT_DIR")

    @property
    def lava_cachedir(self):
        return self.config.get("LAVA_CACHEDIR")
