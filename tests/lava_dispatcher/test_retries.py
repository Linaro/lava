# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional
from unittest.mock import patch

from lava_common.exceptions import JobError, LAVABug
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.parser import JobParser
from lava_dispatcher.power import FinalizeAction
from tests.lava_dispatcher.test_basic import LavaDispatcherTestCase

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


DEFAULT_TEST_ERROR_MESSAGE = "Unit Testing Expected Error"


class RaisesErrorException(JobError):
    # Exception raised by RaisesErrorAction
    # to differentiate between real errors and expected testing ones
    ...


class RaisesErrorAction(Action):
    name = "unit-test-raises-error"

    def __init__(
        self,
        job: Job,
        retries_to_success: int = 100,
        error_message: str = DEFAULT_TEST_ERROR_MESSAGE,
        populate_actions: Optional[list[Action]] = None,
        exception_class: type[Exception] = RaisesErrorException,
    ):
        super().__init__(job)
        self.num_calls = 0
        self.num_cleanup_calls = 0
        self.retries_to_success = retries_to_success
        self.error_message = error_message
        self._populate_actions = populate_actions
        self._exception_class = exception_class

    def run(self, connection, max_end_time):
        self.num_calls += 1

        if self.num_calls < self.retries_to_success:
            raise self._exception_class(self.error_message)
        else:
            super().run(connection, max_end_time)

    def populate(self, parameters):
        if self._populate_actions is None:
            return

        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        for a in self._populate_actions:
            self.pipeline.add_action(a)

    def validate(self):
        # Don't check self.name, self.summary and etc...
        ...

    def cleanup(self, connection):
        self.num_cleanup_calls += 1
        super().cleanup(connection)


class UnitTestRetryAction(RetryAction):
    name = "unit-test-retry"

    def __init__(self, job: Job, internal_actions: list[Action]):
        super().__init__(job)
        self._internal_actions = internal_actions
        self.sleep = 0

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        for a in self._internal_actions:
            self.pipeline.add_action(a)

    def validate(self):
        # Don't check self.name, self.summary and etc...
        ...


class TestRetriesAndFailuresBase(LavaDispatcherTestCase):
    def create_job_and_root_pipeline(
        self, job_timeout: int = 10
    ) -> tuple[Pipeline, Job]:
        parameters = {
            "job_name": "retry_test_job",
            "timeouts": {"job": {"seconds": job_timeout}},
        }
        job = self.create_simple_job(job_parameters=parameters)
        job.timeout = JobParser._parse_job_timeout(parameters)
        pipeline = Pipeline(job)
        job.pipeline = pipeline

        return pipeline, job


class TestRetries(TestRetriesAndFailuresBase):
    def test_action_success(self) -> None:
        # Test that Action can successfully run
        root_pipeline, job = self.create_job_and_root_pipeline()

        success_action = RaisesErrorAction(job, retries_to_success=0)
        root_pipeline.add_action(success_action)

        with self.subTest("Run success"):
            job.run()

        with self.subTest("Number of calls"):
            self.assertEqual(success_action.num_calls, 1)

        with self.subTest("Number of cleanups"):
            # Regular Actions .cleanup() is called once by the Job once it finishes
            self.assertEqual(success_action.num_cleanup_calls, 1)

    def test_action_raise_error(self) -> None:
        # Check that running pipeline that raises error
        root_pipeline, job = self.create_job_and_root_pipeline()

        fail_action = RaisesErrorAction(job)
        root_pipeline.add_action(fail_action)

        with self.subTest("Raises error"), self.assertRaisesRegex(
            RaisesErrorException, DEFAULT_TEST_ERROR_MESSAGE
        ):
            job.run()

        with self.subTest("Number of calls"):
            self.assertEqual(fail_action.num_calls, 1)

        with self.subTest("Number of cleanups"):
            # Regular Actions .cleanup() is called once by the Job once it finishes
            self.assertEqual(fail_action.num_cleanup_calls, 1)

        with self.subTest("Failure in results"):
            self.assertIn("fail", fail_action.results)

    def test_retry_action_no_pipeline(self) -> None:
        # RetryAction must fail validation if no sub actions were added
        # but mock the Action.validate because it is not relevant
        root_pipeline, job = self.create_job_and_root_pipeline()

        root_pipeline.add_action(RetryAction(job))

        with self.assertRaisesRegex(
            LAVABug, "needs to implement an internal pipeline"
        ), patch.object(Action, "validate") as action_validate_mock:
            root_pipeline.validate_actions()

        action_validate_mock.assert_called_once()

    def test_retry_action_first_try_success(self) -> None:
        root_pipeline, job = self.create_job_and_root_pipeline()

        success_action = RaisesErrorAction(job, retries_to_success=0)
        retry_action = UnitTestRetryAction(job, [success_action])

        root_pipeline.add_action(retry_action)

        with self.subTest("Run success"):
            job.run()

        with self.subTest("Number of calls"):
            self.assertEqual(success_action.num_calls, 1)

        with self.subTest("Number of cleanups"):
            # Regular Actions .cleanup() is called once by the Job once it finishes
            self.assertEqual(success_action.num_cleanup_calls, 1)

    def test_retry_action_second_try_success(self) -> None:
        root_pipeline, job = self.create_job_and_root_pipeline()

        success_action = RaisesErrorAction(job, retries_to_success=2)
        retry_action = UnitTestRetryAction(job, [success_action])

        root_pipeline.add_action(retry_action, {"failure_retry": 3})

        with self.subTest("Run success"):
            job.run()

        with self.subTest("Number of calls"):
            self.assertEqual(success_action.num_calls, 2)

        with self.subTest("Number of cleanups"):
            # Cleanup called once by RetryAction on failure and once by Job on finish
            self.assertEqual(success_action.num_cleanup_calls, 2)

        with self.subTest("No failure in results"):
            self.assertNotIn("fail", retry_action.results)
            self.assertNotIn("fail", success_action.results)

        with self.subTest("No recorded errors"):
            self.assertFalse(retry_action.errors)
            self.assertFalse(success_action.errors)

    def test_retry_action_all_fails(self) -> None:
        root_pipeline, job = self.create_job_and_root_pipeline()

        fail_action = RaisesErrorAction(job)
        retry_action = UnitTestRetryAction(job, [fail_action])

        root_pipeline.add_action(retry_action, {"failure_retry": 3})

        with self.subTest("Raises error"), self.assertRaisesRegex(
            RaisesErrorException, DEFAULT_TEST_ERROR_MESSAGE
        ):
            job.run()

        with self.subTest("Number of calls"):
            self.assertEqual(fail_action.num_calls, 3)

        with self.subTest("Number of cleanups"):
            # 3 reties == 3 cleanups + 1 Job cleanup
            self.assertEqual(
                fail_action.num_cleanup_calls,
                4,
            )

        with self.subTest("Failure in results"):
            self.assertIn("fail", retry_action.results)
            self.assertIn("fail", fail_action.results)

        with self.subTest("Recorded errors"):
            self.assertTrue(retry_action.errors)
            self.assertFalse(fail_action.errors)

    def test_retry_action_nested_eventual_success(self) -> None:
        root_pipeline, job = self.create_job_and_root_pipeline()

        success_action = RaisesErrorAction(job, retries_to_success=5)
        retry_action_bottom = UnitTestRetryAction(job, [success_action])
        retry_action_top = UnitTestRetryAction(job, [retry_action_bottom])

        root_pipeline.add_action(retry_action_top, {"failure_retry": 3})

        with self.subTest("Run success"):
            job.run()

        with self.subTest("Number of calls"):
            self.assertEqual(success_action.num_calls, 5)

        with self.subTest("Number of cleanups"):
            # Cleanup called once by RetryAction on failure and once by Job on finish
            self.assertEqual(success_action.num_cleanup_calls, 6)

        with self.subTest("No failure in results"):
            self.assertNotIn("fail", retry_action_top.results)
            self.assertNotIn("fail", retry_action_bottom.results)
            self.assertNotIn("fail", success_action.results)

        with self.subTest("No recorded errors"):
            self.assertFalse(retry_action_top.errors)
            self.assertFalse(retry_action_bottom.errors)
            self.assertFalse(success_action.errors)


class SleepsTimeoutException(JobError):
    # Exception raised then sleep times out
    ...


class SleepsAction(Action):
    name = "unit-test-sleeps"
    timeout_exception = SleepsTimeoutException

    def __init__(self, job: Job, retries_to_success: int = 100):
        super().__init__(job)
        self.num_calls = 0
        self.retries_to_success = retries_to_success

    def run(self, connection, max_end_time):
        self.num_calls += 1

        if self.num_calls < self.retries_to_success:
            time.sleep(60)
        else:
            super().run(connection, max_end_time)

    def validate(self):
        # Don't check self.name, self.summary and etc...
        ...


class TestRetryTimeout(TestRetriesAndFailuresBase):
    def test_retry_timeout_duration_divided(self) -> None:
        root_pipeline, job = self.create_job_and_root_pipeline(job_timeout=4)

        sleep_action = SleepsAction(job)
        retry_action = UnitTestRetryAction(job, [sleep_action])

        root_pipeline.add_action(
            retry_action,
            {
                "failure_retry": 3,
                "failure_retry_interval": 0,
                "timeout": {"seconds": 3},
            },
        )

        start_time = time.monotonic()

        with self.subTest("Raises error"), self.assertRaisesRegex(
            SleepsTimeoutException, "timed out after 1 seconds"
        ):
            root_pipeline.job.run()

        with self.subTest("Number of calls"):
            self.assertEqual(sleep_action.num_calls, 3)

        with self.subTest("Passed time"):
            # Only (3 * 1) + (3 - 1) * 0 = 3 seconds should have passed
            self.assertAlmostEqual(start_time + 3.0, time.monotonic(), delta=0.3)

    def test_retry_timeout_duration_respects_job_timeout(self) -> None:
        root_pipeline, job = self.create_job_and_root_pipeline(job_timeout=2)

        sleep_action = SleepsAction(job)
        retry_action = UnitTestRetryAction(job, [sleep_action])

        root_pipeline.add_action(
            retry_action,
            {
                "failure_retry": 10,
                "failure_retry_interval": 0,
                "timeout": {"seconds": 10},
            },
        )

        start_time = time.monotonic()

        with self.subTest("Raises error"), self.assertRaisesRegex(
            SleepsTimeoutException, "No time left for"
        ):
            root_pipeline.job.run()

        with self.subTest("Number of calls"):
            self.assertEqual(sleep_action.num_calls, 2)

        with self.subTest("Passed time"):
            self.assertAlmostEqual(start_time + 2.0, time.monotonic(), delta=0.3)

    def test_retry_timeout_duration_respects_action_timeout(self) -> None:
        root_pipeline, job = self.create_job_and_root_pipeline(job_timeout=10)

        sleep_action = SleepsAction(job, retries_to_success=8)
        nested_retry_action = UnitTestRetryAction(job, [sleep_action])
        main_action = RaisesErrorAction(
            job, retries_to_success=1, populate_actions=[nested_retry_action]
        )

        root_pipeline.add_action(
            main_action,
            {
                "failure_retry": 10,
                "failure_retry_interval": 0,
                "timeout": {"seconds": 5},
                "timeouts": {
                    main_action.name: {"seconds": 1},
                    nested_retry_action.name: {"seconds": 3},
                },
            },
        )

        start_time = time.monotonic()

        with self.subTest("Raises error"), self.assertRaisesRegex(
            SleepsTimeoutException,
            f"1 retries out of 10 failed for {UnitTestRetryAction.name}",
        ):
            job.run()

        with self.subTest("Number of calls"):
            self.assertEqual(sleep_action.num_calls, 1)

        with self.subTest("Passed time"):
            self.assertAlmostEqual(start_time + 1.0, time.monotonic(), delta=0.3)


class TestFinalizeAction(TestRetriesAndFailuresBase):
    def test_finalize_action_success(self) -> None:
        root_pipeline, job = self.create_job_and_root_pipeline()

        success_action = RaisesErrorAction(job, retries_to_success=0)
        root_pipeline.add_action(success_action)

        finalize_action = FinalizeAction(job)
        root_pipeline.add_action(finalize_action)

        self.assertFalse(job.started)

        with self.subTest("Run success"):
            root_pipeline.job.run()

        self.assertTrue(job.started)
        self.assertTrue(finalize_action.ran)

    def test_finalize_action_failure(self) -> None:
        root_pipeline, job = self.create_job_and_root_pipeline()

        success_action = RaisesErrorAction(job)
        root_pipeline.add_action(success_action)

        finalize_action = FinalizeAction(job)
        root_pipeline.add_action(finalize_action)

        self.assertFalse(job.started)

        with self.subTest("Raises error"), self.assertRaisesRegex(
            RaisesErrorException, DEFAULT_TEST_ERROR_MESSAGE
        ):
            job.run()

        self.assertTrue(job.started)
        self.assertTrue(finalize_action.ran)
