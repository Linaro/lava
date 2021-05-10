# Copyright (C) 2021 Arm Limited
#
# Author: Malcolm Brooks <malcolm.brooks@arm.com>
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

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class N1sdpFactory(Factory):
    def create_n1sdp_job(self, filename):  # pylint: disable=no-self-use
        return self.create_job("n1sdp-01.jinja2", filename)


class TestN1sdp(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = N1sdpFactory()
        self.job = self.factory.create_n1sdp_job(
            "sample_jobs/n1sdp-fw-grub-ramdisk.yaml"
        )

    def test_pipeline(self):
        self.job.validate()
        description_ref = self.pipeline_reference(
            "n1sdp-fw-grub-ramdisk.yaml", job=self.job
        )
        self.assertEqual(description_ref, self.job.pipeline.describe(False))
