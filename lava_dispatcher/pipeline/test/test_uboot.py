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
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.boot.u_boot import UBootAction
from lava_dispatcher.pipeline.actions.deploy.tftp import TftpAction


class Factory(object):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_job(self, filename, output_dir=None):  # pylint: disable=no-self-use
        device = NewDevice('bbb-01')
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        sample_job_data = open(kvm_yaml)
        parser = JobParser()
        job = parser.parse(sample_job_data, device, output_dir=output_dir)
        return job


class TestUbootAction(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_simulated_action(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/uboot.yaml')
        self.assertIsNotNone(job)
        self.assertIsNone(job.validate())
        self.assertEqual(job.device.parameters['device_type'], 'beaglebone-black')

    def test_tftp_pipeline(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/uboot.yaml')
        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ['tftp-deploy', 'uboot-action', 'lava-test-retry', 'submit_results', 'finalize']
        )
        tftp = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        self.assertIsNotNone(tftp.internal_pipeline)
        self.assertEqual(
            [action.name for action in tftp.internal_pipeline.actions],
            ['download_retry', 'download_retry', 'download_retry', 'prepare-tftp-overlay']
        )
        self.assertIn('ramdisk', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertIn('kernel', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertIn('dtb', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertEqual(
            [action.path for action in tftp.internal_pipeline.actions if hasattr(action, 'path')],
            ["/var/lib/lava/dispatcher/tmp" for item in range(len(tftp.internal_pipeline.actions) - 1)]  # pylint: disable=unused-variable
        )

    def test_device_bbb(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/uboot.yaml')
        self.assertEqual(
            job.device.parameters['commands']['connect'],
            'telnet localhost 6000'
        )
        self.assertEqual(job.device.parameters['commands'].get('interrupt', ' '), ' ')
        items = []
        items.extend([item['u-boot'] for item in job.device.parameters['actions']['boot']['methods']])
        for item in items:
            self.assertEqual(item['parameters'].get('bootloader_prompt', None), 'U-Boot')

    def test_uboot_action(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/uboot.yaml')
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn('u-boot', [item.keys() for item in job.device.parameters['actions']['boot']['methods']][0])
        for action in job.pipeline.actions:
            action.validate()
            if isinstance(action, UBootAction):
                self.assertIn('u-boot', action.parameters.keys())
            if isinstance(action, TftpAction):
                self.assertIn('ramdisk', action.parameters.keys())
                self.assertIn('kernel', action.parameters.keys())
                self.assertEqual(action.parameters['methods'], ['tftp'])
            self.assertTrue(action.valid)
        # FIXME: a more elegant introspection of the pipeline would be useful here
        tftp = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        types = []
        items = []
        items.extend([item['u-boot'] for item in job.device.parameters['actions']['boot']['methods']])
        items = items[0]
        for action in tftp.internal_pipeline.actions:
            types.extend([action.key for action in action.internal_pipeline.actions if hasattr(action, 'key') and action.key != 'parameters'])
        for command in types:
            if command == 'ramdisk':
                self.assertIsNotNone(items.get(command, None))
                # print items[command]
            else:
                self.assertIsNone(items.get(command, None))
        for line in job.context['u-boot']['commands']:
            # check substitutions have taken place
            self.assertNotIn('{SERVER_IP}', line)
            self.assertNotIn('{KERNEL_ADDR}', line)
            self.assertNotIn('{DTB_ADDR}', line)
            self.assertNotIn('{RAMDISK_ADDR}', line)
            self.assertNotIn('{BOOTX}', line)

    def test_download_action(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/uboot.yaml')
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIsNotNone(job.context['download_action']['kernel']['file'])
        self.assertIsNotNone(job.context['download_action']['ramdisk']['file'])
        self.assertIsNotNone(job.context['download_action']['dtb']['file'])
