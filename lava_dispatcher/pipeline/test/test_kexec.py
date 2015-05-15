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


import os
import unittest
from lava_dispatcher.pipeline.test.test_basic import pipeline_reference
from lava_dispatcher.pipeline.test.test_uboot import Factory
from lava_dispatcher.pipeline.actions.boot.kexec import BootKexecAction, KexecAction
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.actions.test.shell import TestShellRetry


class TestKExec(unittest.TestCase):

    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_deploy_parameters(self):
        factory = Factory()
        job = factory.create_bbb_job('sample_jobs/kexec.yaml')
        self.assertIsNotNone(job)

        # Check Pipeline
        description_ref = pipeline_reference('kexec.yaml')
        self.assertEqual(description_ref, job.pipeline.describe(False))

        # Check kexec specific options
        job.validate()
        self.assertIsInstance(job.pipeline.actions[2], TestShellRetry)
        self.assertIsInstance(job.pipeline.actions[3], BootKexecAction)
        kexec = job.pipeline.actions[3]
        self.assertIsInstance(kexec.internal_pipeline.actions[0], KexecAction)
        self.assertIsInstance(kexec.internal_pipeline.actions[1], AutoLoginAction)
        self.assertIsInstance(kexec.internal_pipeline.actions[2], ExpectShellSession)
        self.assertIsInstance(kexec.internal_pipeline.actions[3],
                              ExportDeviceEnvironment)
        self.assertIn('kernel', kexec.parameters)
        self.assertIn('command', kexec.parameters)
        self.assertIn('method', kexec.parameters)
        self.assertIn('dtb', kexec.parameters)
        self.assertIn('options', kexec.parameters)
        self.assertIn('kernel-config', kexec.parameters)
        self.assertTrue(kexec.valid)
        self.assertEqual(
            '/sbin/kexec --load /home/vmlinux --dtb /home/dtb --initrd /home/initrd --reuse-cmdline',
            kexec.internal_pipeline.actions[0].load_command
        )
        self.assertEqual(
            '/sbin/kexec -e',
            kexec.internal_pipeline.actions[0].command
        )
        self.assertIsNotNone(kexec.internal_pipeline.actions[0].parameters['boot_message'])
        self.assertEqual(kexec.internal_pipeline.actions[0].timeout.duration, 45)
