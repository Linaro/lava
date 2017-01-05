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
from lava_dispatcher.pipeline.action import JobError
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.removable import MassStorage
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.shell import infrastructure_error


class Factory(object):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_job(self, sample_job, device_file, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), device_file))
        yaml = os.path.join(os.path.dirname(__file__), sample_job)
        with open(yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, None, None,
                               output_dir=output_dir)
        return job


class TestRemovable(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_device_parameters(self):
        """
        Test that the correct parameters have been set for the device
        """
        cubie = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/cubie1.yaml'))
        self.assertIsNotNone(cubie['parameters']['media'].get('usb', None))
        self.assertIsNotNone(cubie.get('commands', None))
        self.assertIsNotNone(cubie.get('actions', None))
        self.assertIsNotNone(cubie['actions'].get('deploy', None))
        self.assertIsNotNone(cubie['actions']['deploy'].get('methods', None))
        self.assertIn('usb', cubie['actions']['deploy']['methods'])
        self.assertIsNotNone(cubie['actions'].get('boot', None))
        self.assertIsNotNone(cubie['actions']['boot'].get('methods', None))
        self.assertIn('u-boot', cubie['actions']['boot']['methods'])
        u_boot_params = cubie['actions']['boot']['methods']['u-boot']
        self.assertIn('usb', u_boot_params)
        self.assertIn('commands', u_boot_params['usb'])
        self.assertIn('parameters', u_boot_params)
        self.assertIn('boot_message', u_boot_params['parameters'])
        self.assertIn('bootloader_prompt', u_boot_params['parameters'])

    def test_job_parameters(self):
        """
        Test that the job parameters match expected structure
        """
        self.maxDiff = None  # pylint: disable=invalid-name
        job_parser = JobParser()
        cubie = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/cubie1.yaml'))
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/cubietruck-removable.yaml')
        with open(sample_job_file) as sample_job_data:
            job = job_parser.parse(sample_job_data, cubie, 4212, None, None, None, output_dir='/tmp/')
        try:
            job.validate()
        except JobError:
            self.fail(job.pipeline.errors)
        sample_job_data.close()
        description_ref = pipeline_reference('cubietruck-removable.yaml')
        self.assertEqual(description_ref, job.pipeline.describe(False))

        mass_storage = None  # deploy
        for action in job.pipeline.actions:
            if isinstance(action, DeployAction):
                if isinstance(action, MassStorage):
                    self.assertTrue(action.valid)
                    agent = action.parameters['download']['tool']
                    self.assertTrue(agent.startswith('/'))  # needs to be a full path but on the device, so avoid os.path
                    self.assertIn(action.parameters['device'], job.device['parameters']['media']['usb'])
                    mass_storage = action
        self.assertIsNotNone(mass_storage)
        self.assertIn('device', mass_storage.parameters)
        self.assertIn(mass_storage.parameters['device'], cubie['parameters']['media']['usb'])
        self.assertIsNotNone(mass_storage.get_namespace_data(action='storage-deploy', label='u-boot', key='device'))
        u_boot_params = cubie['actions']['boot']['methods']['u-boot']
        self.assertEqual(mass_storage.get_namespace_data(action='uboot-retry', label='bootloader_prompt', key='prompt'), u_boot_params['parameters']['bootloader_prompt'])

    def test_deployment(self):
        job_parser = JobParser()
        cubie = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/cubie1.yaml'))
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/cubietruck-removable.yaml')
        with open(sample_job_file) as sample_job_data:
            job = job_parser.parse(sample_job_data, cubie, 4212, None, None, None, output_dir='/tmp/')
        job.validate()
        self.assertIn('usb', cubie['parameters']['media'].keys())
        deploy_params = [methods for methods in job.parameters['actions'] if 'deploy' in methods.keys()][1]['deploy']
        self.assertIn('device', deploy_params)
        self.assertIn(deploy_params['device'], cubie['parameters']['media']['usb'])
        self.assertIn('uuid', cubie['parameters']['media']['usb'][deploy_params['device']])
        self.assertIn('device_id', cubie['parameters']['media']['usb'][deploy_params['device']])
        self.assertNotIn('boot_part', cubie['parameters']['media']['usb'][deploy_params['device']])
        deploy_action = [action for action in job.pipeline.actions if action.name == 'storage-deploy'][0]
        tftp_deploy_action = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        self.assertIsNotNone(deploy_action)
        test_dir = deploy_action.get_namespace_data(action='test', label='results', key='lava_test_results_dir', parameters=tftp_deploy_action.parameters)
        self.assertIsNotNone(test_dir)
        self.assertIn('/lava-', test_dir)
        self.assertIsInstance(deploy_action, MassStorage)
        self.assertIn('image', deploy_action.parameters.keys())
        dd_action = [action for action in deploy_action.internal_pipeline.actions if action.name == 'dd-image'][0]
        self.assertEqual(
            dd_action.boot_params[dd_action.parameters['device']]['uuid'],
            'usb-SanDisk_Ultra_20060775320F43006019-0:0')
        self.assertIsNotNone(dd_action.get_namespace_data(action=dd_action.name, label='u-boot', key='boot_part'))
        self.assertIsNotNone(dd_action.get_namespace_data(action='uboot-from-media', label='uuid', key='boot_part'))
        self.assertEqual('0', '%s' % dd_action.get_namespace_data(action=dd_action.name, label='u-boot', key='boot_part'))
        self.assertIsInstance(dd_action.get_namespace_data(action='uboot-from-media', label='uuid', key='boot_part'), str)
        self.assertEqual('0:1', dd_action.get_namespace_data(action='uboot-from-media', label='uuid', key='boot_part'))

    def test_juno_deployment(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/juno-uboot-removable.yaml', '../devices/juno-uboot.yaml')
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn('usb', job.device['parameters']['media'].keys())
        deploy_params = [methods for methods in job.parameters['actions'] if 'deploy' in methods.keys()][1]['deploy']
        self.assertIn('device', deploy_params)
        self.assertIn(deploy_params['device'], job.device['parameters']['media']['usb'])
        self.assertIn('uuid', job.device['parameters']['media']['usb'][deploy_params['device']])
        self.assertIn('device_id', job.device['parameters']['media']['usb'][deploy_params['device']])
        self.assertNotIn('boot_part', job.device['parameters']['media']['usb'][deploy_params['device']])
        tftp_deploys = [action for action in job.pipeline.actions if action.name == 'tftp-deploy']
        self.assertEqual(len(tftp_deploys), 2)
        first_deploy = tftp_deploys[0]
        second_deploy = tftp_deploys[1]
        self.assertIsNotNone(first_deploy)
        self.assertIsNotNone(second_deploy)
        self.assertEqual('openembedded', first_deploy.parameters['namespace'])
        self.assertEqual('android', second_deploy.parameters['namespace'])
        self.assertNotIn('deployment_data', first_deploy.parameters)
        self.assertNotIn('deployment_data', second_deploy.parameters)
        storage_deploy_action = [action for action in job.pipeline.actions if action.name == 'storage-deploy'][0]
        download_action = [
            action for action in storage_deploy_action.internal_pipeline.actions if action.name == 'download_retry'][0]
        self.assertIsNotNone(download_action)
        self.assertEqual('android', storage_deploy_action.parameters['namespace'])

    @unittest.skipIf(infrastructure_error('mkimage'), "u-boot-tools not installed")
    def test_primary_media(self):
        """
        Test that definitions of secondary media do not block submissions using primary media
        """
        job_parser = JobParser()
        bbb = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/uboot-ramdisk.yaml')
        with open(sample_job_file) as sample_job_data:
            job = job_parser.parse(sample_job_data, bbb, 4212, None, None, None, output_dir='/tmp/')
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn('usb', bbb['parameters']['media'].keys())

    def test_substitutions(self):
        """
        Test substitution of secondary media values into u-boot commands

        Unlike most u-boot calls, removable knows in advance all the values it needs to substitute
        into the boot commands for the secondary deployment as these are fixed by the device config
        and the image details from the job submission.
        """
        job_parser = JobParser()
        cubie = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/cubie1.yaml'))
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/cubietruck-removable.yaml')
        with open(sample_job_file) as sample_job_data:
            job = job_parser.parse(sample_job_data, cubie, 4212, None, None, None, output_dir='/tmp/')
        job.validate()
        boot_params = [
            methods for methods in job.parameters['actions'] if 'boot' in methods.keys()][1]['boot']
        self.assertIn('ramdisk', boot_params)
        self.assertIn('kernel', boot_params)
        self.assertIn('dtb', boot_params)
        self.assertIn('root_uuid', boot_params)
        self.assertIn('boot_part', boot_params)
        self.assertIn('type', boot_params)
        self.assertGreater(len(job.pipeline.actions), 1)
        self.assertIsNotNone(job.pipeline.actions[1].internal_pipeline)
        u_boot_action = [action for action in job.pipeline.actions if action.name == 'uboot-action'][1].internal_pipeline.actions[2]
        self.assertIsNotNone(u_boot_action.get_namespace_data(action='storage-deploy', label='u-boot', key='device'))
        self.assertEqual(u_boot_action.name, "bootloader-overlay")

        methods = cubie['actions']['boot']['methods']
        self.assertIn('u-boot', methods)
        self.assertIn('usb', methods['u-boot'])
        self.assertIn('commands', methods['u-boot']['usb'])
        commands_list = methods['u-boot']['usb']['commands']
        device_id = u_boot_action.get_namespace_data(action='storage-deploy', label='u-boot', key='device')
        self.assertIsNotNone(device_id)
        substitutions = {
            '{BOOTX}': "%s %s %s %s" % (
                u_boot_action.parameters['type'],
                cubie['parameters'][u_boot_action.parameters['type']]['kernel'],
                cubie['parameters'][u_boot_action.parameters['type']]['ramdisk'],
                cubie['parameters'][u_boot_action.parameters['type']]['dtb'],),
            '{RAMDISK}': boot_params['ramdisk'],
            '{KERNEL}': boot_params['kernel'],
            '{DTB}': boot_params['dtb'],
            '{ROOT}': boot_params['root_uuid'],
            '{ROOT_PART}': "%s:%s" % (
                cubie['parameters']['media']['usb'][device_id]['device_id'],
                u_boot_action.parameters['boot_part']
            )
        }
        self.assertEqual('bootz 0x42000000 0x43300000 0x43000000', substitutions['{BOOTX}'])
        self.assertEqual('/boot/initrd.img-3.16.0-4-armmp-lpae.u-boot', substitutions['{RAMDISK}'])
        commands = substitute(commands_list, substitutions)
        self.assertEqual(
            commands,
            [
                'usb start',
                'usb info',
                'setenv autoload no',
                "setenv initrd_high '0xffffffff'",
                "setenv fdt_high '0xffffffff'",
                'setenv initrd_addr_r ${ramdisk_addr_r}',
                "setenv loadkernel 'load usb 0:1 ${kernel_addr_r} /boot/vmlinuz-3.16.0-4-armmp-lpae'",
                "setenv loadinitrd 'load usb 0:1 ${initrd_addr_r} /boot/initrd.img-3.16.0-4-armmp-lpae.u-boot; setenv initrd_size ${filesize}'",
                "setenv loadfdt 'load usb 0:1 ${fdt_addr_r} /boot/dtb-3.16.0-4-armmp-lpae'",
                "setenv bootargs 'console=ttyS0,115200n8 root=UUID=159d17cc-697c-4125-95a0-a3775e1deabe ip=dhcp'",
                "setenv bootcmd 'run loadkernel; run loadinitrd; run loadfdt; bootz 0x42000000 0x43300000 0x43000000'", 'boot'
            ]
        )
        # reference commands:
        #        setenv loadkernel 'load usb 0:1 ${kernel_addr_r} /boot/vmlinuz-3.16.0-4-armmp-lpae'
        #        setenv loadinitrd 'load usb 0:1 ${initrd_addr_r} /boot/initrd.img-3.16.0-4-armmp-lpae.u-boot; setenv initrd_size ${filesize}'
        #        setenv loadfdt 'load usb 0:1 ${fdt_addr_r} /boot/dtb-3.16.0-4-armmp-lpae'
        #        setenv bootargs 'console=ttyS0,115200 rw root=UUID=159d17cc-697c-4125-95a0-a3775e1deabe ip=dhcp'
