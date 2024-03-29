# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.logical import RetryAction

from .test_basic import LavaDispatcherTestCase


class TestRepeatAction(LavaDispatcherTestCase):
    def test_repeat_action(self):
        class DummyAction(Action):
            # pylint: disable=no-self-argument
            def __init__(self_):
                super().__init__()
                self_.ran = 0

            def run(self_, connection, max_end_time):
                self.assertIsNone(connection)
                self_.ran += 1

        ra = RetryAction()
        ra.parameters = {"repeat": 5}
        ra.level = "1"
        ra.pipeline = Pipeline(job=self.create_simple_job(), parent=ra)
        ra.pipeline.add_action(DummyAction())
        with ra.pipeline.job.timeout(None, None) as max_end_time:
            ra.run(None, max_end_time)
        self.assertEqual(
            ra.pipeline.actions[0].ran,
            5,
        )
