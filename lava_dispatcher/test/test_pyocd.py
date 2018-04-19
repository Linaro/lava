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


import os
import unittest
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.test.utils import DummyLogger, infrastructure_error


class Pyocd_Factory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    @unittest.skipIf(infrastructure_error('pyocd-flashtool'), 'pyocd-flashtool not installed')
    def create_k64f_job(self, filename):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/frdm-k64f-01.yaml'))
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4999, None, "")
        job.logger = DummyLogger()
        return job

    @unittest.skipIf(infrastructure_error('pyocd-flashtool'), 'pyocd-flashtool not installed')
    def create_k64f_job_with_power(self, filename):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/frdm-k64f-01-with-power.yaml'))
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 5999, None, "")
        job.logger = DummyLogger()
        return job


class TestPyocdAction(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def test_pyocd_pipeline(self):
        factory = Pyocd_Factory()
        job = factory.create_k64f_job('sample_jobs/zephyr-frdm-k64f-pyocd-test-kernel-common.yaml')
        job.validate()
        description_ref = self.pipeline_reference('pyocd.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
        job = factory.create_k64f_job_with_power('sample_jobs/zephyr-frdm-k64f-pyocd-test-kernel-common.yaml')
        job.validate()
        description_ref = self.pipeline_reference('pyocd-with-power.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
