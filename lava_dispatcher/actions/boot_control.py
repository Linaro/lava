#!/usr/bin/python

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

import logging

from lava_dispatcher.actions import BaseAction
from lava_dispatcher.client.base import CriticalError

class cmd_boot_linaro_android_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        client = self.client
        try:
            client.boot_linaro_android_image()
        except Exception as e:
            logging.exception("boot_linaro_android_image failed: %s" % e)
            raise CriticalError("Failed to boot test image.")

class cmd_boot_linaro_image(BaseAction):
    """ Call client code to boot to the test image
    """
    def run(self):
        client = self.client
        status = 'pass'
        try:
            client.boot_linaro_image()
        except:
            logging.exception("boot_linaro_image failed")
            status = 'fail'
            raise CriticalError("Failed to boot test image.")
        finally:
            self.context.test_data.add_result("boot_image", status)


class cmd_boot_master_image(BaseAction):
    """ Call client code to boot to the master image
    """
    def run(self):
        client = self.client
        client.boot_master_image()
