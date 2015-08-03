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
import yaml
import tarfile
import unittest
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.boot.u_boot import (
    UBootAction,
    UBootCommandOverlay,
    UBootSecondaryMedia
)
from lava_dispatcher.pipeline.actions.deploy.tftp import TftpAction
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.action import Pipeline, InfrastructureError, JobError
from lava_dispatcher.pipeline.test.test_basic import pipeline_reference
from lava_dispatcher.pipeline.utils.network import dispatcher_ip
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp, tftpd_dir
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.constants import (
    SHUTDOWN_MESSAGE,
    BOOT_MESSAGE,
)


class Factory(object):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_bbb_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(kvm_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, output_dir=output_dir)
        return job


class TestUbootAction(unittest.TestCase):  # pylint: disable=too-many-public-methods

    @unittest.skipIf(infrastructure_error('mkimage'), "u-boot-tools not installed")
    def test_simulated_action(self):
        factory = Factory()
        job = factory.create_bbb_job('sample_jobs/uboot-ramdisk.yaml')
        self.assertIsNotNone(job)

        # uboot and uboot-ramdisk have the same pipeline structure
        description_ref = pipeline_reference('uboot.yaml')
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())
        self.assertEqual(job.device['device_type'], 'beaglebone-black')

    def test_tftp_pipeline(self):
        factory = Factory()
        job = factory.create_bbb_job('sample_jobs/uboot-ramdisk.yaml')
        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ['tftp-deploy', 'uboot-action', 'lava-test-retry', 'finalize']
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
        # allow root to compare the path (with the mkdtemp added)
        paths = {action.path for action in tftp.internal_pipeline.actions if hasattr(action, 'path')}
        self.assertIn(
            tftpd_dir(),
            [item for item in paths][0]
        )

    def test_device_bbb(self):
        factory = Factory()
        job = factory.create_bbb_job('sample_jobs/uboot.yaml')
        self.assertEqual(
            job.device['commands']['connect'],
            'telnet localhost 6000'
        )
        self.assertEqual(job.device['commands'].get('interrupt', ' '), ' ')
        methods = job.device['actions']['boot']['methods']
        self.assertIn('u-boot', methods)
        self.assertEqual(methods['u-boot']['parameters'].get('bootloader_prompt', None), 'U-Boot')

    @unittest.skipIf(infrastructure_error('mkimage'), "u-boot-tools not installed")
    def test_uboot_action(self):
        factory = Factory()
        job = factory.create_bbb_job('sample_jobs/uboot-ramdisk.yaml')
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn('u-boot', job.device['actions']['boot']['methods'])
        params = job.device['actions']['boot']['methods']['u-boot']['parameters']
        boot_message = params.get('boot_message', BOOT_MESSAGE)
        self.assertIsNotNone(boot_message)
        for action in job.pipeline.actions:
            action.validate()
            if isinstance(action, UBootAction):
                self.assertIn('method', action.parameters)
                self.assertEqual('u-boot', action.parameters['method'])
                self.assertEqual(
                    'reboot: Restarting system',
                    action.parameters.get('parameters', {}).get('shutdown-message', SHUTDOWN_MESSAGE)
                )
            if isinstance(action, TftpAction):
                self.assertIn('ramdisk', action.parameters)
                self.assertIn('kernel', action.parameters)
                self.assertIn('to', action.parameters)
                self.assertEqual('tftp', action.parameters['to'])
            self.assertTrue(action.valid)

    def test_overlay_action(self):  # pylint: disable=too-many-locals
        parameters = {
            'device_type': 'beaglebone-black',
            'job_name': 'uboot-pipeline',
            'job_timeout': '15m',
            'action_timeout': '5m',
            'priority': 'medium',
            'output_dir': mkdtemp(),
            'actions': {
                'boot': {
                    'method': 'u-boot',
                    'commands': 'ramdisk',
                    'type': 'bootz'
                },
                'deploy': {
                    'ramdisk': 'initrd.gz',
                    'kernel': 'zImage',
                    'dtb': 'broken.dtb'
                }
            }
        }
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        job = Job(4212, None, parameters)
        job.device = device
        pipeline = Pipeline(job=job, parameters=parameters['actions']['boot'])
        job.set_pipeline(pipeline)
        overlay = UBootCommandOverlay()
        pipeline.add_action(overlay)
        try:
            ip_addr = dispatcher_ip()
        except InfrastructureError as exc:
            raise RuntimeError("Unable to get dispatcher IP address: %s" % exc)
        parsed = []
        kernel_addr = job.device['parameters'][overlay.parameters['type']]['ramdisk']
        ramdisk_addr = job.device['parameters'][overlay.parameters['type']]['ramdisk']
        dtb_addr = job.device['parameters'][overlay.parameters['type']]['dtb']
        kernel = parameters['actions']['deploy']['kernel']
        ramdisk = parameters['actions']['deploy']['ramdisk']
        dtb = parameters['actions']['deploy']['dtb']

        substitution_dictionary = {
            '{SERVER_IP}': ip_addr,
            # the addresses need to be hexadecimal
            '{KERNEL_ADDR}': kernel_addr,
            '{DTB_ADDR}': dtb_addr,
            '{RAMDISK_ADDR}': ramdisk_addr,
            '{BOOTX}': "%s %s %s %s" % (
                overlay.parameters['type'], kernel_addr, ramdisk_addr, dtb_addr),
            '{RAMDISK}': ramdisk,
            '{KERNEL}': kernel,
            '{DTB}': dtb
        }
        params = device['actions']['boot']['methods']
        params['u-boot']['ramdisk']['commands'] = substitute(params['u-boot']['ramdisk']['commands'], substitution_dictionary)

        commands = params['u-boot']['ramdisk']['commands']
        self.assertIs(type(commands), list)
        self.assertIn("setenv loadkernel 'tftp ${kernel_addr_r} zImage'", commands)
        self.assertIn("setenv loadinitrd 'tftp ${initrd_addr_r} initrd.gz; setenv initrd_size ${filesize}'", commands)
        self.assertIn("setenv loadfdt 'tftp ${fdt_addr_r} broken.dtb'", commands)
        self.assertNotIn("setenv kernel_addr_r '{KERNEL_ADDR}'", commands)
        self.assertNotIn("setenv initrd_addr_r '{RAMDISK_ADDR}'", commands)
        self.assertNotIn("setenv fdt_addr_r '{DTB_ADDR}'", commands)

        for line in params['u-boot']['ramdisk']['commands']:
            line = line.replace('{SERVER_IP}', ip_addr)
            # the addresses need to be hexadecimal
            line = line.replace('{KERNEL_ADDR}', kernel_addr)
            line = line.replace('{DTB_ADDR}', dtb_addr)
            line = line.replace('{RAMDISK_ADDR}', ramdisk_addr)
            line = line.replace('{BOOTX}', "%s %s %s %s" % (
                overlay.parameters['type'], kernel_addr, ramdisk_addr, dtb_addr))
            line = line.replace('{RAMDISK}', ramdisk)
            line = line.replace('{KERNEL}', kernel)
            line = line.replace('{DTB}', dtb)
            parsed.append(line)
        self.assertIn("setenv loadkernel 'tftp ${kernel_addr_r} zImage'", parsed)
        self.assertIn("setenv loadinitrd 'tftp ${initrd_addr_r} initrd.gz; setenv initrd_size ${filesize}'", parsed)
        self.assertIn("setenv loadfdt 'tftp ${fdt_addr_r} broken.dtb'", parsed)
        self.assertNotIn("setenv kernel_addr_r '{KERNEL_ADDR}'", parsed)
        self.assertNotIn("setenv initrd_addr_r '{RAMDISK_ADDR}'", parsed)
        self.assertNotIn("setenv fdt_addr_r '{DTB_ADDR}'", parsed)

    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_download_action(self):
        factory = Factory()
        job = factory.create_bbb_job('sample_jobs/uboot.yaml')
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
        self.assertIn('lava_test_results_dir', overlay.data)
        self.assertIn('/lava-', overlay.data['lava_test_results_dir'])
        self.assertIsNotNone(extract)
        self.assertEqual(extract.timeout.duration, job.parameters['timeouts'][extract.name]['seconds'])

    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_reset_actions(self):
        factory = Factory()
        job = factory.create_bbb_job('sample_jobs/uboot.yaml')
        uboot_action = None
        uboot_retry = None
        reset_action = None
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
            if action.name == 'uboot-action':
                uboot_action = action
        names = [r_action.name for r_action in uboot_action.internal_pipeline.actions]
        self.assertIn('connect-device', names)
        self.assertIn('uboot-retry', names)
        for action in uboot_action.internal_pipeline.actions:
            if action.name == 'uboot-retry':
                uboot_retry = action
        names = [r_action.name for r_action in uboot_retry.internal_pipeline.actions]
        self.assertIn('reboot-device', names)
        self.assertIn('u-boot-interrupt', names)
        self.assertIn('expect-shell-connection', names)
        self.assertIn('u-boot-commands', names)
        for action in uboot_retry.internal_pipeline.actions:
            if action.name == 'reboot-device':
                reset_action = action
        names = [r_action.name for r_action in reset_action.internal_pipeline.actions]
        self.assertIn('soft-reboot', names)
        self.assertIn('pdu_reboot', names)
        self.assertIn('power_on', names)

    def test_secondary_media(self):
        """
        Test UBootSecondaryMedia validation
        """
        job_parser = JobParser()
        cubie = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/cubie1.yaml'))
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/cubietruck-removable.yaml')
        sample_job_data = open(sample_job_file)
        job = job_parser.parse(sample_job_data, cubie, 4212, None, output_dir='/tmp/')
        job.validate()
        u_boot_media = job.pipeline.actions[1].internal_pipeline.actions[0]
        self.assertIsInstance(u_boot_media, UBootSecondaryMedia)
        self.assertEqual([], u_boot_media.errors)
        self.assertEqual(u_boot_media.parameters['kernel'], '/boot/vmlinuz-3.16.0-4-armmp-lpae')
        self.assertEqual(u_boot_media.parameters['kernel'], u_boot_media.get_common_data('file', 'kernel'))
        self.assertEqual(u_boot_media.parameters['ramdisk'], u_boot_media.get_common_data('file', 'ramdisk'))
        self.assertEqual(u_boot_media.parameters['dtb'], u_boot_media.get_common_data('file', 'dtb'))
        self.assertEqual(u_boot_media.parameters['root_uuid'], u_boot_media.get_common_data('uuid', 'root'))
        part_reference = '%s:%s' % (
            job.device['parameters']['media']['usb'][u_boot_media.get_common_data('u-boot', 'device')]['device_id'],
            u_boot_media.parameters['boot_part']
        )
        self.assertEqual(part_reference, u_boot_media.get_common_data('uuid', 'boot_part'))
        self.assertEqual(part_reference, "0:1")

    @unittest.skipIf(infrastructure_error('telnet'), "telnet not installed")
    def test_prompt_from_job(self):
        """
        Support setting the prompt after login via the job

        Loads a known YAML, adds a prompt to the dict and re-parses the job.
        Checks that the prompt is available in the expect_shell_connection action.
        """
        factory = Factory()
        job = factory.create_bbb_job('sample_jobs/uboot.yaml')
        job.validate()
        uboot = [action for action in job.pipeline.actions if action.name == 'uboot-action'][0]
        retry = [action for action in uboot.internal_pipeline.actions
                 if action.name == 'uboot-retry'][0]
        expect = [action for action in retry.internal_pipeline.actions
                  if action.name == 'expect-shell-connection'][0]
        check = expect.parameters
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        extra_yaml = os.path.join(os.path.dirname(__file__), 'sample_jobs/uboot.yaml')
        with open(extra_yaml) as data:
            sample_job_string = data.read()
        parser = JobParser()
        sample_job_data = yaml.load(sample_job_string)
        boot = [item['boot'] for item in sample_job_data['actions'] if 'boot' in item][0]
        boot.update({'parameters': {'boot_prompt': 'root@bbb'}})
        sample_job_string = yaml.dump(sample_job_data)
        job = parser.parse(sample_job_string, device, 4212, None, output_dir='/tmp')
        job.validate()
        uboot = [action for action in job.pipeline.actions if action.name == 'uboot-action'][0]
        retry = [action for action in uboot.internal_pipeline.actions
                 if action.name == 'uboot-retry'][0]
        expect = [action for action in retry.internal_pipeline.actions
                  if action.name == 'expect-shell-connection'][0]
        self.assertNotEqual(check, expect.parameters)
        self.assertIn('root@bbb', expect.prompts)

    def test_xz_nfs(self):
        factory = Factory()
        job = factory.create_bbb_job('sample_jobs/uboot-nfs.yaml')
        # this job won't validate as the .xz nfsrootfs URL is a fiction
        self.assertRaises(JobError, job.validate)
        tftp_deploy = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        prepare = [action for action in tftp_deploy.internal_pipeline.actions if action.name == 'prepare-tftp-overlay'][0]
        nfs = [action for action in prepare.internal_pipeline.actions if action.name == 'extract-nfsrootfs'][0]
        self.assertIn('rootfs_compression', nfs.parameters)
        self.assertEqual(nfs.parameters['rootfs_compression'], 'xz')
        valid = tarfile.TarFile
        if 'xz' not in valid.__dict__['OPEN_METH'].keys():
            self.assertTrue(nfs.use_lzma)
            self.assertFalse(nfs.use_tarfile)
        else:
            # python3 has xz support in tarfile.
            self.assertFalse(nfs.use_lzma)
            self.assertTrue(nfs.use_tarfile)
