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
from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    Timeout,
    JobError,
)
from lava_dispatcher.pipeline.logical import (
    AdjuvantAction,
    RetryAction,
    DiagnosticAction,
)
from lava_dispatcher.pipeline.power import FinalizeAction
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.test.test_basic import StdoutTestCase


# pylint: disable=too-few-public-methods

class DummyLogger(object):
    def info(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def results(self, *args, **kwargs):
        pass


class TestAction(StdoutTestCase):  # pylint: disable=too-many-public-methods

    class FakeJob(Job):

        def __init__(self, parameters):
            super(TestAction.FakeJob, self).__init__(4212, parameters, None)

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
            self.action.job = self.job

    class MissingCleanupDeploy(object):

        def __init__(self, parent):
            self.__parameters__ = {}
            self.pipeline = parent
            self.job = parent.job
            self.action = TestAction.InternalRetryAction()
            self.action.job = self.job

    class FakePipeline(Pipeline):

        def __init__(self, parent=None, job=None):
            super(TestAction.FakePipeline, self).__init__(parent, job)
            job.pipeline = self

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

        def run(self, connection, max_end_time, args=None):
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
            self.section = 'internal'
            self.summary = "fake trigger action for unit tests"
            self.description = "fake, do not use outside unit tests"

        def run(self, connection, max_end_time, args=None):
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
            self.section = 'internal'
            self.summary = "internal retry action for unit tests"
            self.description = "internal, do not use outside unit tests"

        def populate(self, parameters):
            self.internal_pipeline = Pipeline(parent=self, job=self.job)
            self.internal_pipeline.add_action(TestAction.FakeAction(), parameters)

    class CleanupRetryAction(RetryAction):

        def __init__(self):
            super(TestAction.CleanupRetryAction, self).__init__()
            self.name = "internal-retry-action"
            self.section = 'internal'
            self.summary = "internal retry action for unit tests"
            self.description = "internal, do not use outside unit tests"

        def populate(self, parameters):
            self.internal_pipeline = Pipeline(parent=self, job=self.job)
            self.internal_pipeline.add_action(TestAction.FakeAction(), parameters)

        def cleanup(self, connection):
            pass

    class DiagnoseCheck(DiagnosticAction):

        def __init__(self):
            super(TestAction.DiagnoseCheck, self).__init__()

        @classmethod
        def trigger(cls):
            return 'fake-check'

    def setUp(self):
        super(TestAction, self).setUp()
        self.parameters = {
            "job_name": "fakejob",
            'output_dir': mkdtemp(),
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

    def lookup_deploy(self, params):  # pylint: disable=no-self-use
        actions = iter(params)
        while actions:
            try:
                action = next(actions)
                if 'deploy' in action:
                    yield action['deploy']
            except StopIteration:
                break

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
        self.assertRaises(JobError, fakepipeline.run_actions, None, None)
        self.assertIsNotNone(fakepipeline.errors)
        self.assertIsNotNone(deploy.action.job)

    def test_internal_retry(self):
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        deploy = TestAction.FakeDeploy(fakepipeline)
        for actions in self.lookup_deploy(self.parameters['actions']):
            deploy.action.parameters = actions
        self.assertEqual(deploy.action.max_retries, 3)
        fakepipeline.add_action(deploy.action)
        self.assertIsNotNone(deploy.action.job)
        self.assertIsNone(fakepipeline.validate_actions())
        self.assertRaises(JobError, fakepipeline.run_actions, None, None)
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


class TestAdjuvant(StdoutTestCase):  # pylint: disable=too-many-public-methods

    class FakeJob(Job):

        def __init__(self, parameters):
            super(TestAdjuvant.FakeJob, self).__init__(4212, parameters, None)
            self.logger = DummyLogger()
            self.timeout = Timeout("FakeJob", Timeout.parse({'minutes': 2}))

        def validate(self, simulate=False):
            self.pipeline.validate_actions()

    class FakeDeploy(object):
        """
        Derived from object, *not* Deployment as this confuses python -m unittest discover
        - leads to the FakeDeploy being called instead.
        """
        def __init__(self, parent):
            self.__parameters__ = {}
            self.pipeline = parent
            self.job = parent.job
            self.action = TestAdjuvant.FakeAction()

    class FakeConnection(object):
        def __init__(self):
            self.name = "fake-connect"

    class FakeDevice(object):
        def __init__(self):
            self.parameters = {}

    class FakePipeline(Pipeline):

        def __init__(self, parent=None, job=None):
            super(TestAdjuvant.FakePipeline, self).__init__(parent, job)

    class FailingAdjuvant(AdjuvantAction):  # pylint: disable=abstract-method
        """
        Added to the pipeline but only runs if FakeAction sets a suitable key.
        """
        def __init__(self):
            super(TestAdjuvant.FailingAdjuvant, self).__init__()
            self.name = "fake-adjuvant"
            self.summary = "fake helper"
            self.description = "fake adjuvant helper"

    class FakeAdjuvant(AdjuvantAction):
        """
        Added to the pipeline but only runs if FakeAction sets a suitable key.
        """
        def __init__(self):
            super(TestAdjuvant.FakeAdjuvant, self).__init__()
            self.name = "fake-adjuvant"
            self.summary = "fake helper"
            self.description = "fake adjuvant helper"

        @classmethod
        def key(cls):
            return "fake-key"

        def run(self, connection, max_end_time, args=None):
            connection = super(TestAdjuvant.FakeAdjuvant, self).run(connection, max_end_time, args)
            if not self.valid:
                raise RuntimeError("fakeadjuvant should be valid")
            if self.data[self.key()]:
                self.data[self.key()] = 'triggered'
            if self.adjuvant:
                self.data[self.key()] = 'base class trigger'
            return connection

    class FakeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        def __init__(self):
            super(TestAdjuvant.FakeAction, self).__init__()
            self.count = 1
            self.name = "fake-action"
            self.summary = "fake action for unit tests"
            self.description = "fake, do not use outside unit tests"

        def populate(self, parameters):
            self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
            self.internal_pipeline.add_action(TestAdjuvant.FakeAdjuvant())

        def run(self, connection, max_end_time, args=None):
            if connection:
                raise RuntimeError("Fake action not meant to have a real connection")
            connection = TestAdjuvant.FakeConnection()
            self.count += 1
            self.results = {'status': "failed"}
            self.data[TestAdjuvant.FakeAdjuvant.key()] = True
            return connection

    class SafeAction(Action):
        """
        Isolated test action which does not trigger the adjuvant
        """
        def __init__(self):
            super(TestAdjuvant.SafeAction, self).__init__()
            self.name = "passing-action"
            self.summary = "fake action without adjuvant"
            self.description = "fake action runs without calling adjuvant"

        def populate(self, parameters):
            self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
            self.internal_pipeline.add_action(TestAdjuvant.FakeAdjuvant())

        def run(self, connection, max_end_time, args=None):
            if connection:
                raise RuntimeError("Fake action not meant to have a real connection")
            connection = TestAdjuvant.FakeConnection()
            self.results = {'status': "passed"}
            self.data[TestAdjuvant.FakeAdjuvant.key()] = False
            return connection

    def setUp(self):
        super(TestAdjuvant, self).setUp()
        self.parameters = {
            "job_name": "fakejob",
            'output_dir': mkdtemp(),
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
        self.fakejob = TestAdjuvant.FakeJob(self.parameters)

    def test_adjuvant_key(self):
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        pipeline.add_action(TestAdjuvant.FakeAction())
        pipeline.add_action(TestAdjuvant.FailingAdjuvant())
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestAdjuvant.FakeDevice()
        with self.assertRaises(JobError):
            self.fakejob.validate()

    def test_adjuvant(self):
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        pipeline.add_action(TestAdjuvant.FakeAction())
        pipeline.add_action(TestAdjuvant.FakeAdjuvant())
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestAdjuvant.FakeDevice()
        actions = []
        for action in self.fakejob.pipeline.actions:
            actions.append(action.name)
        self.assertIn('fake-action', actions)
        self.assertIn('fake-adjuvant', actions)
        self.assertEqual(self.fakejob.pipeline.actions[1].key(), TestAdjuvant.FakeAdjuvant.key())

    def test_run_adjuvant_action(self):
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        pipeline.add_action(TestAdjuvant.FakeAction())
        pipeline.add_action(TestAdjuvant.FakeAdjuvant())
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestAdjuvant.FakeDevice()
        self.assertEqual(self.fakejob.run(), 0)
        self.assertEqual(self.fakejob.context, {'fake-key': 'base class trigger'})

    def test_run_action(self):
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        pipeline.add_action(TestAdjuvant.SafeAction())
        pipeline.add_action(TestAdjuvant.FakeAdjuvant())
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestAdjuvant.FakeDevice()
        self.assertEqual(self.fakejob.run(), 0)
        self.assertNotEqual(self.fakejob.context, {'fake-key': 'triggered'})
        self.assertNotEqual(self.fakejob.context, {'fake-key': 'base class trigger'})
        self.assertEqual(self.fakejob.context, {'fake-key': False})

    def test_namespace_data(self):
        """
        namespace data uses copies, not references

        This allows actions to refer to the common data and manipulate it without affecting other actions.
        """
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = TestAdjuvant.SafeAction()
        pipeline.add_action(action)
        action.set_namespace_data(action='test', label="fake", key="string value", value="test string")
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='string value'), 'test string')
        test_string = action.get_namespace_data(action='test', label='fake', key='string value')
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='string value'), 'test string')
        self.assertEqual(test_string, 'test string')
        test_string += "extra data"
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='string value'), 'test string')
        self.assertNotEqual(test_string, 'test string')
        self.assertNotEqual(action.get_namespace_data(action='test', label='fake', key='string value'), test_string)
        action.set_namespace_data(action='test', label="fake", key="list value", value=[1, 2, 3])
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='list value'), [1, 2, 3])
        test_list = action.get_namespace_data(action='test', label='fake', key='list value')
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='list value'), [1, 2, 3])
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='list value'), test_list)
        test_list.extend([4, 5, 6])
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='list value'), [1, 2, 3])
        self.assertNotEqual(action.get_namespace_data(action='test', label='fake', key='list value'), test_list)
        self.assertEqual(test_list, [1, 2, 3, 4, 5, 6])

        # test support for the more risky reference method
        reference_list = action.get_namespace_data(action='test', label='fake', key='list value', deepcopy=False)
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='list value'), [1, 2, 3])
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='list value'), reference_list)
        reference_list.extend([7, 8, 9])
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='list value'), [1, 2, 3, 7, 8, 9])
        self.assertEqual(reference_list, [1, 2, 3, 7, 8, 9])
        reference_list = [4, 5, 6]
        self.assertEqual(action.get_namespace_data(action='test', label='fake', key='list value'), [1, 2, 3, 7, 8, 9])
        self.assertNotEqual(reference_list, [1, 2, 3, 7, 8, 9])


class TestTimeout(StdoutTestCase):  # pylint: disable=too-many-public-methods

    class FakeJob(Job):

        def __init__(self, parameters):
            super(TestTimeout.FakeJob, self).__init__(4212, parameters, None)
            self.logger = DummyLogger()

        def validate(self, simulate=False):
            self.pipeline.validate_actions()

    class FakeDevice(object):
        def __init__(self):
            self.parameters = {}
            self.power_state = ''

    class FakePipeline(Pipeline):

        def __init__(self, parent=None, job=None):
            super(TestTimeout.FakePipeline, self).__init__(parent, job)

    class FakeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        def __init__(self):
            super(TestTimeout.FakeAction, self).__init__()
            self.name = "fake-action"
            self.summary = "fake action for unit tests"
            self.description = "fake, do not use outside unit tests"

        def populate(self, parameters):
            self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
            self.internal_pipeline.add_action(TestAdjuvant.FakeAdjuvant())

        def run(self, connection, max_end_time, args=None):
            if connection:
                raise RuntimeError("Fake action not meant to have a real connection")
            time.sleep(3)
            self.results = {'status': "failed"}
            return connection

    class SafeAction(Action):
        """
        Isolated test action which passes
        """
        def __init__(self):
            super(TestTimeout.SafeAction, self).__init__()
            self.name = "passing-action"
            self.summary = "fake action without adjuvant"
            self.description = "fake action runs without calling adjuvant"

        def run(self, connection, max_end_time, args=None):
            if connection:
                raise RuntimeError("Fake action not meant to have a real connection")
            self.results = {'status': "passed"}
            return connection

    class LongAction(Action):
        """
        Isolated test action which times out the job itself
        """
        def __init__(self):
            super(TestTimeout.LongAction, self).__init__()
            self.name = "long-action"
            self.summary = "fake action with overly long sleep"
            self.description = "fake action"

        def run(self, connection, max_end_time, args=None):
            if connection:
                raise RuntimeError("Fake action not meant to have a real connection")
            time.sleep(5)
            self.results = {'status': "passed"}
            return connection

    class SkippedAction(Action):
        """
        Isolated test action which must not be run
        """
        def __init__(self):
            super(TestTimeout.SkippedAction, self).__init__()
            self.name = "passing-action"
            self.summary = "fake action without adjuvant"
            self.description = "fake action runs without calling adjuvant"

        def run(self, connection, max_end_time, args=None):
            raise RuntimeError("Fake action not meant to actually run - should have timed out")

    class FakeSafeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        def __init__(self):
            super(TestTimeout.FakeSafeAction, self).__init__()
            self.name = "fake-action"
            self.summary = "fake action for unit tests"
            self.description = "fake, do not use outside unit tests"
            self.timeout.duration = 4

        def populate(self, parameters):
            self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
            self.internal_pipeline.add_action(TestAdjuvant.FakeAdjuvant())

        def run(self, connection, max_end_time, args=None):
            if connection:
                raise RuntimeError("Fake action not meant to have a real connection")
            time.sleep(3)
            self.results = {'status': "failed"}
            return connection

    def setUp(self):
        super(TestTimeout, self).setUp()
        self.parameters = {
            "job_name": "fakejob",
            'output_dir': mkdtemp(),
            'timeouts': {
                'job': {
                    'seconds': 3
                }
            },
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
        self.fakejob = TestTimeout.FakeJob(self.parameters)
        # copy of the _timeout function from parser.
        if 'timeouts' in self.parameters:
            if 'job' in self.parameters['timeouts']:
                duration = Timeout.parse(self.parameters['timeouts']['job'])
                self.fakejob.timeout = Timeout(self.parameters['job_name'], duration)

    def test_action_timeout(self):
        """
        Testing timeouts does mean that the tests do nothing until the timeout happens,
        so the total length of time to run the tests has to increase...
        """
        self.assertIsNotNone(self.fakejob.timeout)
        seconds = 2
        pipeline = TestTimeout.FakePipeline(job=self.fakejob)
        action = TestTimeout.FakeAction()
        action.timeout = Timeout(action.name, duration=seconds)
        pipeline.add_action(action)
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        # run() returns 2 for JobError
        self.assertEqual(self.fakejob.run(), 2)

    def test_action_complete(self):
        self.assertIsNotNone(self.fakejob.timeout)
        seconds = 2
        pipeline = TestTimeout.FakePipeline(job=self.fakejob)
        action = TestTimeout.SafeAction()
        action.timeout = Timeout(action.name, duration=seconds)
        pipeline.add_action(action)
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        self.assertEqual(self.fakejob.run(), 0)

    def test_job_timeout(self):
        self.assertIsNotNone(self.fakejob.timeout)
        pipeline = TestTimeout.FakePipeline(job=self.fakejob)
        action = TestTimeout.LongAction()
        pipeline.add_action(action)
        pipeline.add_action(TestTimeout.SafeAction())
        pipeline.add_action(FinalizeAction())
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        # run() returns 2 for JobError
        self.assertEqual(self.fakejob.run(), 2)

    def test_job_safe(self):
        self.assertIsNotNone(self.fakejob.timeout)
        pipeline = TestTimeout.FakePipeline(job=self.fakejob)
        action = TestTimeout.SafeAction()
        pipeline.add_action(action)
        pipeline.add_action(TestTimeout.SafeAction())
        pipeline.add_action(FinalizeAction())
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        # run() returns 0 in case of success
        self.assertEqual(self.fakejob.run(), 0)

    def test_long_job_safe(self):
        self.fakejob.timeout.duration = 8
        self.assertIsNotNone(self.fakejob.timeout)
        pipeline = TestTimeout.FakePipeline(job=self.fakejob)
        self.fakejob.pipeline = pipeline
        action = TestTimeout.SafeAction()
        action.timeout.duration = 2
        pipeline.add_action(action)
        pipeline.add_action(action)
        pipeline.add_action(TestTimeout.FakeSafeAction())
        pipeline.add_action(TestTimeout.FakeSafeAction())
        pipeline.add_action(FinalizeAction())
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        self.assertEqual(self.fakejob.run(), 0)
