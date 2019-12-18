# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
        self.assertEqual(description_ref, job.pipeline.describe(False))
