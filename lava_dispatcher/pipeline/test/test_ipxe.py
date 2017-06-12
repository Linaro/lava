# Copyright (C) 2014 Linaro Limited
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
import sys
import yaml
import unittest
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.boot.ipxe import BootloaderAction
from lava_dispatcher.pipeline.actions.boot import (
    BootloaderCommandOverlay
)
from lava_dispatcher.pipeline.actions.deploy.tftp import TftpAction
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.action import Pipeline, JobError
from lava_dispatcher.pipeline.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.pipeline.test.utils import DummyLogger
from lava_dispatcher.pipeline.utils.network import dispatcher_ip
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.utils.strings import substitute


class X86Factory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/x86-01.yaml'))
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "",
                               output_dir=output_dir)
        job.logger = DummyLogger()
        return job


class TestBootloaderAction(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestBootloaderAction, self).setUp()
        self.factory = X86Factory()

    def test_simulated_action(self):
        job = self.factory.create_job('sample_jobs/ipxe-ramdisk.yaml')
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference('ipxe.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())
        self.assertEqual(job.device['device_type'], 'x86')

    def test_tftp_pipeline(self):
        job = self.factory.create_job('sample_jobs/ipxe-ramdisk.yaml')
        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ['tftp-deploy', 'bootloader-action', 'lava-test-retry', 'finalize']
        )
        tftp = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        self.assertTrue(tftp.get_namespace_data(action=tftp.name, label='tftp', key='ramdisk'))
        self.assertIsNotNone(tftp.internal_pipeline)
        self.assertEqual(
            [action.name for action in tftp.internal_pipeline.actions],
            ['download-retry', 'download-retry', 'download-retry', 'prepare-tftp-overlay', 'lxc-add-device-action', 'deploy-device-env']
        )
        self.assertIn('ramdisk', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertIn('kernel', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])

    def test_device_x86(self):
        job = self.factory.create_job('sample_jobs/ipxe-ramdisk.yaml')
        self.assertEqual(
            job.device['commands']['connect'],
            'telnet bumblebee 8003'
        )
        self.assertEqual(job.device['commands'].get('interrupt', ' '), ' ')
        methods = job.device['actions']['boot']['methods']
        self.assertIn('ipxe', methods)
        self.assertEqual(methods['ipxe']['parameters'].get('bootloader_prompt', None), 'iPXE>')

    def test_bootloader_action(self):
        job = self.factory.create_job('sample_jobs/ipxe-ramdisk.yaml')
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn('ipxe', job.device['actions']['boot']['methods'])
        params = job.device['actions']['boot']['methods']['ipxe']['parameters']
        boot_message = params.get('boot_message',
                                  job.device.get_constant('boot-message'))
        self.assertIsNotNone(boot_message)
        bootloader_action = [action for action in job.pipeline.actions if action.name == 'bootloader-action'][0]
        bootloader_retry = [action for action in bootloader_action.internal_pipeline.actions if action.name == 'bootloader-retry'][0]
        commands = [action for action in bootloader_retry.internal_pipeline.actions if action.name == 'bootloader-commands'][0]
        self.assertEqual(commands.character_delay, 250)
        for action in job.pipeline.actions:
            action.validate()
            if isinstance(action, BootloaderAction):
                self.assertIn('method', action.parameters)
                self.assertEqual('ipxe', action.parameters['method'])
                self.assertEqual(
                    'reboot: Restarting system',
                    action.parameters.get('parameters', {}).get('shutdown-message', job.device.get_constant('shutdown-message'))
                )
            if isinstance(action, TftpAction):
                self.assertIn('ramdisk', action.parameters)
                self.assertIn('kernel', action.parameters)
                self.assertIn('to', action.parameters)
                self.assertEqual('tftp', action.parameters['to'])
            self.assertTrue(action.valid)

    def test_overlay_action(self):  # pylint: disable=too-many-locals
        parameters = {
            'device_type': 'x86',
            'job_name': 'ipxe-pipeline',
            'job_timeout': '15m',
            'action_timeout': '5m',
            'priority': 'medium',
            'output_dir': mkdtemp(),
            'actions': {
                'boot': {
                    'method': 'ipxe',
                    'commands': 'ramdisk',
                    'prompts': ['linaro-test', 'root@debian:~#']
                },
                'deploy': {
                    'ramdisk': 'initrd.gz',
                    'kernel': 'zImage',
                }
            }
        }
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/x86-01.yaml'))
        job = Job(4212, parameters, None)
        job.device = device
        pipeline = Pipeline(job=job, parameters=parameters['actions']['boot'])
        job.pipeline = pipeline
        overlay = BootloaderCommandOverlay()
        pipeline.add_action(overlay)
        ip_addr = dispatcher_ip(None)
        kernel = parameters['actions']['deploy']['kernel']
        ramdisk = parameters['actions']['deploy']['ramdisk']

        substitution_dictionary = {
            '{SERVER_IP}': ip_addr,
            '{RAMDISK}': ramdisk,
            '{KERNEL}': kernel,
            '{LAVA_MAC}': "00:00:00:00:00:00"
        }
        params = device['actions']['boot']['methods']
        params['ipxe']['ramdisk']['commands'] = substitute(params['ipxe']['ramdisk']['commands'], substitution_dictionary)

        commands = params['ipxe']['ramdisk']['commands']
        self.assertIs(type(commands), list)
        self.assertIn("dhcp net0", commands)
        self.assertIn("set console console=ttyS0,115200n8 lava_mac=00:00:00:00:00:00", commands)
        self.assertIn("set extraargs init=/sbin/init ip=dhcp", commands)
        self.assertNotIn("kernel tftp://{SERVER_IP}/{KERNEL} ${extraargs} ${console}", commands)
        self.assertNotIn("initrd tftp://{SERVER_IP}/{RAMDISK}", commands)
        self.assertIn("boot", commands)

    def test_download_action(self):
        job = self.factory.create_job('sample_jobs/ipxe.yaml')
        for action in job.pipeline.actions:
            action.validate()
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
        test_dir = overlay.get_namespace_data(action='test', label='results', key='lava_test_results_dir')
        self.assertIsNotNone(test_dir)
        self.assertIn('/lava-', test_dir)
        self.assertIsNotNone(extract)
        self.assertEqual(extract.timeout.duration, 120)

    def test_reset_actions(self):
        job = self.factory.create_job('sample_jobs/ipxe.yaml')
        bootloader_action = None
        bootloader_retry = None
        reset_action = None
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
            if action.name == 'bootloader-action':
                bootloader_action = action
        names = [r_action.name for r_action in bootloader_action.internal_pipeline.actions]
        self.assertIn('connect-device', names)
        self.assertIn('bootloader-retry', names)
        for action in bootloader_action.internal_pipeline.actions:
            if action.name == 'bootloader-retry':
                bootloader_retry = action
        names = [r_action.name for r_action in bootloader_retry.internal_pipeline.actions]
        self.assertIn('reboot-device', names)
        self.assertIn('bootloader-interrupt', names)
        self.assertIn('expect-shell-connection', names)
        self.assertIn('bootloader-commands', names)
        for action in bootloader_retry.internal_pipeline.actions:
            if action.name == 'reboot-device':
                reset_action = action
        names = [r_action.name for r_action in reset_action.internal_pipeline.actions]
        self.assertIn('soft-reboot', names)
        self.assertIn('pdu-reboot', names)
        self.assertIn('power-on', names)

    @unittest.skipIf(infrastructure_error('telnet'), "telnet not installed")
    def test_prompt_from_job(self):  # pylint: disable=too-many-locals
        """
        Support setting the prompt after login via the job

        Loads a known YAML, adds a prompt to the dict and re-parses the job.
        Checks that the prompt is available in the expect_shell_connection action.
        """
        job = self.factory.create_job('sample_jobs/ipxe-ramdisk.yaml')
        job.validate()
        bootloader = [action for action in job.pipeline.actions if action.name == 'bootloader-action'][0]
        retry = [action for action in bootloader.internal_pipeline.actions
                 if action.name == 'bootloader-retry'][0]
        expect = [action for action in retry.internal_pipeline.actions
                  if action.name == 'expect-shell-connection'][0]
        check = expect.parameters
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/x86-01.yaml'))
        extra_yaml = os.path.join(os.path.dirname(__file__), 'sample_jobs/ipxe.yaml')
        with open(extra_yaml) as data:
            sample_job_string = data.read()
        parser = JobParser()
        sample_job_data = yaml.load(sample_job_string)
        boot = [item['boot'] for item in sample_job_data['actions'] if 'boot' in item][0]
        self.assertIsNotNone(boot)
        sample_job_string = yaml.dump(sample_job_data)
        job = parser.parse(sample_job_string, device, 4212, None, "",
                           output_dir='/tmp')
        job.logger = DummyLogger()
        job.validate()
        bootloader = [action for action in job.pipeline.actions if action.name == 'bootloader-action'][0]
        retry = [action for action in bootloader.internal_pipeline.actions
                 if action.name == 'bootloader-retry'][0]
        expect = [action for action in retry.internal_pipeline.actions
                  if action.name == 'expect-shell-connection'][0]
        if sys.version < '3':
            # skipping in 3 due to "RecursionError: maximum recursion depth exceeded in comparison"
            self.assertNotEqual(check, expect.parameters)

    def test_xz_nfs(self):
        job = self.factory.create_job('sample_jobs/ipxe-nfs.yaml')
        # this job won't validate as the .xz nfsrootfs URL is a fiction
        self.assertRaises(JobError, job.validate)
        tftp_deploy = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        prepare = [action for action in tftp_deploy.internal_pipeline.actions if action.name == 'prepare-tftp-overlay'][0]
        nfs = [action for action in prepare.internal_pipeline.actions if action.name == 'extract-nfsrootfs'][0]
        self.assertIn('compression', nfs.parameters['nfsrootfs'])
        self.assertEqual(nfs.parameters['nfsrootfs']['compression'], 'xz')

    def test_ipxe_with_monitor(self):
        job = self.factory.create_job('sample_jobs/ipxe-monitor.yaml')
        job.validate()
        description_ref = self.pipeline_reference('ipxe-monitor.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
