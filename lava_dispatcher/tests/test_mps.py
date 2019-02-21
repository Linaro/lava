# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Birch <dean.birch@linaro.org>
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

from lava_dispatcher.tests.test_basic import Factory, StdoutTestCase


class MpsFactory(Factory):
    def create_mps_job(self, filename):  # pylint: disable=no-self-use
        return self.create_job("mps2plus-01.jinja2", filename)


class TestMps(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = MpsFactory()
        self.job = self.factory.create_mps_job("sample_jobs/mps2plus.yaml")

    def test_mps_reference(self):
        self.job.validate()
        self.assertEqual([], self.job.pipeline.errors)
        description_ref = self.pipeline_reference("mps2plus.yaml")
        self.assertEqual(description_ref, self.job.pipeline.describe(False))
