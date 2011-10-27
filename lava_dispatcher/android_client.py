# Copyright (C) 2011 Linaro Limited
#
# Author: Linaro Validation Team <linaro-dev@lists.linaro.org>
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
from tempfile import mkdtemp

from lava_dispatcher.client import LavaClient


class LavaAndroidClient(LavaClient):
    """
    LavaAndroidClient manipulates the board running Android system, bootup,
    reset, power off the board, sends commands to board to execute
    """

    def __init__(self, context, config):
        LavaClient.__init__(self, context, config)
        # use a random result directory on android for they are using same host
        self.android_result_dir = mkdtemp()
        os.chmod(self.android_result_dir, 0755)

