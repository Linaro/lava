# Copyright (C) 2016 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from unittest.mock import patch

from lava_common.yaml import yaml_safe_load
from lava_dispatcher.action import Pipeline, Timeout
from lava_dispatcher.actions.deploy.iso import (
    IsoEmptyImage,
    IsoPullInstaller,
    QemuCommandLine,
)
from lava_dispatcher.actions.test.shell import TestShellAction, TestShellRetry
from lava_dispatcher.device import DeviceDict
from lava_dispatcher.job import Job
from lava_dispatcher.parser import JobParser
from lava_dispatcher.utils.strings import substitute
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.utils import DummyLogger


class InstallerFactory(Factory):
    def create_qemu_installer_job(self):
        (rendered, _) = self.create_device("kvm01.jinja2")
        device = DeviceDict.from_yaml_str(rendered)
        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs/qemu-debian-installer.yaml"
        )
        parser = JobParser()
        with open(sample_job_file) as sample_job_data:
            job = parser.parse(sample_job_data, device, 4212, None, "")
        job.logger = DummyLogger()
        return job


class TestIsoJob(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = InstallerFactory()
        self.job = factory.create_qemu_installer_job()
        self.assertIsNotNone(self.job)
        self.assertIsInstance(self.job, Job)
        self.assertIsInstance(self.job.pipeline, Pipeline)

    def test_job_reference(self):
        description_ref = self.pipeline_reference(
            "qemu-debian-installer.yaml", job=self.job
        )
        self.assertEqual(description_ref, self.job.pipeline.describe())

    @patch("lava_dispatcher.actions.deploy.iso.which", return_value="/usr/bin/in.tftpd")
    def test_iso_preparation(self, which_mock):
        self.job.validate()

        empty = self.job.pipeline.find_action(IsoEmptyImage)
        self.assertEqual(empty.size, 2 * 1024 * 1024 * 1024)

        pull = self.job.pipeline.find_action(IsoPullInstaller)
        self.assertEqual(pull.files["kernel"], "/install.amd/vmlinuz")
        self.assertEqual(pull.files["initrd"], "/install.amd/initrd.gz")
        self.assertEqual(len(pull.files.keys()), 2)

    @patch("lava_dispatcher.actions.deploy.iso.which", return_value="/usr/bin/in.tftpd")
    def test_command_line(self, which_mock):
        self.job.validate()

        prepare = self.job.pipeline.find_action(QemuCommandLine)
        self.assertEqual(prepare.boot_order, "-boot c")
        self.assertEqual(prepare.console, "console=ttyS0,115200")
        self.assertIsNotNone(prepare.preseed_url)
        self.assertIn("-nographic", prepare.sub_command)
        self.assertIn(prepare.boot_order, prepare.sub_command)
        self.assertIn(" -drive format=raw,file={emptyimage} ", prepare.sub_command)
        self.assertIn("-append", prepare.command_line)
        self.assertIn("auto=true", prepare.command_line)
        self.assertIn("DEBIAN_FRONTEND=text", prepare.command_line)
        self.assertIn("{preseed} ---", prepare.command_line)
        self.assertIn("tftp://", prepare.command_line)
        self.assertIsNotNone(prepare.parameters["deployment_data"]["prompts"])

    def test_substitutions(self):
        sub_command = [
            "/usr/bin/qemu-system-x86_64",
            "-nographic",
            "-enable-kvm",
            "-cpu host",
            "-net nic,model=virtio,macaddr=52:54:00:12:34:58 -net user",
            "-m 2048",
            " -drive format=raw,file={emptyimage} ",
            "-boot c",
        ]
        substitutions = {
            "{emptyimage}": "/tmp/tmp.00000/hd.img"  # nosec unit test support.
        }
        sub_command = substitute(sub_command, substitutions)
        self.assertNotIn("{emptyimage}", sub_command)
        self.assertNotIn(
            "/tmp/tmp.00000/hd.img", sub_command  # nosec unit test support.
        )
        self.assertIn(
            "/tmp/tmp.00000/hd.img", " ".join(sub_command)  # nosec unit test support.
        )

    def test_timeout_inheritance(self):
        """
        test that classes pick up block timeouts

        Each action in the pipeline needs to pick up the timeout
        specified in the job definition block for the top level parent action.
        """
        test_retry = self.job.pipeline.find_action(TestShellRetry)

        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs/qemu-debian-installer.yaml"
        )
        with open(sample_job_file) as jobdef:
            data = yaml_safe_load(jobdef)
        testdata = [block["test"] for block in data["actions"] if "test" in block][0]
        duration = Timeout.parse(testdata["timeout"])
        self.assertEqual(duration, test_retry.timeout.duration)
        shell = test_retry.pipeline.find_action(TestShellAction)
        self.assertEqual(duration, shell.timeout.duration)
        if shell.timeout.duration > shell.connection_timeout.duration:
            self.assertEqual(duration, shell.timeout.duration)
        else:
            self.fail("Incorrect timeout calculation")
