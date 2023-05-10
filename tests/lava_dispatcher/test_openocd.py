# Copyright (C) 2019 Linaro Limited
#
# Author: Vincent Wan <vincent.wan@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import unittest

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.utils.shell import which
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import infrastructure_error


def check_openocd():
    try:
        which("openocd")
        return False
    except InfrastructureError:
        return True


class OpenOCDFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    @unittest.skipIf(infrastructure_error("openocd"), "openocd not installed")
    def create_cc3230SF_job(self, filename):
        return self.create_job("cc3220SF-02.jinja2", filename)


class TestOpenOCDAction(StdoutTestCase):
    @unittest.skipIf(check_openocd(), "openocd not available")
    def test_openocd_pipeline(self):
        factory = OpenOCDFactory()
        job = factory.create_cc3230SF_job("sample_jobs/cc3220SF-openocd.yaml")
        job.validate()
        description_ref = self.pipeline_reference("openocd.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        # Check FlashOpenOCDAction
        action = job.pipeline.actions[1].pipeline.actions[0]
        self.assertEqual(action.name, "connect-device")

        action = job.pipeline.actions[1].pipeline.actions[1]
        self.assertEqual(action.name, "flash-openocd")
        self.assertEqual(len(action.base_command), 24)
        print(action.base_command)
        self.assertEqual(action.base_command[0], "openocd")
        self.assertEqual(action.base_command[1], "-f")
        self.assertEqual(action.base_command[2], "board/ti_cc3220sf_launchpad.cfg")
        self.assertEqual(action.base_command[5], "-d2")
        self.assertEqual(action.base_command[23], "shutdown")
