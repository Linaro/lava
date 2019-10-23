# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

from unittest.mock import patch
from lava_dispatcher.tests.test_basic import StdoutTestCase
from lava_dispatcher.tests.test_uboot import UBootFactory
from lava_dispatcher.actions.boot.kexec import BootKexecAction, KexecAction
from lava_dispatcher.actions.boot import AutoLoginAction
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.actions.test.shell import TestShellRetry


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
        self.assertEqual(description_ref, job.pipeline.describe(False))

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
