# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import patch

from lava_dispatcher.actions.boot import AutoLoginAction
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.actions.boot.kexec import BootKexecAction, KexecAction
from lava_dispatcher.actions.test.shell import TestShellRetry
from lava_dispatcher.shell import ExpectShellSession
from tests.lava_dispatcher.test_basic import StdoutTestCase
from tests.lava_dispatcher.test_uboot import UBootFactory


class TestKExec(StdoutTestCase):
    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_deploy_parameters(self, which_mock):
        factory = UBootFactory()
        job = factory.create_bbb_job("sample_jobs/kexec.yaml")
        self.assertIsNotNone(job)

        # Check Pipeline
        description_ref = self.pipeline_reference("kexec.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        # Check kexec specific options
        job.validate()
        self.assertIsInstance(job.pipeline.actions[2], TestShellRetry)
        self.assertIsInstance(job.pipeline.actions[3], BootKexecAction)
        kexec = job.pipeline.actions[3]
        self.assertIsInstance(kexec.pipeline.actions[0], KexecAction)
        self.assertIsInstance(kexec.pipeline.actions[1], AutoLoginAction)
        self.assertIsInstance(kexec.pipeline.actions[2], ExpectShellSession)
        self.assertIsInstance(kexec.pipeline.actions[3], ExportDeviceEnvironment)
        self.assertIn("kernel", kexec.parameters)
        self.assertIn("command", kexec.parameters)
        self.assertIn("method", kexec.parameters)
        self.assertIn("dtb", kexec.parameters)
        self.assertIn("options", kexec.parameters)
        self.assertIn("kernel-config", kexec.parameters)
        self.assertTrue(kexec.valid)
        self.assertEqual(
            "/sbin/kexec --load /home/vmlinux --dtb /home/dtb --initrd /home/initrd --reuse-cmdline",
            kexec.pipeline.actions[0].load_command,
        )
        self.assertEqual("/sbin/kexec -e", kexec.pipeline.actions[0].command)
        self.assertIsNotNone(kexec.pipeline.actions[0].parameters["boot_message"])

        self.assertIsNotNone(kexec.pipeline.actions[0].name)
        self.assertIsNotNone(kexec.pipeline.actions[0].level)
        self.assertEqual(kexec.pipeline.actions[0].timeout.duration, 45)
