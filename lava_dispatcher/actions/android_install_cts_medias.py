# Copyright (C) 2012 Linaro Limited
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
# along with this program; if not, see <http://www.gnu.org/licenses>.

import logging
from lava_dispatcher.actions import BaseAction


class cmd_android_install_cts_medias(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'media_url': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
            'role': {'type': 'string', 'optional': True},
        },
        'additionalProperties': False,
    }

    def run(self, media_url=None, timeout=2400):
        if not media_url:
            media_url = self.client.config.cts_media_url
        if not media_url:
            logging.error("The url for the cts media files is not specified")
            return

        partition = self.client.config.sdcard_part_android_org
        self.client.target_device.extract_tarball(media_url, partition)
