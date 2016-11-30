# Copyright (C) 2016 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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
import yaml
import unittest
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.boot.grub import (
    GrubMainAction,
    BootloaderCommandOverlay
)
from lava_dispatcher.pipeline.actions.deploy.tftp import TftpAction
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.action import Pipeline, InfrastructureError
from lava_dispatcher.pipeline.test.test_basic import pipeline_reference
from lava_dispatcher.pipeline.utils.network import dispatcher_ip
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp, tftpd_dir
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.constants import (
    BOOT_MESSAGE
)


class Factory(object):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/d02-01.yaml'))
        yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, None, None,
                               output_dir=output_dir)
        return job


class TestGrubAction(unittest.TestCase):  # pylint: disable=too-many-public-methods

    @unittest.skipIf(infrastructure_error('mkimage'), "u-boot-tools not installed")
    def test_simulated_action(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/grub-ramdisk.yaml')
        self.assertIsNotNone(job)

        # uboot and uboot-ramdisk have the same pipeline structure
        description_ref = pipeline_reference('grub.yaml')
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())
        self.assertEqual(job.device['device_type'], 'd02')

    def test_tftp_pipeline(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/grub-ramdisk.yaml')
        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ['tftp-deploy', 'grub-main-action', 'lava-test-retry', 'finalize']
        )
        tftp = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        self.assertTrue(tftp.get_common_data('tftp', 'ramdisk'))
        self.assertIsNotNone(tftp.internal_pipeline)
        self.assertEqual(
            [action.name for action in tftp.internal_pipeline.actions],
            ['download_retry', 'download_retry', 'download_retry', 'prepare-tftp-overlay', 'deploy-device-env']
        )
        self.assertIn('ramdisk', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertIn('kernel', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertIn('dtb', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertNotIn('=', tftpd_dir())

    def test_device_d02(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/grub-ramdisk.yaml')
        self.assertEqual(
            job.device['commands']['connect'],
            'telnet ratchet 7003'
        )
        self.assertEqual(job.device['commands'].get('interrupt', ' '), ' ')
        methods = job.device['actions']['boot']['methods']
        self.assertIn('grub', methods)
        self.assertEqual(methods['grub']['parameters'].get('bootloader_prompt', None), 'grub>')

    @unittest.skipIf(infrastructure_error('mkimage'), "u-boot-tools not installed")
    def test_grub_action(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/grub-ramdisk.yaml')
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn('grub', job.device['actions']['boot']['methods'])
        params = job.device['actions']['boot']['methods']['grub']['parameters']
        boot_message = params.get('boot_message', BOOT_MESSAGE)
        self.assertIsNotNone(boot_message)
        for action in job.pipeline.actions:
            action.validate()
            if isinstance(action, GrubMainAction):
                self.assertIn('method', action.parameters)
                self.assertEqual('grub', action.parameters['method'])
            if isinstance(action, TftpAction):
                self.assertIn('ramdisk', action.parameters)
                self.assertIn('kernel', action.parameters)
                self.assertIn('to', action.parameters)
                self.assertEqual('tftp', action.parameters['to'])
            self.assertTrue(action.valid)

    def test_overlay_action(self):  # pylint: disable=too-many-locals
        parameters = {
            'device_type': 'd02',
            'job_name': 'grub-standard-ramdisk',
            'job_timeout': '15m',
            'action_timeout': '5m',
            'priority': 'medium',
            'output_dir': mkdtemp(),
            'actions': {
                'boot': {
                    'method': 'grub',
                    'commands': 'ramdisk',
                    'prompts': ['linaro-test', 'root@debian:~#']
                },
                'deploy': {
                    'ramdisk': 'initrd.gz',
                    'kernel': 'zImage',
                    'dtb': 'broken.dtb'
                }
            }
        }
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/d02-01.yaml'))
        job = Job(4212, None, None, None, parameters)
        job.device = device
        pipeline = Pipeline(job=job, parameters=parameters['actions']['boot'])
        job.pipeline = pipeline
        overlay = BootloaderCommandOverlay()
        pipeline.add_action(overlay)
        try:
            ip_addr = dispatcher_ip()
        except InfrastructureError as exc:
            raise RuntimeError("Unable to get dispatcher IP address: %s" % exc)
        parsed = []
        kernel = parameters['actions']['deploy']['kernel']
        ramdisk = parameters['actions']['deploy']['ramdisk']
        dtb = parameters['actions']['deploy']['dtb']

        substitution_dictionary = {
            '{SERVER_IP}': ip_addr,
            # the addresses need to be hexadecimal
            '{RAMDISK}': ramdisk,
            '{KERNEL}': kernel,
            '{DTB}': dtb
        }
        params = device['actions']['boot']['methods']
        commands = params['grub']['ramdisk']['commands']
        self.assertIn('net_bootp', commands)
        self.assertIn("linux (tftp,{SERVER_IP})/{KERNEL} console=ttyS0,115200 earlycon=uart8250,mmio32,0x80300000 root=/dev/ram0 ip=dhcp", commands)
        self.assertIn('initrd (tftp,{SERVER_IP})/{RAMDISK}', commands)
        self.assertIn('devicetree (tftp,{SERVER_IP})/{DTB}', commands)

        params['grub']['ramdisk']['commands'] = substitute(params['grub']['ramdisk']['commands'], substitution_dictionary)
        substituted_commands = params['grub']['ramdisk']['commands']
        self.assertIs(type(substituted_commands), list)
        self.assertIn('net_bootp', substituted_commands)
        self.assertNotIn("linux (tftp,{SERVER_IP})/{KERNEL} console=ttyS0,115200 earlycon=uart8250,mmio32,0x80300000 root=/dev/ram0 ip=dhcp", substituted_commands)
        self.assertIn("linux (tftp,%s)/%s console=ttyS0,115200 earlycon=uart8250,mmio32,0x80300000 root=/dev/ram0 ip=dhcp" % (ip_addr, kernel), substituted_commands)
        self.assertNotIn('initrd (tftp,{SERVER_IP})/{RAMDISK}', parsed)
        self.assertNotIn('devicetree (tftp,{SERVER_IP})/{DTB}', parsed)

    def test_download_action(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/grub-nfs.yaml')
        for action in job.pipeline.actions:
            action.validate()
            if not action.valid:
                raise RuntimeError(action.errors)
            self.assertTrue(action.valid)
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        deploy = None
        overlay = None
        extract = None
        for action in job.pipeline.actions:
            if action.name == 'tftp-deploy':
                deploy = action
        if deploy:
            for action in deploy.internal_pipeline.actions:
                if action.name == 'prepare-tftp-overlay':
                    overlay = action
        if overlay:
            for action in overlay.internal_pipeline.actions:
                if action.name == 'extract-nfsrootfs':
                    extract = action
        self.assertIn('lava_test_results_dir', overlay.data)
        self.assertIn('/lava-', overlay.data['lava_test_results_dir'])
        self.assertIsNotNone(extract)
        self.assertEqual(extract.timeout.duration, job.parameters['timeouts'][extract.name]['seconds'])

    def test_reset_actions(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/grub-ramdisk.yaml')
        grub_action = None
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
            if action.name == 'grub-main-action':
                grub_action = action
        names = [r_action.name for r_action in grub_action.internal_pipeline.actions]
        self.assertIn('connect-device', names)
        self.assertIn('reboot-device', names)
        self.assertIn('bootloader-interrupt', names)
        self.assertIn('expect-shell-connection', names)
        self.assertIn('bootloader-commands', names)
