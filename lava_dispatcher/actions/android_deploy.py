#!/usr/bin/python

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

from lava_dispatcher.actions import BaseAction
from lava_dispatcher.client.master import LavaMasterImageClient
from lava_dispatcher.client.targetdevice import TargetBasedClient


class cmd_deploy_linaro_android_image(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'boot': {'type': 'string'},
            'system': {'type': 'string'},
            'data': {'type': 'string'},
            'rootfstype': {'type': 'string', 'optional': True, 'default': 'ext4'},
            },
        'additionalProperties': False,
        }

    def run(self, boot, system, data, rootfstype='ext4'):
        if not isinstance(self.client, LavaMasterImageClient) and \
            not isinstance(self.client, TargetBasedClient):
            raise RuntimeError("Invalid LavaClient for this action")
        self.client.deploy_linaro_android(boot, system, data, rootfstype)
