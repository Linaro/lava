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

import unittest

from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction


def find_autologin(job):
    for action in job.pipeline.actions:
        if action.internal_pipeline:
            for action in action.internal_pipeline.actions:
                if isinstance(action, AutoLoginAction):
                    return True
    return False


class TestMonitorPipeline(unittest.TestCase):

    def test_autologin_normal_kvm(self):
        factory = Factory()
        job = factory.create_kvm_job('sample_jobs/kvm.yaml', mkdtemp())
        job.validate()
        self.assertTrue(find_autologin(job))

    def test_qemu_monitor_no_prompts(self):
        factory = Factory()
        job = factory.create_kvm_job('sample_jobs/qemu-monitor.yaml', mkdtemp())
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
        job = factory.create_kvm_job('sample_jobs/kvm-notest-noprompts.yaml', mkdtemp())
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
        job = factory.create_kvm_job('sample_jobs/qemu-zephyr-monitor.yaml', mkdtemp())
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
        job = factory.create_kvm_job('sample_jobs/kvm-notest.yaml', mkdtemp())
        job.validate()
        self.assertIsNotNone(job)
        self.assertIsNotNone(job.pipeline)
        self.assertIsNotNone(job.pipeline.actions)
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        self.assertTrue(find_autologin(job))
