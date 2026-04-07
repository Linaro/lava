# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import Any

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.actions.test.shell import TestShellAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestDefinitionHandlers(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()

    def test_testshell(self):
        job = self.factory.create_kvm_job("sample_jobs/kvm.yaml")

        testshell = job.pipeline.find_action(TestShellAction)

        self.assertIsInstance(testshell, TestShellAction)
        self.assertTrue(testshell.valid)

        self.assertEqual(200, testshell.timeout.duration)

    def test_missing_handler(self):
        def set_test_from_to_bad_value(job_dict: dict[str, Any]) -> None:
            job_dict["actions"][-1]["test"]["definitions"][0][
                "from"
            ] = "unusable-handler-test"

        with self.assertRaisesRegex(
            JobError,
            "(?=No testdef_repo handler is available for)"
            "(?=.*unusable-handler-test)",
        ):
            self.factory.create_job(
                "kvm01",
                "sample_jobs/kvm.yaml",
                validate=False,
                job_dict_preprocessor=set_test_from_to_bad_value,
            )

    def test_eventpatterns(self):
        job = self.factory.create_kvm_job("sample_jobs/kvm.yaml")

        testshell = job.pipeline.find_action(TestShellAction)

        self.assertTrue(testshell.valid)
        self.assertFalse(testshell.check_patterns("exit", None))
        self.assertRaises(InfrastructureError, testshell.check_patterns, "eof", None)
        self.assertTrue(testshell.check_patterns("timeout", None))


class X86Factory(Factory):
    def create_x86_job(self, filename, device, validate=True):
        return self.create_job(device, filename, validate=validate)
