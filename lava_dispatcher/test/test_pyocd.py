# Copyright (C) 2017 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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
from lava_dispatcher.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.test.utils import infrastructure_error


class PyocdFactory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    @unittest.skipIf(
        infrastructure_error("pyocd-flashtool"), "pyocd-flashtool not installed"
    )
    def create_k64f_job(self, filename):
        return self.create_job("frdm-k64f-01.jinja2", filename)

    @unittest.skipIf(
        infrastructure_error("pyocd-flashtool"), "pyocd-flashtool not installed"
    )
    def create_k64f_job_with_power(self, filename):  # pylint: disable=no-self-use
        return self.create_job("frdm-k64f-power-01.jinja2", filename)


class TestPyocdAction(StdoutTestCase):  # pylint: disable=too-many-public-methods
    def test_pyocd_pipeline(self):
        factory = PyocdFactory()
        job = factory.create_k64f_job(
            "sample_jobs/zephyr-frdm-k64f-pyocd-test-kernel-common.yaml"
        )
        job.validate()
        description_ref = self.pipeline_reference("pyocd.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
        job = factory.create_k64f_job_with_power(
            "sample_jobs/zephyr-frdm-k64f-pyocd-test-kernel-common.yaml"
        )
        job.validate()
        description_ref = self.pipeline_reference("pyocd-with-power.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
