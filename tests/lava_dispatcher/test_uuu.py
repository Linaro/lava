# Copyright 2019-2020 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
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


class UUUBootFactory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_imx8mq_job(self, filename):
        return self.create_job("imx8mq-evk-01.jinja2", filename)


class TestUUUbootAction(StdoutTestCase):  # pylint: disable=too-many-public-methods
    def setUp(self):
        super().setUp()
        self.factory = UUUBootFactory()

    @patch("lava_dispatcher.actions.boot.uuu.which", return_value="/bin/test_uuu")
    def test_pipeline_uuu_only_uboot(self, which_mock):
        job = self.factory.create_imx8mq_job("sample_jobs/uuu-bootimage-only.yaml")
        self.assertIsNotNone(job)

        # Test that generated pipeline is the same as defined in pipeline_refs
        description_ref = self.pipeline_reference("uuu-bootimage-only.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())
