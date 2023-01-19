# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
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
