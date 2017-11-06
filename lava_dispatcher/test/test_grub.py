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
import unittest
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.test.utils import DummyLogger
from lava_dispatcher.actions.boot.grub import GrubMainAction
from lava_dispatcher.actions.boot import BootloaderCommandOverlay
from lava_dispatcher.actions.deploy.tftp import TftpAction
from lava_dispatcher.job import Job
from lava_dispatcher.action import JobError, Pipeline
from lava_dispatcher.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.shell import infrastructure_error
from lava_dispatcher.utils.filesystem import mkdtemp, tftpd_dir
from lava_dispatcher.utils.strings import substitute
from lava_dispatcher.utils.shell import infrastructure_error_multi_paths


class GrubFactory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/d02-01.yaml'))
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "",
                               output_dir=output_dir)
        job.logger = DummyLogger()
        return job

    def create_mustang_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/mustang-grub-efi.yaml'))
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "",
                               output_dir=output_dir)
        job.logger = DummyLogger()
        return job

    def create_hikey_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/hi6220-hikey-01.yaml'))
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "",
                               output_dir=output_dir)
        job.logger = DummyLogger()
        return job

    def create_hikey960_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/hikey960-01.yaml'))
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "",
                               output_dir=output_dir)
        job.logger = DummyLogger()
        return job


class TestGrubAction(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestGrubAction, self).setUp()
        self.factory = GrubFactory()

    @unittest.skipIf(infrastructure_error('mkimage'), "u-boot-tools not installed")
    def test_simulated_action(self):
        job = self.factory.create_job('sample_jobs/grub-ramdisk.yaml')
        self.assertIsNotNone(job)

        # uboot and uboot-ramdisk have the same pipeline structure
        description_ref = self.pipeline_reference('grub.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())
        self.assertEqual(job.device['device_type'], 'd02')

    def test_tftp_pipeline(self):
        job = self.factory.create_job('sample_jobs/grub-ramdisk.yaml')
        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ['tftp-deploy', 'grub-main-action', 'lava-test-retry', 'finalize']
        )
        tftp = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        self.assertTrue(tftp.get_namespace_data(action=tftp.name, label='tftp', key='ramdisk'))
        self.assertIsNotNone(tftp.internal_pipeline)
        self.assertEqual(
            [action.name for action in tftp.internal_pipeline.actions],
            ['download-retry', 'download-retry', 'download-retry', 'prepare-tftp-overlay', 'lxc-create-udev-rule-action', 'deploy-device-env']
        )
        self.assertIn('ramdisk', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertIn('kernel', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertIn('dtb', [action.key for action in tftp.internal_pipeline.actions if hasattr(action, 'key')])
        self.assertNotIn('=', tftpd_dir())

    def test_device_d02(self):
        job = self.factory.create_job('sample_jobs/grub-ramdisk.yaml')
        self.assertNotIn('connect', job.device['commands'])
        self.assertEqual(
            job.device['commands']['connections']['uart0']['connect'],
            'telnet ratchet 7003'
        )
        self.assertEqual(job.device['commands'].get('interrupt', ' '), ' ')
        methods = job.device['actions']['boot']['methods']
        self.assertIn('grub', methods)
        self.assertEqual(methods['grub']['parameters'].get('bootloader_prompt', None), 'grub>')

    @unittest.skipIf(infrastructure_error('mkimage'), "u-boot-tools not installed")
    def test_grub_action(self):
        job = self.factory.create_job('sample_jobs/grub-ramdisk.yaml')
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn('grub', job.device['actions']['boot']['methods'])
        params = job.device['actions']['boot']['methods']['grub']['parameters']
        boot_message = params.get('boot_message',
                                  job.device.get_constant('boot-message'))
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
        job = Job(4212, parameters, None)
        job.device = device
        pipeline = Pipeline(job=job, parameters=parameters['actions']['boot'])
        job.pipeline = pipeline
        overlay = BootloaderCommandOverlay()
        pipeline.add_action(overlay)
        ip_addr = dispatcher_ip(None)
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
        job = self.factory.create_job('sample_jobs/grub-nfs.yaml')
        for action in job.pipeline.actions:
            action.validate()
            if not action.valid:
                raise JobError(action.errors)
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
        self.assertEqual(extract.timeout.duration, 600)

    def test_reset_actions(self):
        job = self.factory.create_job('sample_jobs/grub-ramdisk.yaml')
        grub_action = None
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
            if action.name == 'grub-main-action':
                grub_action = action
        names = [r_action.name for r_action in grub_action.internal_pipeline.actions]
        self.assertIn('connect-device', names)
        self.assertIn('reset-device', names)
        self.assertIn('bootloader-interrupt', names)
        self.assertIn('expect-shell-connection', names)
        self.assertIn('bootloader-commands', names)

    def test_grub_with_monitor(self):
        job = self.factory.create_job('sample_jobs/grub-ramdisk-monitor.yaml')
        job.validate()
        description_ref = self.pipeline_reference('grub-ramdisk-monitor.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

    def test_grub_via_efi(self):
        job = self.factory.create_mustang_job('sample_jobs/mustang-grub-efi-nfs.yaml')
        self.assertIsNotNone(job)
        job.validate()
        description_ref = self.pipeline_reference('mustang-grub-efi-nfs.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
        grub = [action for action in job.pipeline.actions if action.name == 'grub-main-action'][0]
        menu = [action for action in grub.internal_pipeline.actions if action.name == 'uefi-menu-interrupt'][0]
        self.assertIn('item_class', menu.params)
        grub_efi = [action for action in grub.internal_pipeline.actions if action.name == 'grub-efi-menu-selector'][0]
        self.assertEqual('pxe-grub', grub_efi.commands)

    def test_hikey_grub_efi(self):
        job = self.factory.create_hikey_job('sample_jobs/hikey-grub-lxc.yaml')
        self.assertIsNotNone(job)
        job.validate()
        description_ref = self.pipeline_reference('hikey-grub-efi.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
        grub = [action for action in job.pipeline.actions if action.name == 'grub-main-action'][0]
        menu = [action for action in grub.internal_pipeline.actions if action.name == 'uefi-menu-interrupt'][0]
        self.assertIn('item_class', menu.params)
        grub_efi = [action for action in grub.internal_pipeline.actions if action.name == 'grub-efi-menu-selector'][0]
        self.assertEqual('fastboot', grub_efi.commands)

    @unittest.skipIf(infrastructure_error_multi_paths(
        ['lxc-info', 'img2simg', 'simg2img']),
        "lxc or img2simg or simg2img not installed")
    def test_hikey_uart(self):
        job = self.factory.create_hikey_job('sample_jobs/hikey-console.yaml')
        self.assertIsNotNone(job)
        job.validate()
        description_ref = self.pipeline_reference('hikey-console.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
        console = [action for action in job.pipeline.actions if action.name == 'secondary-shell-action'][0]
        command = [action for action in console.internal_pipeline.actions if action.name == 'connect-shell'][0]
        self.assertEqual('isolation', command.parameters['namespace'])
        self.assertEqual('uart0', command.hardware)
        self.assertIn('connections', job.device['commands'])
        uart = job.device['commands']['connections'][command.hardware]['connect']
        self.assertIn(command.command, uart)
        self.assertEqual('telnet localhost 7020', uart)
        tshells = [action for action in job.pipeline.actions if action.name == 'lava-test-retry']
        for shell in tshells:
            cn = shell.parameters.get('connection-namespace', None)
            if cn:
                self.assertEqual(shell.parameters['namespace'], 'hikey-oe')
                self.assertNotEqual(shell.parameters['namespace'], 'isolation')
                self.assertNotEqual(shell.parameters['namespace'], 'tlxc')
                self.assertEqual(shell.parameters['connection-namespace'], 'isolation')
                retry = [action for action in shell.internal_pipeline.actions][0]
                print(retry.parameters.get('connection-namespace', None))
            else:
                self.assertNotEqual(shell.parameters['namespace'], 'hikey-oe')
                self.assertNotEqual(shell.parameters['namespace'], 'isolation')
                self.assertEqual(shell.parameters['namespace'], 'tlxc')
                self.assertNotIn('connection-namespace', shell.parameters.keys())

    def test_hikey960_grub(self):
        job = self.factory.create_hikey960_job('sample_jobs/hikey960-oe.yaml')
        self.assertIsNotNone(job)
        job.validate()
        description_ref = self.pipeline_reference('hi960-grub-efi.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))
        deploy = [action for action in job.pipeline.actions if action.name == 'fastboot-deploy'][0]
        flash_ord = [action for action in deploy.internal_pipeline.actions if action.name == 'fastboot-flash-order-action'][0]
        flash = [action for action in flash_ord.internal_pipeline.actions if action.name == 'fastboot-flash-action'][0]
        self.assertIsNotNone(flash.interrupt_prompt)
        self.assertEqual('Android Fastboot mode', flash.interrupt_prompt)
        self.assertIsNotNone(flash.interrupt_string)
        self.assertEqual(' ', flash.interrupt_string)
        grub_seq = [action for action in job.pipeline.actions if action.name == 'grub-sequence-action'][0]
        self.assertIsNotNone(grub_seq)
        wait = [action for action in grub_seq.internal_pipeline.actions if action.name == 'wait-fastboot-interrupt'][0]
        self.assertIsNotNone(wait)
        login = [action for action in grub_seq.internal_pipeline.actions if action.name == 'auto-login-action'][0]
        self.assertIsNotNone(login)
