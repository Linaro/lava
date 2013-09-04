# Copyright (C) 2013 Linaro Limited
#
# Author: Dave Pigott <dave.pigott@linaro.org>
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
import lava_dispatcher.actions.lmp.ethsata as ethsata
import lava_dispatcher.actions.lmp.hdmi as hdmi

from lava_dispatcher.actions import BaseAction, null_or_empty_schema
from lava_dispatcher.errors import (
    CriticalError,
)


class cmd_ethsata(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'connect': {'default': True, 'optional': False},
        'additionalProperties': False,
        }
    }

    def run(self, connect=True):
        lmp_id = self.client.config.ethsata_id
        if connect:
            ethsata.passthru(lmp_id)
        else:
            ethsata.disconnect(lmp_id)


class cmd_hdmi(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'connect': {'default': True, 'optional': False},
        'additionalProperties': False,
        }
    }

    def run(self, connect=True):
        lmp_id = self.client.config.hdmi_id
        if connect:
            hdmi.passthru(lmp_id)
        else:
            ethsata.disconnect(lmp_id)
