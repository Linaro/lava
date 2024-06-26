# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.actions.commands import CommandAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestCommand(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-command.yaml")

    def test_pipeline(self):
        description_ref = self.pipeline_reference("kvm-command.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

        command = self.job.pipeline.find_action(CommandAction)
        self.assertEqual(command.parameters["name"], "user_command_to_run")
        self.assertEqual(command.timeout.duration, 60)
