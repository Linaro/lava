# Copyright (C) 2019 Pengutronix e.K.
#
# Author: Michael Grzeschik <m.grzeschik@pengutronix.de>
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
from unittest.mock import patch
from lava_common.compat import yaml_safe_load
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.actions.boot.barebox import BareboxAction
from lava_dispatcher.actions.deploy.apply_overlay import CompressRamdisk
from lava_dispatcher.actions.deploy.tftp import TftpAction
from lava_dispatcher.tests.test_basic import Factory, StdoutTestCase
from lava_dispatcher.utils.filesystem import tftpd_dir


class BareboxFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_bbb_job(self, filename):
        return self.create_job("bbb-03-barebox.jinja2", filename)


class TestBareboxAction(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = BareboxFactory()

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_tftp_pipeline(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/barebox-ramdisk.yaml")
        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ["tftp-deploy", "barebox-action", "lava-test-retry", "finalize"],
        )
        tftp = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        self.assertTrue(
            tftp.get_namespace_data(action=tftp.name, label="tftp", key="ramdisk")
        )
        self.assertIsNotNone(tftp.internal_pipeline)
        self.assertEqual(
            [action.name for action in tftp.internal_pipeline.actions],
            [
                "download-retry",
                "download-retry",
                "download-retry",
                "prepare-tftp-overlay",
                "lxc-create-udev-rule-action",
                "deploy-device-env",
            ],
        )
        self.assertIn(
            "ramdisk",
            [
                action.key
                for action in tftp.internal_pipeline.actions
                if hasattr(action, "key")
            ],
        )
        self.assertIn(
            "kernel",
            [
                action.key
                for action in tftp.internal_pipeline.actions
                if hasattr(action, "key")
            ],
        )
        self.assertIn(
            "dtb",
            [
                action.key
                for action in tftp.internal_pipeline.actions
                if hasattr(action, "key")
            ],
        )
        self.assertNotIn("=", tftpd_dir())
        job.validate()
        tftp.validate()
        self.assertEqual([], tftp.errors)

    def test_device_bbb(self):
        job = self.factory.create_bbb_job("sample_jobs/barebox.yaml")
        self.assertEqual(
            job.device["commands"]["connections"]["uart0"]["connect"],
            "telnet localhost 6000",
        )
        self.assertEqual(job.device["commands"].get("interrupt", " "), " ")
        methods = job.device["actions"]["boot"]["methods"]
        self.assertIn("barebox", methods)
        self.assertEqual(
            methods["barebox"]["parameters"].get("bootloader_prompt"),
            "TI AM335x BeagleBone black:/",
        )

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_barebox_action(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/barebox-ramdisk.yaml")
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn("barebox", job.device["actions"]["boot"]["methods"])
        params = job.device["actions"]["deploy"]["parameters"]
        boot_message = params.get(
            "boot_message", job.device.get_constant("kernel-start-message")
        )
        self.assertIsNotNone(boot_message)
        for action in job.pipeline.actions:
            action.validate()
            if isinstance(action, BareboxAction):
                self.assertIn("method", action.parameters)
                self.assertEqual("barebox", action.parameters["method"])
                self.assertEqual(
                    "reboot: Restarting system",
                    action.parameters.get("parameters", {}).get(
                        "shutdown-message", job.device.get_constant("shutdown-message")
                    ),
                )
            if isinstance(action, TftpAction):
                self.assertIn("ramdisk", action.parameters)
                self.assertIn("kernel", action.parameters)
                self.assertIn("to", action.parameters)
                self.assertEqual("tftp", action.parameters["to"])
            if isinstance(action, CompressRamdisk):
                self.assertEqual(action.mkimage_arch, "arm")
            self.assertTrue(action.valid)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_boot_commands(self, which_mock):
        job = self.factory.create_bbb_job(
            "sample_jobs/barebox-ramdisk-inline-commands.yaml"
        )
        job.validate()
        barebox = [
            action for action in job.pipeline.actions if action.name == "barebox-action"
        ][0]
        overlay = [
            action
            for action in barebox.internal_pipeline.actions
            if action.name == "bootloader-overlay"
        ][0]
        self.assertEqual(
            overlay.commands, ["a list", "of commands", "with a load_addr substitution"]
        )

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_download_action(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/barebox.yaml")
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        deploy = None
        overlay = None
        extract = None
        for action in job.pipeline.actions:
            if action.name == "tftp-deploy":
                deploy = action
        if deploy:
            for action in deploy.internal_pipeline.actions:
                if action.name == "prepare-tftp-overlay":
                    overlay = action
        if overlay:
            for action in overlay.internal_pipeline.actions:
                if action.name == "extract-nfsrootfs":
                    extract = action
        test_dir = overlay.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        self.assertIsNotNone(test_dir)
        self.assertIn("/lava-", test_dir)
        self.assertIsNotNone(extract)
        self.assertEqual(extract.timeout.duration, 240)


class TestKernelConversion(StdoutTestCase):
    def setUp(self):
        self.device = NewDevice(
            os.path.join(os.path.dirname(__file__), "devices/bbb-01-barebox.yaml")
        )
        bbb_yaml = os.path.join(
            os.path.dirname(__file__), "sample_jobs/barebox-ramdisk.yaml"
        )
        with open(bbb_yaml) as sample_job_data:
            self.base_data = yaml_safe_load(sample_job_data)
        self.deploy_block = [
            block for block in self.base_data["actions"] if "deploy" in block
        ][0]["deploy"]
        self.boot_block = [
            block for block in self.base_data["actions"] if "boot" in block
        ][0]["boot"]
        self.parser = JobParser()
