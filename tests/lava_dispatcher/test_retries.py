# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from lava_common.exceptions import InfrastructureError, JobError, LAVABug
from lava_common.timeout import Timeout
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.parser import JobParser
from lava_dispatcher.power import FinalizeAction
from tests.lava_dispatcher.test_basic import LavaDispatcherTestCase

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class TestAction(LavaDispatcherTestCase):
    class FakeDeploy:
        """
        Derived from object, *not* Deployment as this confuses python -m unittest discover
        - leads to the FakeDeploy being called instead.
        """

        def __init__(self, parent):
            self.__parameters__ = {}
            self.pipeline = parent
            self.job = parent.job
            self.action = TestAction.CleanupRetryAction(self.job)

    class MissingCleanupDeploy:
        def __init__(self, parent):
            self.__parameters__ = {}
            self.pipeline = parent
            self.job = parent.job
            self.action = TestAction.InternalRetryAction(self.job)

    class FakePipeline(Pipeline):
        def __init__(self, job: Job):
            super().__init__(job)
            job.pipeline = self

    class FakeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        name = "fake-action"
        description = "fake, do not use outside unit tests"
        summary = "fake action for unit tests"

        def __init__(self, job: Job):
            super().__init__(job)
            self.count = 1
            self.parameters["namespace"] = "common"

        def run(self, connection, max_end_time):
            self.count += 1
            raise JobError("fake error")

    class FakeRetryAction(RetryAction):
        name = "fake-retry-action"
        description = "fake, do not use outside unit tests"
        summary = "fake retry action for unit tests"

    class InternalRetryAction(RetryAction):
        section = "internal"
        name = "internal-retry-action"
        description = "internal, do not use outside unit tests"
        summary = "internal retry action for unit tests"

        def populate(self, parameters):
            self.pipeline = Pipeline(parent=self, job=self.job)
            self.pipeline.add_action(TestAction.FakeAction(self.job), parameters)

    class CleanupRetryAction(RetryAction):
        section = "internal"
        name = "internal-retry-action"
        description = "internal, do not use outside unit tests"
        summary = "internal retry action for unit tests"

        def populate(self, parameters):
            self.pipeline = Pipeline(parent=self, job=self.job)
            self.pipeline.add_action(TestAction.FakeAction(self.job), parameters)

        def cleanup(self, connection):
            pass

    def setUp(self):
        super().setUp()
        self.parameters = {
            "job_name": "fakejob",
            "timeouts": {"job": {"seconds": 3}},
            "actions": [
                {
                    "deploy": {"namespace": "common", "failure_retry": 3},
                    "boot": {"namespace": "common", "failure_retry": 4},
                    "test": {"namespace": "common", "failure_retry": 5},
                }
            ],
        }
        self.fakejob = self.create_simple_job(job_parameters=self.parameters)
        self.fakejob.timeout = JobParser._parse_job_timeout(self.parameters)

    def lookup_deploy(self, params):
        actions = iter(params)
        while actions:
            try:
                action = next(actions)
                if "deploy" in action:
                    yield action["deploy"]
            except StopIteration:
                break

    def test_fakeaction_fails_joberror(self):
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        fakepipeline.add_action(TestAction.FakeAction(self.fakejob))
        self.assertIsInstance(fakepipeline.actions[0], TestAction.FakeAction)
        with self.assertRaises(JobError):
            # FakeAction is not a RetryAction
            fakepipeline.run_actions(None, None)

    def test_fakeretry_action(self):
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        fakepipeline.add_action(TestAction.FakeRetryAction(self.fakejob))
        with self.assertRaises(LAVABug):
            # first fake retry has no internal pipeline
            self.assertTrue(fakepipeline.validate_actions())

    def test_cleanup_deploy(self):
        fakepipeline = TestAction.FakePipeline(job=self.fakejob)
        deploy = TestAction.MissingCleanupDeploy(fakepipeline)
        for actions in self.lookup_deploy(self.parameters["actions"]):
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
        for actions in self.lookup_deploy(self.parameters["actions"]):
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

    def test_namespace_data(self):
        """
        namespace data uses copies, not references

        This allows actions to refer to the common data and manipulate it without affecting other actions.
        """
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = TestAction.FakeAction(self.fakejob)
        pipeline.add_action(action)
        self.assertEqual({"namespace": "common"}, action.parameters)
        action.set_namespace_data(
            action="test", label="fake", key="string value", value="test string"
        )
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="string value"),
            "test string",
        )
        test_string = action.get_namespace_data(
            action="test", label="fake", key="string value"
        )
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="string value"),
            "test string",
        )
        self.assertEqual(test_string, "test string")
        test_string += "extra data"
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="string value"),
            "test string",
        )
        self.assertNotEqual(test_string, "test string")
        self.assertNotEqual(
            action.get_namespace_data(action="test", label="fake", key="string value"),
            test_string,
        )
        action.set_namespace_data(
            action="test", label="fake", key="list value", value=[1, 2, 3]
        )
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="list value"),
            [1, 2, 3],
        )
        test_list = action.get_namespace_data(
            action="test", label="fake", key="list value"
        )
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="list value"),
            [1, 2, 3],
        )
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="list value"),
            test_list,
        )
        test_list.extend([4, 5, 6])
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="list value"),
            [1, 2, 3],
        )
        self.assertNotEqual(
            action.get_namespace_data(action="test", label="fake", key="list value"),
            test_list,
        )
        self.assertEqual(test_list, [1, 2, 3, 4, 5, 6])

        # test support for the more risky reference method
        reference_list = action.get_namespace_data(
            action="test", label="fake", key="list value", deepcopy=False
        )
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="list value"),
            [1, 2, 3],
        )
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="list value"),
            reference_list,
        )
        reference_list.extend([7, 8, 9])
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="list value"),
            [1, 2, 3, 7, 8, 9],
        )
        self.assertEqual(reference_list, [1, 2, 3, 7, 8, 9])
        reference_list = [4, 5, 6]
        self.assertEqual(
            action.get_namespace_data(action="test", label="fake", key="list value"),
            [1, 2, 3, 7, 8, 9],
        )
        self.assertNotEqual(reference_list, [1, 2, 3, 7, 8, 9])

    def test_failure_retry_default_interval(self):
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = TestAction.InternalRetryAction(self.fakejob)
        for actions in self.lookup_deploy(self.parameters["actions"]):
            action.parameters = actions
        pipeline.add_action(action)
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        with self.assertRaises(JobError):
            self.fakejob.run()
        self.assertEqual(action.sleep, 1)

    def test_failure_retry_specified_interval(self):
        self.parameters = {
            "job_name": "fakejob",
            "timeouts": {"job": {"seconds": 3}},
            "actions": [
                {
                    "deploy": {
                        "namespace": "common",
                        "failure_retry": 3,
                        "failure_retry_interval": 2,
                    },
                    "boot": {"namespace": "common", "failure_retry": 4},
                    "test": {"namespace": "common", "failure_retry": 5},
                }
            ],
        }
        self.fakejob = self.create_simple_job(job_parameters=self.parameters)
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = TestAction.InternalRetryAction(self.fakejob)
        for actions in self.lookup_deploy(self.parameters["actions"]):
            action.parameters = actions
        pipeline.add_action(action)
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        with self.assertRaises(JobError):
            self.fakejob.run()
        self.assertEqual(action.sleep, 2)


class TestTimeout(LavaDispatcherTestCase):
    class FakeDevice(dict):
        def __init__(self):
            self.update({"parameters": {}, "commands": {}})

        def __get_item__(self):
            return {}

    class FakeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        name = "fake-action"
        description = "fake, do not use outside unit tests"
        summary = "fake action for unit tests"

        def populate(self, parameters):
            self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
            self.pipeline.add_action(TestAction.FakeAction(self.job))

        def run(self, connection, max_end_time):
            if connection:
                raise LAVABug("Fake action not meant to have a real connection")
            time.sleep(3)
            self.results = {"status": "failed"}
            return connection

    class SafeAction(Action):
        """
        Isolated test action which passes
        """

        name = "passing-action"
        description = "fake action runs without calling adjuvant"
        summary = "fake action without adjuvant"

        def __init__(self, job: Job):
            super().__init__(job)
            self.parameters["namespace"] = "common"

        def run(self, connection, max_end_time):
            if connection:
                raise LAVABug("Fake action not meant to have a real connection")
            self.results = {"status": "passed"}
            return connection

    class LongAction(Action):
        """
        Isolated test action which times out the job itself
        """

        name = "long-action"
        description = "fake action"
        summary = "fake action with overly long sleep"

        def __init__(self, job: Job):
            super().__init__(job)
            self.parameters["namespace"] = "common"

        def run(self, connection, max_end_time):
            if connection:
                raise LAVABug("Fake action not meant to have a real connection")
            time.sleep(5)
            self.results = {"status": "passed"}
            return connection

    class SkippedAction(Action):
        """
        Isolated test action which must not be run
        """

        name = "passing-action"
        description = "fake action runs without calling adjuvant"
        summary = "fake action without adjuvant"

        def run(self, connection, max_end_time):
            raise LAVABug(
                "Fake action not meant to actually run - should have timed out"
            )

    class FakeSafeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        name = "fake-action"
        description = "fake, do not use outside unit tests"
        summary = "fake action for unit tests"

        def __init__(self, job: Job):
            super().__init__(job)
            self.timeout.duration = 4

        def populate(self, parameters):
            self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
            self.pipeline.add_action(TestAction.FakeAction(self.job))

        def run(self, connection, max_end_time):
            if connection:
                raise LAVABug("Fake action not meant to have a real connection")
            time.sleep(3)
            self.results = {"status": "failed"}
            return connection

    def setUp(self):
        super().setUp()
        self.parameters = {
            "job_name": "fakejob",
            "timeouts": {"job": {"seconds": 3}},
            "actions": [
                {
                    "deploy": {"namespace": "common", "failure_retry": 3},
                    "boot": {"namespace": "common", "failure_retry": 4},
                    "test": {"namespace": "common", "failure_retry": 5},
                }
            ],
        }
        self.fakejob = self.create_simple_job(job_parameters=self.parameters)
        self.fakejob.timeout = JobParser._parse_job_timeout(self.parameters)

    def test_action_timeout(self):
        """
        Testing timeouts does mean that the tests do nothing until the timeout happens,
        so the total length of time to run the tests has to increase...
        """
        self.assertIsNotNone(self.fakejob.timeout)
        seconds = 2
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = TestTimeout.FakeAction(self.fakejob)
        pipeline.add_action(action)
        action.timeout = Timeout(action.name, action=action, duration=seconds)
        self.fakejob.device = TestTimeout.FakeDevice()
        with self.assertRaises(JobError):
            self.fakejob.run()

    def test_action_timout_custom_exception(self):
        seconds = 2
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = TestTimeout.FakeAction(self.fakejob)
        action.timeout = Timeout(
            action.name, action=action, duration=seconds, exception=InfrastructureError
        )
        pipeline.add_action(action)
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        with self.assertRaises(InfrastructureError):
            self.fakejob.run()

    def test_action_complete(self):
        self.assertIsNotNone(self.fakejob.timeout)
        seconds = 2
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = TestTimeout.SafeAction(self.fakejob)
        action.timeout = Timeout(action.name, action=action, duration=seconds)
        pipeline.add_action(action)
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        self.fakejob.run()

    def test_job_timeout(self):
        self.assertIsNotNone(self.fakejob.timeout)
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = TestTimeout.LongAction(self.fakejob)
        pipeline.add_action(action)
        pipeline.add_action(TestTimeout.SafeAction(self.fakejob))
        finalize = FinalizeAction(self.fakejob)
        finalize.parameters["namespace"] = "common"
        pipeline.add_action(finalize)
        self.fakejob.device = TestTimeout.FakeDevice()
        with self.assertRaises(JobError):
            self.fakejob.run()

    def test_retry_job_timeout(self):
        fakejob = self.fakejob

        class LongRetryAction(RetryAction):
            def populate(self, parameters):
                self.pipeline = TestAction.FakePipeline(job=fakejob)
                self.pipeline.add_action(TestTimeout.LongAction(fakejob))

                finalize = FinalizeAction(self.job)
                finalize.parameters["namespace"] = "common"
                self.pipeline.add_action(finalize)

        self.assertIsNotNone(self.fakejob.timeout)
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = LongRetryAction(self.fakejob)
        action.max_retries = 10
        pipeline.add_action(action)
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()

        from time import monotonic

        start_time = monotonic()

        with self.assertRaises(JobError):
            self.fakejob.run()

        # Test that we honor job timeout over retries
        self.assertAlmostEqual(
            self.fakejob.timeout.duration,
            monotonic() - start_time,
            delta=3,
        )

    def test_job_safe(self):
        self.assertIsNotNone(self.fakejob.timeout)
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        action = TestTimeout.SafeAction(self.fakejob)
        pipeline.add_action(action)
        pipeline.add_action(TestTimeout.SafeAction(self.fakejob))
        finalize = FinalizeAction(self.fakejob)
        finalize.parameters["namespace"] = "common"
        pipeline.add_action(finalize)
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        # run() raises an exception in case of error
        self.fakejob.run()

    def test_long_job_safe(self):
        self.fakejob.timeout.duration = 8
        self.assertIsNotNone(self.fakejob.timeout)
        pipeline = TestAction.FakePipeline(job=self.fakejob)
        self.fakejob.pipeline = pipeline
        action = TestTimeout.SafeAction(self.fakejob)
        action.timeout.duration = 2
        pipeline.add_action(action)
        pipeline.add_action(action)
        pipeline.add_action(TestTimeout.FakeSafeAction(self.fakejob))
        pipeline.add_action(TestTimeout.FakeSafeAction(self.fakejob))
        finalize = FinalizeAction(self.fakejob)
        finalize.parameters["namespace"] = "common"
        pipeline.add_action(finalize)
        self.fakejob.pipeline = pipeline
        self.fakejob.device = TestTimeout.FakeDevice()
        self.fakejob.run()
