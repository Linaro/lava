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
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.boot.ssh import SchrootAction
from lava_dispatcher.pipeline.actions.boot.qemu import BootVMAction
from lava_dispatcher.pipeline.connections.ssh import ConnectDynamicSsh
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.test.test_basic import pipeline_reference
from lava_dispatcher.pipeline.utils.filesystem import check_ssh_identity_file


class Factory(object):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_ssh_job(self, filename, output_dir=None):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/ssh-host-01.yaml'))
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(kvm_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 0, socket_addr=None, output_dir=output_dir)
        return job

    def create_bbb_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(kvm_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, output_dir=output_dir)
        return job


class TestConnection(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestConnection, self).setUp()
        factory = Factory()
        self.job = factory.create_ssh_job('sample_jobs/ssh-deploy.yaml', mkdtemp())
        self.guest_job = factory.create_bbb_job('sample_jobs/bbb-ssh-guest.yaml', mkdtemp())

    @unittest.skipIf(infrastructure_error('schroot'), "schroot not installed")
    def test_ssh_job(self):
        self.assertIsNotNone(self.job)
        self.job.validate()
        self.assertEqual([], self.job.pipeline.errors)
        # Check Pipeline
        description_ref = pipeline_reference('ssh-deploy.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

    @unittest.skipIf(infrastructure_error('schroot'), "schroot not installed")
    def test_ssh_authorize(self):
        overlay = [action for action in self.job.pipeline.actions if action.name == 'scp-overlay'][0]
        prepare = [action for action in overlay.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        authorize = [action for action in prepare.internal_pipeline.actions if action.name == 'ssh-authorize'][0]
        self.assertFalse(authorize.active)
        self.job.validate()
        # only secondary connections set 'active' which then copies the identity file into the overlay.
        self.assertFalse(authorize.active)

    def test_ssh_identity(self):
        params = {
            'tftp': 'None',
            'usb': 'None',
            'ssh': {
                'host': '172.16.200.165', 'options': [
                    '-o', 'Compression=yes', '-o', 'UserKnownHostsFile=/dev/null',
                    '-o', 'PasswordAuthentication=no', '-o', 'StrictHostKeyChecking=no',
                    '-o', 'LogLevel=FATAL', '-l', 'root ', '-p', 22],
                'identity_file': 'device/dynamic_vm_keys/lava'
            }
        }
        check = check_ssh_identity_file(params)
        self.assertIsNone(check[0])
        self.assertIsNotNone(check[1])
        self.assertEqual(os.path.basename(check[1]), 'lava')

    @unittest.skipIf(infrastructure_error('schroot'), "schroot not installed")
    def test_ssh_params(self):
        self.assertEqual(self.job.device['hostname'], 'ssh-host-01')
        self.assertTrue(any('ssh' in item for item in self.job.device['actions']['deploy']['methods']))
        params = self.job.device['actions']['deploy']['methods']
        identity = os.path.realpath(os.path.join(__file__, '../../../', params['ssh']['identity_file']))
        self.assertTrue(os.path.exists(identity))
        test_command = [
            'ssh', '-o', 'Compression=yes', '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'PasswordAuthentication=no', '-o', 'StrictHostKeyChecking=no',
            '-o', 'LogLevel=FATAL', '-l', 'root ',
            '-p', '8022']
        self.job.validate()
        login = [action for action in self.job.pipeline.actions if action.name == 'login-ssh'][0]
        self.assertIn('primary-ssh', [action.name for action in login.internal_pipeline.actions])
        primary = [action for action in login.internal_pipeline.actions if action.name == 'primary-ssh'][0]
        self.assertEqual(identity, primary.identity_file)
        self.assertEqual(primary.host, params['ssh']['host'])
        self.assertEqual(test_command, primary.command)
        # idempotency check
        self.job.validate()
        self.assertEqual(identity, primary.identity_file)
        self.assertEqual(test_command, primary.command)
        bad_port = {
            'host': 'localhost',
            'options': [
                '-o', 'Compression=yes', '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'PasswordAuthentication=no', '-o', 'StrictHostKeyChecking=no',
                '-o', 'LogLevel=FATAL', '-l', 'root ', '-p', 8022
            ],
            'identity_file': 'device/dynamic_vm_keys/lava'}
        self.job.device['actions']['deploy']['methods']['ssh'] = bad_port
        with self.assertRaises(JobError):
            self.job.validate()

    @unittest.skipIf(infrastructure_error('schroot'), "schroot not installed")
    def test_scp_command(self):
        self.job.validate()
        overlay = [action for action in self.job.pipeline.actions if action.name == 'scp-overlay'][0]
        deploy = [action for action in overlay.internal_pipeline.actions if action.name == 'scp-deploy'][0]
        scp = [action for action in overlay.internal_pipeline.actions if action.name == 'prepare-scp-overlay'][0]
        self.assertIsNotNone(scp)
        self.assertIn('scp', deploy.scp)
        self.assertNotIn('ssh', deploy.scp)
        self.assertIn('ssh', deploy.command)
        self.assertNotIn('scp', deploy.command)
        self.assertIn('lava_test_results_dir', deploy.data)
        self.assertIn('/lava-', deploy.data['lava_test_results_dir'])

    @unittest.skipIf(infrastructure_error('schroot'), "schroot not installed")
    def test_schroot_params(self):
        self.assertIn('schroot-login', [action.name for action in self.job.pipeline.actions])
        schroot = [action for action in self.job.pipeline.actions if action.name == "schroot-login"][0]
        self.job.validate()
        schroot.run_command(['schroot', '-i', '-c', schroot.parameters['schroot']])
        if any("Chroot not found" in chk for chk in schroot.errors) or not schroot.valid:
            # schroot binary found but no matching chroot configured - skip test
            self.skipTest("no schroot support for %s" % schroot.parameters['schroot'])
        bad_chroot = 'unobtainium'
        schroot.run_command(['schroot', '-i', '-c', bad_chroot])
        if not any("Chroot not found" in chk for chk in schroot.errors) or schroot.valid:
            self.fail("Failed to catch a missing schroot name")

        self.assertIsInstance(schroot, SchrootAction)
        self.assertEqual(schroot.parameters['schroot'], 'unstable')
        boot_act = [boot['boot'] for boot in self.job.parameters['actions']
                    if 'boot' in boot and 'schroot' in boot['boot']][0]
        self.assertEqual(boot_act['schroot'], schroot.parameters['schroot'])

    def test_guest_ssh(self):
        self.assertIsNotNone(self.guest_job)
        self.guest_job.validate()
        self.assertEqual([], self.guest_job.pipeline.errors)
        scp_overlay = [item for item in self.guest_job.pipeline.actions if item.name == 'scp-overlay']
        environment = scp_overlay[0].get_common_data('environment', 'env_dict')
        self.assertIsNotNone(environment)
        self.assertIn('LANG', environment.keys())
        self.assertIn('C', environment.values())
        self.assertEqual(len(scp_overlay), 1)
        overlay = [item for item in scp_overlay[0].internal_pipeline.actions if item.name == 'lava-overlay']
        multinode = [item for item in overlay[0].internal_pipeline.actions if item.name == 'lava-multinode-overlay']
        self.assertEqual(len(multinode), 1)
        # Check Pipeline
        description_ref = pipeline_reference('ssh-guest.yaml')
        self.assertEqual(description_ref, self.guest_job.pipeline.describe(False))
