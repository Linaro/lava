# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import patch

from lava_dispatcher.actions.commands import CommandAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class UserCommandFactory(Factory):
    def create_b2260_job(self, filename):
        return self.create_job("b2260-01", filename)


class TestIsCommand(LavaDispatcherTestCase):
    def test_valid(self):
        for cmd in ["/bin/true", ["/bin/true"], ["/bin/true", "/bin/false"]]:
            self.assertTrue(CommandAction.is_command(cmd), cmd)

    def test_invalid(self):
        # Empty commands would silently run nothing, so they are rejected
        # alongside the values that are not commands at all.
        for cmd in ["", [], [""], ["/bin/true", ""], None, 1, [1], {"do": "/bin/true"}]:
            self.assertFalse(CommandAction.is_command(cmd), cmd)


class TestUserCommand(LavaDispatcherTestCase):
    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_pipeline(self, which_mock):
        factory = UserCommandFactory()
        job = factory.create_b2260_job("sample_jobs/b2260-user-command.yaml")
        job.validate()
        description_ref = self.pipeline_reference("b2260-user-command.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
