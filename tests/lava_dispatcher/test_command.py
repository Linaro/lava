# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class TestCommand(StdoutTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-command.yaml")

    def test_pipeline(self):
        description_ref = self.pipeline_reference("kvm-command.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

        command = [
            action
            for action in self.job.pipeline.actions
            if action.name == "user-command"
        ][0]
        self.assertEqual(command.parameters["name"], "user_command_to_run")
        self.assertEqual(command.timeout.duration, 60)
