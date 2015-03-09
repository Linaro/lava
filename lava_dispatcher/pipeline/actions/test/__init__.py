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

from lava_dispatcher.pipeline.action import (
    Action,
    JobError,
)
from lava_dispatcher.pipeline.logical import (
    LavaTest,
    RetryAction,
)


def handle_testcase(params):

    # FIXME: move to utils
    data = {}
    for param in params:
        parts = param.split('=')
        if len(parts) == 2:
            key, value = parts
            key = key.lower()
            data[key] = value
        else:
            raise JobError(
                "Ignoring malformed parameter for signal: \"%s\". " % param)
    return data


class TestAction(Action):
    """
    Base class for all actions which run lava test
    cases on a device under test.
    The subclass selected to do the work will be the
    subclass returning True in the accepts(device, image)
    function.
    Each new subclass needs a unit test to ensure it is
    reliably selected for the correct deployment and not
    selected for an invalid deployment or a deployment
    accepted by a different subclass.
    """

    name = 'test'
