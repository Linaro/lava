# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import patch

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class UserCommandFactory(Factory):
    def create_b2260_job(self, filename):
        return self.create_job("b2260-01.jinja2", filename)


class TestUserCommand(StdoutTestCase):
    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_pipeline(self, which_mock):
        factory = UserCommandFactory()
        job = factory.create_b2260_job("sample_jobs/b2260-user-command.yaml")
        job.validate()
        description_ref = self.pipeline_reference("b2260-user-command.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
