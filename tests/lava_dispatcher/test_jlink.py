# Copyright (C) 2019 Linaro Limited
#
# Author: Andrei Gansari <andrei.gansari@linaro.org>
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


from lava_common.exceptions import JobError
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class JLinkFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_k64f_job(self, filename):
        return self.create_job("frdm-k64f-01.jinja2", filename)

    def create_k64f_job_with_power(self, filename):
        return self.create_job("frdm-k64f-power-01.jinja2", filename)


class TestJLinkAction(StdoutTestCase):
    def test_jlink_pipeline(self):
        factory = JLinkFactory()
        job = factory.create_k64f_job(
            "sample_jobs/zephyr-frdm-k64f-jlink-test-kernel-common.yaml"
        )
        try:
            job.validate()
        except JobError as exc:
            assert (  # nosec
                str(exc)
                == "Invalid job data: ['2.1.1 flash-jlink: Unable to retrieve version of JLinkExe']\n"
            )
        description_ref = self.pipeline_reference("jlink.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        job = factory.create_k64f_job_with_power(
            "sample_jobs/zephyr-frdm-k64f-jlink-test-kernel-common.yaml"
        )
        try:
            job.validate()
        except JobError as exc:
            assert (  # nosec
                str(exc)
                == "Invalid job data: ['2.1.3 flash-jlink: Unable to retrieve version of JLinkExe']\n"
            )
        description_ref = self.pipeline_reference("jlink-with-power.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
