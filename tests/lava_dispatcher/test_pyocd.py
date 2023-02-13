# Copyright (C) 2017 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import unittest

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import infrastructure_error


class PyocdFactory(Factory):
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
    def create_k64f_job_with_power(self, filename):
        return self.create_job("frdm-k64f-power-01.jinja2", filename)


class TestPyocdAction(StdoutTestCase):
    def test_pyocd_pipeline(self):
        factory = PyocdFactory()
        job = factory.create_k64f_job(
            "sample_jobs/zephyr-frdm-k64f-pyocd-test-kernel-common.yaml"
        )
        job.validate()
        description_ref = self.pipeline_reference("pyocd.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        job = factory.create_k64f_job_with_power(
            "sample_jobs/zephyr-frdm-k64f-pyocd-test-kernel-common.yaml"
        )
        job.validate()
        description_ref = self.pipeline_reference("pyocd-with-power.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
