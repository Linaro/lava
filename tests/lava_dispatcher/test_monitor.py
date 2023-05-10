# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.actions.boot import AutoLoginAction
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


def find_autologin(job):
    for action in job.pipeline.actions:
        if action.pipeline:
            for action in action.pipeline.actions:
                if isinstance(action, AutoLoginAction):
                    return True
    return False


class TestMonitorPipeline(StdoutTestCase):
    def test_autologin_normal_kvm(self):
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/kvm.yaml")
        job.validate()
        self.assertTrue(find_autologin(job))

    def test_qemu_monitor_no_prompts(self):
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/qemu-monitor.yaml")
        job.validate()
        self.assertIsNotNone(job)
        self.assertIsNotNone(job.pipeline)
        self.assertIsNotNone(job.pipeline.actions)
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        self.assertFalse(find_autologin(job))

    def test_qemu_monitor_notest_noprompts(self):
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/kvm-notest-noprompts.yaml")
        job.validate()
        self.assertIsNotNone(job)
        self.assertIsNotNone(job.pipeline)
        self.assertIsNotNone(job.pipeline.actions)
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        self.assertFalse(find_autologin(job))

    def test_qemu_monitor_zephyr_job(self):
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/zephyr-qemu-test-task.yaml")
        job.validate()
        self.assertIsNotNone(job)
        self.assertIsNotNone(job.pipeline)
        self.assertIsNotNone(job.pipeline.actions)
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        self.assertFalse(find_autologin(job))

    def test_qemu_notest(self):
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/kvm-notest.yaml")
        job.validate()
        self.assertIsNotNone(job)
        self.assertIsNotNone(job.pipeline)
        self.assertIsNotNone(job.pipeline.actions)
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        self.assertTrue(find_autologin(job))
