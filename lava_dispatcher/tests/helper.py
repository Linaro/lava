# Copyright (C) 2012 Linaro Limited
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

import os
from lava_dispatcher import utils
from unittest import TestCase
from lava_dispatcher.config import get_device_config
import lava_dispatcher.config

tmp_dir = os.getenv("TMPDIR") or '/tmp'
tmp_config_dir = os.path.join(tmp_dir, 'lava-dispatcher-config')


def create_config(name, data):
    filename = os.path.join(tmp_config_dir, name)
    if not os.path.exists(os.path.dirname(filename)):
        utils.ensure_directory(os.path.dirname(filename))
    with open(filename, 'w') as f:
        for key in data.keys():
            f.write("%s = %s\n" % (key, data[key]))


def create_device_config(name, data):
    create_config("devices/%s.conf" % name, data)
    lava_dispatcher.config.custom_config_path = tmp_config_dir
    config = get_device_config(name)
    return config


def setup_config_dir():
    utils.ensure_directory(tmp_config_dir)


def cleanup_config_dir():
    if os.path.exists(tmp_config_dir):
        os.system('rm -rf %s' % tmp_config_dir)


class LavaDispatcherTestCase(TestCase):

    def setUp(self):
        cleanup_config_dir()  # clean up after a possibly failed test.
        setup_config_dir()
        self.config_dir = tmp_config_dir
        lava_dispatcher.config.custom_config_path = tmp_config_dir

    def tearDown(self):
        lava_dispatcher.config.custom_config_path = None
        cleanup_config_dir()
