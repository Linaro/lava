# Copyright (C) 2014 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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
import logging
import unittest

from lava_dispatcher.pipeline.log import YamlLogger, get_yaml_handler


class TestLog(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_yaml_logger_init(self):
        log = YamlLogger('fake')
        self.assertEqual(log.name, 'fake')
        self.assertEqual(log.description, 'yaml logger')
        self.assertEqual(log.log.level, logging.DEBUG)

    def test_get_yaml_handler(self):
        handler = get_yaml_handler('fake.log')
        self.assertIsInstance(handler, logging.FileHandler)
        handler = get_yaml_handler()
        self.assertIsInstance(handler, logging.StreamHandler)
        os.unlink('fake.log')
