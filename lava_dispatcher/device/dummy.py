# Copyright (C) 2013 Linaro Limited
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
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import contextlib
import logging
import os

from lava_dispatcher.device.target import Target
import lava_dispatcher.device.dummy_drivers as drivers
from lava_dispatcher.errors import (
    CriticalError,
)


class DummyTarget(Target):

    def __init__(self, context, config):
        super(DummyTarget, self).__init__(context, config)

        driver = self.config.dummy_driver
        if driver is None:
            raise CriticalError(
                "Required configuration entry missing: dummy_driver")

        driver_class = drivers.__getattribute__(driver)

        self.driver = driver_class(self)

    def power_on(self):
        proc = self.driver.connect()
        proc.sendline("")
        proc.sendline('export PS1="%s"' % self.tester_ps1)
        return proc

    def power_off(self, proc):
        super(DummyTarget, self).power_off(proc)
        self.driver.finalize(proc)

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        with self.driver.root() as root:
            logging.debug("Accessing the file system at %s", root)
            dest = root + directory
            if not os.path.exists(dest):
                os.makedirs(dest)
            yield dest


target_class = DummyTarget
