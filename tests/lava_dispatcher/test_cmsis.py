# Copyright (C) 2016 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from lava_common.exceptions import JobError
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class Cmsis_Factory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_k64f_job(self, filename):
        return self.create_job("frdm-k64f-01.jinja2", filename)

    def create_k64f_job_with_power(self, filename):
        return self.create_job("frdm-k64f-power-01.jinja2", filename)


class TestCMSISAction(StdoutTestCase):
    def test_usb_mass_exists(self):
        factory = Cmsis_Factory()
        job = factory.create_k64f_job(
            "sample_jobs/zephyr-frdm-k64f-cmsis-test-kernel-common.yaml"
        )
        job.device["actions"]["boot"]["methods"]["cmsis-dap"]["parameters"][
            "usb_mass_device"
        ] = ""
        self.assertRaises(JobError, job.validate)
        self.assertIn("usb_mass_device unset", job.pipeline.errors)
        job = factory.create_k64f_job(
            "sample_jobs/zephyr-frdm-k64f-cmsis-test-kernel-common.yaml"
        )
        job.device["actions"]["boot"]["methods"]["cmsis-dap"]["parameters"][
            "usb_mass_device"
        ] = "/dev/null"
        try:
            job.validate()
        except Exception as e:
            self.fail("Encountered an unexpected exception: %s" % e)
        self.assertEqual(job.pipeline.errors, [])

    def test_cmsis_pipeline(self):
        factory = Cmsis_Factory()
        job = factory.create_k64f_job(
            "sample_jobs/zephyr-frdm-k64f-cmsis-test-kernel-common.yaml"
        )
        job.device["actions"]["boot"]["methods"]["cmsis-dap"]["parameters"][
            "usb_mass_device"
        ] = "/dev/null"
        job.validate()
        description_ref = self.pipeline_reference("cmsis.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        job = factory.create_k64f_job_with_power(
            "sample_jobs/zephyr-frdm-k64f-cmsis-test-kernel-common.yaml"
        )
        job.device["actions"]["boot"]["methods"]["cmsis-dap"]["parameters"][
            "usb_mass_device"
        ] = "/dev/null"
        job.validate()
        description_ref = self.pipeline_reference("cmsis-with-power.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
