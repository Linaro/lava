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
from lava_dispatcher.config import get_device_config
#from lava_dispatcher.config import get_config, get_device_config

# remove when tests are working again.
# flake8: noqa

__tmp_dir = os.getenv("TMPDIR") or '/tmp'
__tmp_config_dir = os.path.join(__tmp_dir, 'lava-dispatcher-config')


def create_config(name, data):
    filename = os.path.join(__tmp_config_dir, name)
    if not os.path.exists(os.path.dirname(filename)):
        os.mkdir(os.path.dirname(filename))
    with open(filename, 'w') as f:
        for key in data.keys():
            f.write("%s = %s\n" % (key, data[key]))


def create_device_config(name, data):
    create_config("devices/%s.conf" % name, data)
    # noinspection PyArgumentList
    return get_device_config(name, __tmp_config_dir)


def setup_config_dir():
    os.mkdir(__tmp_config_dir)


def cleanup_config_dir():
    os.system('rm -rf %s' % __tmp_config_dir)

from unittest import TestCase


class LavaDispatcherTestCase(TestCase):

    def setUp(self):
        setup_config_dir()

    def tearDown(self):
        cleanup_config_dir()
