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
from lava_dispatcher.pipeline.action import JobError
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.removable import MassStorage
from lava_dispatcher.pipeline.utils.strings import substitute


class TestRemovable(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_device_parameters(self):
        """
        Test that the correct parameters have been set for the device
        """
        cubie = NewDevice('cubie1')
        self.assertIsNotNone(cubie.parameters['media'].get('usb', None))
        self.assertIsNotNone(cubie.parameters.get('commands', None))
        self.assertIsNotNone(cubie.parameters.get('actions', None))
        self.assertIsNotNone(cubie.parameters['actions'].get('deploy', None))
        self.assertIsNotNone(cubie.parameters['actions']['deploy'].get('methods', None))
        self.assertIn('usb', cubie.parameters['actions']['deploy']['methods'])
        self.assertIsNotNone(cubie.parameters['actions'].get('boot', None))
        self.assertIsNotNone(cubie.parameters['actions']['boot'].get('methods', None))
        self.assertIn('u-boot', [methods.keys() for methods in cubie.parameters['actions']['boot']['methods']][0])
        u_boot_params = [
            methods for methods in cubie.parameters['actions']['boot']['methods']
            if 'u-boot' in methods.keys()
        ][0]['u-boot']
        self.assertIn('usb', u_boot_params)
        self.assertIn('commands', u_boot_params['usb'])
        self.assertIn('parameters', u_boot_params)
        self.assertIn('boot_message', u_boot_params['parameters'])
        self.assertIn('bootloader_prompt', u_boot_params['parameters'])

    def test_job_parameters(self):
        """
        Test that the job parameters match expected structure
        """
        job_parser = JobParser()
        cubie = NewDevice('cubie1')
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/cubietruck-removable.yaml')
        sample_job_data = open(sample_job_file)
        job = job_parser.parse(sample_job_data, cubie)
        try:
            job.validate()
        except JobError:
            self.fail(job.pipeline.errors)
        mass_storage = None  # deploy
        for action in job.pipeline.actions:
            if isinstance(action, DeployAction):
                if isinstance(action, MassStorage):
                    self.assertTrue(action.valid)
                    agent = action.parameters['download']
                    self.assertTrue(agent.startswith('/'))  # needs to be a full path but on the device, so avoid os.path
                    self.assertIn(action.parameters['device'], job.device.parameters['media']['usb'])
                    mass_storage = action
        self.assertIsNotNone(mass_storage)
        self.assertIn('device', mass_storage.parameters)
        self.assertIn(mass_storage.parameters['device'], cubie.parameters['media']['usb'])
        self.assertIsNotNone(mass_storage.get_common_data('u-boot', 'device'))
        u_boot_params = [
            methods for methods in cubie.parameters['actions']['boot']['methods']
            if 'u-boot' in methods.keys()
        ][0]['u-boot']
        self.assertEqual(mass_storage.get_common_data('bootloader_prompt', 'prompt'), u_boot_params['parameters']['bootloader_prompt'])

    def test_deployment(self):
        job_parser = JobParser()
        cubie = NewDevice('cubie1')
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/cubietruck-removable.yaml')
        sample_job_data = open(sample_job_file)
        job = job_parser.parse(sample_job_data, cubie)
        job.validate()
        self.assertIn('usb', cubie.parameters['media'].keys())
        deploy_params = [methods for methods in job.parameters['actions'] if 'deploy' in methods.keys()][0]['deploy']
        self.assertIn('device', deploy_params)
        self.assertIn(deploy_params['device'], cubie.parameters['media']['usb'])
        self.assertIn('uuid', cubie.parameters['media']['usb'][deploy_params['device']])
        self.assertIn('device_id', cubie.parameters['media']['usb'][deploy_params['device']])
        self.assertNotIn('boot_part', cubie.parameters['media']['usb'][deploy_params['device']])
        deploy_action = job.pipeline.actions[0]
        self.assertIsInstance(deploy_action, MassStorage)
        self.assertIn('image', deploy_action.parameters.keys())
        dd_action = deploy_action.internal_pipeline.actions[1]
        self.assertEqual(
            dd_action.boot_params[dd_action.parameters['device']]['uuid'],
            'usb-SanDisk_Ultra_20060775320F43006019-0:0')
        self.assertEqual('0', '%s' % dd_action.get_common_data('u-boot', 'boot_part'))
        self.assertTrue(type(dd_action.get_common_data('uuid', 'boot_part')) is str)
        self.assertEqual('0:1', dd_action.get_common_data('uuid', 'boot_part'))

    def test_substitutions(self):
        """
        Test substitution of secondary media values into u-boot commands

        Unlike most u-boot calls, removable knows in advance all the values it needs to substitute
        into the boot commands for the secondary deployment as these are fixed by the device config
        and the image details from the job submission.
        """
        job_parser = JobParser()
        cubie = NewDevice('cubie1')
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/cubietruck-removable.yaml')
        sample_job_data = open(sample_job_file)
        job = job_parser.parse(sample_job_data, cubie)
        job.validate()
        boot_params = [methods for methods in job.parameters['actions'] if 'boot' in methods.keys()][0]['boot']
        self.assertIn('ramdisk', boot_params)
        self.assertIn('kernel', boot_params)
        self.assertIn('dtb', boot_params)
        self.assertIn('root_uuid', boot_params)
        self.assertIn('boot_part', boot_params)
        self.assertIn('type', boot_params)
        self.assertGreater(len(job.pipeline.actions), 1)
        self.assertIsNotNone(job.pipeline.actions[1].internal_pipeline)
        u_boot_action = job.pipeline.actions[1].internal_pipeline.actions[1]
        self.assertIsNotNone(u_boot_action.get_common_data('u-boot', 'device'))
        self.assertEqual(u_boot_action.name, "uboot-overlay")
        self.assertIn('u-boot', u_boot_action.parameters)
        self.assertIn('usb', u_boot_action.parameters['u-boot'])
        self.assertIn('commands', u_boot_action.parameters['u-boot']['usb'])
        commands_list = u_boot_action.parameters['u-boot']['usb']['commands']
        device_id = u_boot_action.get_common_data('u-boot', 'device')
        substitutions = {
            '{BOOTX}': "%s %s %s %s" % (
                u_boot_action.parameters['type'],
                cubie.parameters['parameters'][u_boot_action.parameters['type']]['kernel'],
                cubie.parameters['parameters'][u_boot_action.parameters['type']]['ramdisk'],
                cubie.parameters['parameters'][u_boot_action.parameters['type']]['dtb'],),
            '{RAMDISK}': boot_params['ramdisk'],
            '{KERNEL}': boot_params['kernel'],
            '{DTB}': boot_params['dtb'],
            '{ROOT}': boot_params['root_uuid'],
            '{ROOT_PART}': "%s:%s" % (
                cubie.parameters['media']['usb'][device_id]['device_id'],
                u_boot_action.parameters['boot_part']
            )
        }

        self.assertEqual('bootz 0x47000000 0x48000000 0x43000000', substitutions['{BOOTX}'])
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
                "setenv loadfdt 'load usb 0:1 ${fdt_addr_r} /boot/dtb-3.16.0-4-armmp-lpae''",
                "setenv bootargs 'console=ttyS0,115200n8 root=UUID=159d17cc-697c-4125-95a0-a3775e1deabe ip=dhcp'",
                "setenv bootcmd 'run loadkernel; run loadinitrd; run loadfdt; bootz 0x47000000 0x48000000 0x43000000'", 'boot'
            ]
        )
        # reference commands:
        #        setenv loadkernel 'load usb 0:1 ${kernel_addr_r} /boot/vmlinuz-3.16.0-4-armmp-lpae'
        #        setenv loadinitrd 'load usb 0:1 ${initrd_addr_r} /boot/initrd.img-3.16.0-4-armmp-lpae.u-boot; setenv initrd_size ${filesize}'
        #        setenv loadfdt 'load usb 0:1 ${fdt_addr_r} /boot/dtb-3.16.0-4-armmp-lpae'
        #        setenv bootargs 'console=ttyS0,115200 rw root=UUID=159d17cc-697c-4125-95a0-a3775e1deabe ip=dhcp'
