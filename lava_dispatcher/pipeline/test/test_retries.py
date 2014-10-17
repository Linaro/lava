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
from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    RetryAction,
    DiagnosticAction,
    JobError,
)
from lava_dispatcher.pipeline.job import Job


class TestAction(unittest.TestCase):  # pylint: disable=too-many-public-methods

    class FakeJob(Job):

        def __init__(self, parameters):
            super(TestAction.FakeJob, self).__init__(parameters)

    class FakeDeploy(object):
        """
        Derived from object, *not* Deployment as this confuses python -m unittest discover
        - leads to the FakeDeploy being called instead.
        """
        def __init__(self, parent):
            self.__parameters__ = {}
            self.pipeline = parent
            self.job = parent.job
            self.action = TestAction.CleanupRetryAction()

    class MissingCleanupDeploy(object):

        def __init__(self, parent):
            self.__parameters__ = {}
            self.pipeline = parent
            self.job = parent.job
            self.action = TestAction.InternalRetryAction()

    class FakePipeline(Pipeline):

        def __init__(self, parent=None, job=None):
            super(TestAction.FakePipeline, self).__init__(parent, job)

    class FakeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        def __init__(self):
            super(TestAction.FakeAction, self).__init__()
            self.count = 1
            self.name = "fake-action"
            self.summary = "fake action for unit tests"
            self.description = "fake, do not use outside unit tests"

        def run(self, connection, args=None):
            self.count += 1
            raise JobError("fake error")

    class FakeTriggerAction(Action):
        """
        Always fails, always triggers a diagnostic
        """

        def __init__(self):
            super(TestAction.FakeTriggerAction, self).__init__()
            self.count = 1
            self.name = "trigger-action"
            self.summary = "fake trigger action for unit tests"
            self.description = "fake, do not use outside unit tests"

        def run(self, connection, args=None):
            self.count += 1
            self.job.triggers.append(TestAction.DiagnoseCheck.trigger())
            raise JobError("fake error")

    class FakeRetryAction(RetryAction):

        def __init__(self):
            super(TestAction.FakeRetryAction, self).__init__()
            self.name = "fake-retry-action"
            self.summary = "fake retry action for unit tests"
            self.description = "fake, do not use outside unit tests"

    class InternalRetryAction(RetryAction):

        def __init__(self):
            super(TestAction.InternalRetryAction, self).__init__()
            self.name = "internal-retry-action"
            self.summary = "internal retry action for unit tests"
            self.description = "internal, do not use outside unit tests"

        def populate(self):
            self.internal_pipeline = Pipeline(parent=self, job=self.job)
            self.internal_pipeline.add_action(TestAction.FakeAction())

    class CleanupRetryAction(RetryAction):

        def __init__(self):
            super(TestAction.CleanupRetryAction, self).__init__()
            self.name = "internal-retry-action"
            self.summary = "internal retry action for unit tests"
            self.description = "internal, do not use outside unit tests"

        def populate(self):
            self.internal_pipeline = Pipeline(parent=self, job=self.job)
            self.internal_pipeline.add_action(TestAction.FakeAction())

        def cleanup(self):
            pass

    class DiagnoseCheck(DiagnosticAction):

        def __init__(self):
            super(TestAction.DiagnoseCheck, self).__init__()

        @classmethod
        def trigger(cls):
            return 'fake-check'

    def setUp(self):
        self.parameters = {
            "job_name": "fakejob",
            'output_dir': ".",
            "actions": [
                {
                    'deploy': {
                        'failure_retry': 3
                    },
                    'boot': {
                        'failure_retry': 4
                    },
                    'test': {
                        'failure_retry': 5
                    }
                }
            ]
        }
        self.fakejob = TestAction.FakeJob(self.parameters)

    def lookup_deploy(self, params):
        actions = iter(params)
        while actions:
            action = actions.next()
            if 'deploy' in action:
                yield action['deploy']

    def test_fakeaction_fails_joberror(self):
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        fakepipeline.add_action(TestAction.FakeAction())
        self.assertIsInstance(fakepipeline.actions[0], TestAction.FakeAction)
        with self.assertRaises(JobError):
            # FakeAction is not a RetryAction
            fakepipeline.run_actions(None, None)

    def test_fakeretry_action(self):
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        fakepipeline.add_action(TestAction.FakeRetryAction())
        with self.assertRaises(RuntimeError):
            # first fake retry has no internal pipeline
            self.assertTrue(fakepipeline.validate_actions())

    def test_cleanup_deploy(self):
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        deploy = TestAction.MissingCleanupDeploy(fakepipeline)
        for actions in self.lookup_deploy(self.parameters['actions']):
            deploy.action.parameters = actions
        self.assertEqual(deploy.action.max_retries, 3)
        fakepipeline.add_action(deploy.action)
        self.assertIsNone(fakepipeline.validate_actions())
        fakepipeline.run_actions(None, None)
        self.assertIsNotNone(fakepipeline.errors)

    def test_internal_retry(self):
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        deploy = TestAction.FakeDeploy(fakepipeline)
        for actions in self.lookup_deploy(self.parameters['actions']):
            deploy.action.parameters = actions
        self.assertEqual(deploy.action.max_retries, 3)
        fakepipeline.add_action(deploy.action)
        self.assertIsNone(fakepipeline.validate_actions())
        fakepipeline.run_actions(None, None)
        with self.assertRaises(JobError):
            self.assertIsNotNone(fakepipeline.validate_actions())
        self.assertIsNotNone(fakepipeline.errors)
        # from meliae import scanner
        # scanner.dump_all_objects('filename.json')

    def test_missing_diagnostic(self):
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        fakepipeline.add_action(TestAction.FakeTriggerAction())
        self.assertIsNone(fakepipeline.validate_actions())
        with self.assertRaises(RuntimeError):
            fakepipeline.run_actions(None, None)

    def test_diagnostic(self):
        self.fakejob.diagnostics.append(TestAction.DiagnoseCheck)
        self.assertIn(TestAction.DiagnoseCheck.trigger(), [a.trigger() for a in self.fakejob.diagnostics])
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        fakepipeline.add_action(TestAction.FakeTriggerAction())
        self.assertIsNone(fakepipeline.validate_actions())
        with self.assertRaises(JobError):
            fakepipeline.run_actions(None, None)
