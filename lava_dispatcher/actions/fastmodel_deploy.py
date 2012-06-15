# Copyright (C) 2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
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
from lava_dispatcher.client.fastmodel import LavaFastModelClient


class cmd_deploy_fastmodel_image(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'image': {'type': 'string', 'optional': False},
            'axf': {'type': 'string', 'optional': False},
            'initrd': {'type': 'string', 'optional': False},
            'kernel': {'type': 'string', 'optional': False},
            'dtb': {'type': 'string', 'optional': False},
            },
        'additionalProperties': False,
        }

    def run(self, image, axf, initrd, kernel, dtb):
        if not isinstance(self.client, LavaFastModelClient):
             raise RuntimeError("Invalid LavaClient for this action")
        self.client.deploy_image(image, axf, initrd, kernel, dtb)
