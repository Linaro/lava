# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from pathlib import Path

from lava_common.yaml import yaml_safe_load
from lava_dispatcher.actions.deploy.download import HttpDownloadAction

from .test_basic import Factory, LavaDispatcherTestCase


class TestJob(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.job = self.create_simple_job()

    def test_tmp_dir(self):
        self.assertIsNotNone(self.job.tmp_dir)
        tmp_dir = Path(self.job.tmp_dir)
        self.assertFalse(tmp_dir.exists())
        self.assertEqual(tmp_dir.name, str(self.job.job_id))

    def test_tmp_dir_with_prefix(self):
        self.job.parameters["dispatcher"] = {"prefix": "FOOBAR-"}
        tmp_dir = Path(self.job.tmp_dir)
        self.assertEqual(tmp_dir.name, f"FOOBAR-{self.job.job_id}")

    def test_mkdtemp(self):
        d = self.job.mkdtemp("my-action")
        self.assertTrue(Path(d).exists())
        self.assertIn("my-action", d)

    def test_mkdtemp_with_prefix(self):
        self.job.parameters["dispatcher"] = {"prefix": "FOOBAR-"}
        d = Path(self.job.mkdtemp("my-action"))
        self.assertEqual(d.parent.name, f"FOOBAR-{self.job.job_id}")

    def test_mktemp_with_override(self):
        tmp_dir_path = self.create_temporary_directory()
        override = tmp_dir_path / "override"
        first = Path(self.job.mkdtemp("my-action", override=override))
        second = Path(self.job.mkdtemp("my-assert", override=override))
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, second.parent)
        self.assertEqual(first.parent.name, str(self.job.job_id))


class TestJobTimeouts(LavaDispatcherTestCase):
    def test_job_retry_timeout(self) -> None:
        job = Factory().create_custom_job(
            "juno-uboot-01",
            yaml_safe_load(
                """
job_name: test timeouts
device_type: juno-uboot
visibility: public
timeouts:
  job:
    minutes: 15
  action:
    minutes: 10
actions:
  - deploy:
      to: tftp
      failure_retry: 5
      kernel:
         url: http://images.validation.linaro.org/d02/20151209-1510/Image
  - deploy:
      to: tftp
      failure_retry: 4
      timeout:
        minutes: 2
      kernel:
        url: http://images.validation.linaro.org/d02/20151209-1510/Image
  - deploy:
      to: tftp
      failure_retry: 5
      timeouts:
        http-download:
          minutes: 3
      kernel:
        url: http://images.validation.linaro.org/d02/20151209-1510/Image
"""
            ),
        )
        (
            no_timeout_set_action,
            timeout_set_action,
            named_timeout_action,
        ) = job.pipeline.find_all_actions(HttpDownloadAction)
        # Device sets download action timeout to 5 minutes.
        # The HTTP download should be (5 minutes) / (5 retries) = 1 minutes
        self.assertEqual(no_timeout_set_action.timeout.duration, 60)
        # Action timeout set to 2 minutes.
        # HTTP timeout should be (2 minutes) / (4 retries) = 30 seconds
        self.assertEqual(timeout_set_action.timeout.duration, 30)
        # HTTP timeout should be forced to 3 minutes
        self.assertEqual(named_timeout_action.timeout.duration, 180)

    def test_job_retry_timeout_named_priority(self) -> None:
        job = Factory().create_custom_job(
            "juno-uboot-01",
            yaml_safe_load(
                """
job_name: test timeouts
device_type: juno-uboot
visibility: public
timeouts:
  job:
    minutes: 15
  action:
    minutes: 10
  actions:
    http-download:
      minutes: 2
actions:
  - deploy:
      to: tftp
      failure_retry: 5
      kernel:
        url: http://images.validation.linaro.org/d02/20151209-1510/Image
  - deploy:
      to: tftp
      failure_retry: 4
      timeout:
        minutes: 5
      kernel:
        url: http://images.validation.linaro.org/d02/20151209-1510/Image
  - deploy:
      to: tftp
      failure_retry: 3
      timeouts:
        http-download:
          seconds: 20
      kernel:
        url: http://images.validation.linaro.org/d02/20151209-1510/Image
"""
            ),
        )
        (
            no_timeout_set_action,
            timeout_set_action,
            named_timeout_action,
        ) = job.pipeline.find_all_actions(HttpDownloadAction)
        # HTTP timeout should be forced to 2 minutes
        self.assertEqual(no_timeout_set_action.timeout.duration, 120)
        # HTTP timeout should be forced to 2 minutes
        self.assertEqual(timeout_set_action.timeout.duration, 120)
        # HTTP timeout should be forced to 20 seconds
        self.assertEqual(named_timeout_action.timeout.duration, 20)
