# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

from lava_dispatcher.pipeline import Action


class TestAction(Action):

    name = 'test'

    def __init__(self):
        super(TestAction, self).__init__()

    def validate(self):
        if 'definitions' in self.parameters:
            for testdef in self.parameters['definitions']:
                if 'repository' not in testdef:
                    self.errors = "Repository missing from test definition"

    def run(self, connection, args=None):
        self._log("Loading test definitions")
        return connection
