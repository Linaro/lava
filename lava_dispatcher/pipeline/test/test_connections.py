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
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.boot.ssh import SchrootAction
from lava_dispatcher.pipeline.actions.boot.qemu import BootVMAction
from lava_dispatcher.pipeline.connections.ssh import ConnectDynamicSsh
from lava_dispatcher.pipeline.utils.shell import which


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

    def test_ssh_job(self):
        self.assertIsNotNone(self.job)
        self.job.validate()
        self.assertEqual([], self.job.pipeline.errors)

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
            '-p', 8022]
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

    @unittest.skipIf(not which('schroot'), "schroot not installed")
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
        self.assertEqual(len(scp_overlay), 1)
        overlay = [item for item in scp_overlay[0].internal_pipeline.actions if item.name == 'lava-overlay']
        print [(item.name, item.level) for item in overlay[0].internal_pipeline.actions]
        prepare = [item for item in scp_overlay[0].internal_pipeline.actions if item.name == 'prepare-tftp-overlay']
        print [(item.name, item.level) for item in prepare[0].internal_pipeline.actions]
        self.assertEqual(len(overlay), 1)
        self.assertEqual(len(prepare), 1)
        multinode = [item for item in overlay[0].internal_pipeline.actions if item.name == 'lava-multinode-overlay']
        self.assertEqual(len(multinode), 1)
