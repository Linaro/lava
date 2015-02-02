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

import unittest
import datetime
from lava_dispatcher.pipeline.action import Action, Pipeline, JobError, Timeout
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.pipeline.actions.test.shell import TestShellRetry, TestShellAction


# pylint: disable=duplicate-code


class TestDefinitionHandlers(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionHandlers, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm.yaml')

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

        if 'timeout' in testshell.parameters:
            time_int = Timeout.parse(testshell.parameters['timeout'])
        else:
            time_int = Timeout.default_duration()
        self.assertEqual(
            datetime.timedelta(seconds=time_int).total_seconds(),
            testshell.timeout.duration
        )
        self.assertNotEqual(
            testshell.parameters['default_action_timeout'],
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


class TestShellResults(unittest.TestCase):   # pylint: disable=too-many-public-methods

    class FakeJob(Job):

        def __init__(self, parameters):
            super(TestShellResults.FakeJob, self).__init__(parameters)

    class FakeDeploy(object):
        """
        Derived from object, *not* Deployment as this confuses python -m unittest discover
        - leads to the FakeDeploy being called instead.
        """
        def __init__(self, parent):
            self.__parameters__ = {}
            self.pipeline = parent
            self.job = parent.job
            self.action = TestShellResults.FakeAction()

    class FakePipeline(Pipeline):

        def __init__(self, parent=None, job=None):
            super(TestShellResults.FakePipeline, self).__init__(parent, job)

    class FakeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        def __init__(self):
            super(TestShellResults.FakeAction, self).__init__()
            self.count = 1
            self.name = "fake-action"
            self.summary = "fake action for unit tests"
            self.description = "fake, do not use outside unit tests"

        def run(self, connection, args=None):
            self.count += 1
            raise JobError("fake error")
