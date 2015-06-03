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

from lava_dispatcher.pipeline.action import Action


class SubmitResultsAction(Action):

    name = 'submit_results'
    # FIXME: there is no role for a submit action any longer - remove.

    def __init__(self):
        super(SubmitResultsAction, self).__init__()
        self.section = 'submit'

    def validate(self):
        super(SubmitResultsAction, self).validate()
        if 'repeat' in self.parameters:
            self.errors = "%s does not support repeat" % self.name

    def run(self, connection, args=None):
        return connection

    def cleanup(self):
        pass
