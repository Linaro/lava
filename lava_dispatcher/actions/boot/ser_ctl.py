# Copyright 2020 NXP
#
# Author: Larry Shen <larry.shen@nxp.com>
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

from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import BootHasMixin
from lava_dispatcher.connections.serial import ConnectDevice, DisconnectDevice
from lava_dispatcher.logical import Boot, RetryAction


class SerCtlBoot(Boot):

    compatibility = 1

    @classmethod
    def action(cls):
        return SerCtl()

    @classmethod
    def accepts(cls, device, parameters):
        if "method" not in parameters:
            return False, '"method" was not in parameters'
        if parameters["method"] != "ser_ctl":
            return False, '"method" was not "ser_ctl"'
        if parameters.get("action", "close") not in ("close", "open"):
            return False, '"action" should be "close" or "open"'
        return True, "accepted"


class SerCtl(BootHasMixin, RetryAction):

    name = "ser-ctl"
    description = "control serial open/close"
    summary = "control serial open or close"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if parameters.get("action", "close") == "close":
            self.pipeline.add_action(DisconnectDevice())
        else:
            self.pipeline.add_action(ConnectDevice())
