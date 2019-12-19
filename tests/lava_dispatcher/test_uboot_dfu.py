# Copyright (C) 2019 Linaro Limited
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

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.lava_dispatcher.utils import infrastructure_error


class UBootDFUFactory(Factory):
    def create_rzn1d_job(self, filename):
        return self.create_job("rzn1d-01.jinja2", filename)


class TestUbootDFUAction(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = UBootDFUFactory()

    @unittest.skipIf(infrastructure_error("dfu-util"), "dfu-util not installed")
    def test_enter_dfu_action(self):
        job = self.factory.create_rzn1d_job("sample_jobs/rzn1d-dfu.yaml")
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference("rzn1d-dfu.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())
