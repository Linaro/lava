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

import unittest
import os

from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.test.utils import DummyLogger


class UserCommandFactory(Factory):
    def create_b2260_job(self, filename):
        device = NewDevice(os.path.join(os.path.dirname(__file__), "../devices/b2260-01.yaml"))
        with open(os.path.join(os.path.dirname(__file__), filename)) as f_in:
            parser = JobParser()
            job = parser.parse(f_in, device, 456, None, "")
        job.logger = DummyLogger()
        return job


class TestUserCommand(StdoutTestCase):

    def test_pipeline(self):
        factory = UserCommandFactory()
        job = factory.create_b2260_job('sample_jobs/b2260-user-command.yaml')
        job.validate()
        description_ref = self.pipeline_reference('b2260-user-command.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
