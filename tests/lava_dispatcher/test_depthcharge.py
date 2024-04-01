# Copyright (C) 2016, 2017 Collabora Ltd.
#
# Author: Tomeu Vizoso <tomeu.vizoso@collabora.com>
# Author: Guillaume Tucker <guillaume.tucker@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import unittest
from unittest.mock import patch

from lava_dispatcher.actions.boot.depthcharge import DepthchargeAction, DepthchargeRetry
from lava_dispatcher.actions.deploy.prepare import PrepareFITAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.utils import DummyLogger, infrastructure_error


class DepthchargeFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_jaq_job(self, filename):
        job = super().create_job("rk3288-veyron-jaq-01", filename)
        job.logger = DummyLogger()
        return job


class TestDepthchargeAction(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = DepthchargeFactory()

    @unittest.skipIf(infrastructure_error("mkimage"), "mkimage not installed")
    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_depthcharge(self, which_mock):
        job = self.factory.create_jaq_job("sample_jobs/depthcharge.yaml")
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference("depthcharge.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ["tftp-deploy", "depthcharge-action", "finalize"],
        )

        prep_fit = job.pipeline.find_action(PrepareFITAction)
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
-C none \
-d {kernel} \
-a {load_addr} \
-b {dtb} \
-i {ramdisk} \
{fit_path}'.format(
            **params
        )
        cmd = prep_fit._make_mkimage_command(params)
        self.assertEqual(cmd_ref, " ".join(cmd))

        depthcharge = job.pipeline.find_action(DepthchargeAction)
        self.assertEqual(
            [action.name for action in depthcharge.pipeline.actions],
            ["depthcharge-overlay", "depthcharge-retry"],
        )

        retry = depthcharge.pipeline.find_action(DepthchargeRetry)
        self.assertEqual(
            [action.name for action in retry.pipeline.actions],
            [
                "reset-connection",
                "reset-device",
                "depthcharge-start",
                "bootloader-commands",
            ],
        )
