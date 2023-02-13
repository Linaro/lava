# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
    monkeypatch.setattr(time, "monotonic", lambda: 0)
    ra = RetryAction()
    ra.parameters = {"repeat": 5}
    ra.level = "1"
    ra.pipeline = Pipeline(parent=ra)
    ra.pipeline.add_action(DummyAction())
    ra.run(None, 1)
    assert ra.pipeline.actions[0].ran == 5  # nosec - unit test support.
