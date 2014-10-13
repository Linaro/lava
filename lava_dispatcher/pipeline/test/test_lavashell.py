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

import datetime
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.tests.helper import LavaDispatcherTestCase
from lava_dispatcher.pipeline.actions.test.shell import TestShellRetry, TestShellAction


class TestDefinitionHandlers(LavaDispatcherTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionHandlers, self).setUp()
        factory = Factory()
        self.job = factory.create_job('sample_jobs/kvm.yaml', self.config_dir)

    def test_testshell(self):
        testshell = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, TestShellRetry):
                testshell = action.pipeline.children[action.pipeline][0]
                break
        self.assertIsInstance(testshell, TestShellAction)
        self.assertNotIn('boot-result', testshell.data)
        self.assertTrue(testshell.valid)

        time_str = testshell.parameters['timeout'][:-1]
        time_int = int(time_str)
        self.assertEqual(
            datetime.timedelta(minutes=time_int).total_seconds(),
            testshell.timeout.duration
        )

    def test_eventpatterns(self):
        testshell = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, TestShellRetry):
                testshell = action.pipeline.children[action.pipeline][0]
                break
        self.assertTrue(testshell.valid)
        self.assertFalse(testshell.check_patterns('exit', None))
        self.assertFalse(testshell.check_patterns('eof', None))
        self.assertFalse(testshell.check_patterns('timeout', None))
