# Copyright (C) 2016, 2017 Collabora Ltd.
#
# Author: Tomeu Vizoso <tomeu.vizoso@collabora.com>
# Author: Guillaume Tucker <guillaume.tucker@collabora.com>
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
from lava_dispatcher.tests.test_basic import StdoutTestCase
from lava_dispatcher.tests.utils import DummyLogger, infrastructure_error


class DepthchargeFactory:
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_jaq_job(self, filename):  # pylint: disable=no-self-use
        device = NewDevice(
            os.path.join(os.path.dirname(__file__), "devices/jaq-01.yaml")
        )
        yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "")
            job.logger = DummyLogger()
        return job


class TestDepthchargeAction(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = DepthchargeFactory()

    @unittest.skipIf(infrastructure_error("mkimage"), "mkimage not installed")
    def test_depthcharge(self):
        job = self.factory.create_jaq_job("sample_jobs/depthcharge.yaml")
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference("depthcharge.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())

        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ["tftp-deploy", "depthcharge-action", "finalize"],
        )

        tftp = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        prep_overlay = [
            action
            for action in tftp.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        prep_kernel = [
            action
            for action in prep_overlay.pipeline.actions
            if action.name == "prepare-kernel"
        ][0]
        self.assertEqual(
            [action.name for action in prep_kernel.internal_pipeline.actions],
            ["prepare-fit"],
        )

        prep_fit = [
            action
            for action in prep_kernel.pipeline.actions
            if action.name == "prepare-fit"
        ][0]
        params = {
            "arch": "neo-gothic",
            "load_addr": "0x1234",
            "kernel": "/some/zImage",
            "dtb": "/some/file.dtb",
            "ramdisk": "/some/ramdisk.cpio",
            "fit_path": "/does/not/exist",
        }
        cmd_ref = 'mkimage \
-D "-I dts -O dtb -p 2048" \
-f auto \
-A {arch} \
-O linux \
-T kernel \
-C None \
-d {kernel} \
-a {load_addr} \
-b {dtb} \
-i {ramdisk} \
{fit_path}'.format(
            **params
        )
        cmd = prep_fit._make_mkimage_command(params)  # pylint: disable=protected-access
        self.assertEqual(cmd_ref, " ".join(cmd))

        depthcharge = [
            action
            for action in job.pipeline.actions
            if action.name == "depthcharge-action"
        ][0]
        self.assertEqual(
            [action.name for action in depthcharge.internal_pipeline.actions],
            ["depthcharge-overlay", "connect-device", "depthcharge-retry"],
        )

        retry = [
            action
            for action in depthcharge.internal_pipeline.actions
            if action.name == "depthcharge-retry"
        ][0]
        self.assertEqual(
            [action.name for action in retry.internal_pipeline.actions],
            ["reset-device", "depthcharge-start", "bootloader-commands"],
        )
