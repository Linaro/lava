# Copyright (C) 2019 Linaro Limited
#
# Author: Andrei Gansari <andrei.gansari@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


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
                == "Invalid job data: ['2.2 flash-jlink: Unable to retrieve version of JLinkExe']\n"
            )
        description_ref = self.pipeline_reference("jlink.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        job = factory.create_k64f_job_with_power(
            "sample_jobs/zephyr-frdm-k64f-jlink-test-kernel-common.yaml"
        )
        try:
            job.validate()
        except JobError as exc:
            assert (  # nosec
                str(exc)
                == "Invalid job data: ['2.4 flash-jlink: Unable to retrieve version of JLinkExe']\n"
            )
        description_ref = self.pipeline_reference("jlink-with-power.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
