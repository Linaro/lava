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

import time

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.logical import RetryAction


class DummyAction(Action):
    def __init__(self):
        super().__init__()
        self.ran = 0

    def run(self, connection, max_end_time):
        assert connection is None  # nosec - unit test support.
        assert max_end_time == 1  # nosec - unit test support.
        self.ran += 1


def test_repeat_action(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 0)
    ra = RetryAction()
    ra.parameters = {"repeat": 5}
    ra.level = "1"
    ra.internal_pipeline = Pipeline(parent=ra)
    ra.internal_pipeline.add_action(DummyAction())
    ra.run(None, 1)
    assert ra.internal_pipeline.actions[0].ran == 5  # nosec - unit test support.
