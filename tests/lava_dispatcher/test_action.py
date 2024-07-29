# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from time import monotonic as time_monotonic

from lava_dispatcher.action import Action, Pipeline

from .test_basic import LavaDispatcherTestCase


class TestActionRunCmd(LavaDispatcherTestCase):
    def setUp(self) -> None:
        self.action = Action(self.create_job_mock())

    def test_simple_command_with_args(self) -> None:
        with self.assertLogs(self.action.logger, "DEBUG") as logs:
            ret = self.action.run_cmd(["printf", "Hello, world!"])

        self.assertEqual(ret, 0)
        self.assertIn(
            "Hello, world!",
            "".join(logs.output),
        )

    def test_no_args_command_with_spaces(self) -> None:
        true_path = which("true")
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            symlink_with_spaces_to_true = tmpdir_path / "with spaces true"
            symlink_with_spaces_to_true.symlink_to(true_path)

            ret = self.action.run_cmd([str(symlink_with_spaces_to_true)])

        self.assertEqual(ret, 0)

    def test_command_timeout(self) -> None:
        self.action.timeout.duration = 0.01

        start_time = time_monotonic()

        with self.assertRaises(self.action.command_exception), self.assertLogs(
            self.action.logger, "ERROR"
        ) as error_logs:
            self.action.run_cmd(["sleep", "10"])

        end_time = time_monotonic()

        self.assertIn(
            "Timed out after",
            "".join(error_logs.output),
        )

        self.assertLess(
            end_time - start_time,
            1.0,
        )

    def test_command_does_not_exist(self) -> None:
        non_existant_command = "THIS_COMMAND_does_NOT_exist"

        with self.assertRaises(self.action.command_exception), self.assertLogs(
            self.action.logger, "ERROR"
        ) as error_logs:
            self.action.run_cmd([non_existant_command])

        self.assertIn(
            non_existant_command,
            "".join(error_logs.output),
        )


class TestActionTimeoutWarnings(LavaDispatcherTestCase):
    def test_timeout_warnings(self) -> None:
        job = self.create_simple_job(
            job_parameters={
                "timeouts": {
                    "job": {"minutes": 5},
                    "action": {"minutes": 10},
                    "actions": {
                        "simple-job-action": {"minutes": 10},
                        "nested-action": {"minutes": 20},
                    },
                }
            }
        )
        pipeline = Pipeline(job=job)
        job.pipeline = pipeline

        simple_job_action = Action(job)
        simple_job_action.name = "simple-job-action"
        with self.assertLogs(
            simple_job_action.logger, "WARN"
        ) as simple_job_action_warn_logs:
            pipeline.add_action(simple_job_action)

        self.assertEqual(len(simple_job_action_warn_logs.output), 1)
        simple_job_action_warn = simple_job_action_warn_logs.output[0]
        self.assertIn("exceeds Job", simple_job_action_warn)
        self.assertIn("simple-job-action", simple_job_action_warn)

        nested_pipeline = Pipeline(parent=simple_job_action, job=job, parameters={})
        simple_job_action.pipeline = nested_pipeline

        nested_action = Action(job)
        nested_action.name = "nested-action"
        with self.assertLogs("dispatcher", "WARN") as nested_action_warn_logs:
            nested_pipeline.add_action(nested_action)

        self.assertEqual(len(nested_action_warn_logs.output), 1)
        nested_action_warn = nested_action_warn_logs.output[0]
        self.assertIn("exceeds parent Action", nested_action_warn)
        self.assertIn("simple-job-action", nested_action_warn)
        self.assertIn("nested-action", nested_action_warn)
