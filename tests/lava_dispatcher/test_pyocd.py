# Copyright (C) 2017 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import unittest

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.actions.boot.pyocd import FlashPyOCDAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


def is_pyocd_installed() -> bool:
    try:
        FlashPyOCDAction.find_pyocd_binary()
        return True
    except InfrastructureError:
        return False


class PyocdFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    @unittest.skipUnless(
        is_pyocd_installed(),
        "pyocd or pyocd-flashtool is not installed",
    )
    def create_k64f_job(self, filename):
        return self.create_job("frdm-k64f-01", filename)

    @unittest.skipUnless(
        is_pyocd_installed(),
        "pyocd or pyocd-flashtool is not installed",
    )
    def create_k64f_job_with_power(self, filename):
        return self.create_job("frdm-k64f-power-01", filename)


class TestPyocdAction(LavaDispatcherTestCase):
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
