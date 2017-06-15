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
import logging
import unittest
from lava_dispatcher.pipeline.action import JobError
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.action import Timeout
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.boot.ssh import SchrootAction
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.pipeline.test.utils import DummyLogger
from lava_dispatcher.pipeline.utils.filesystem import check_ssh_identity_file
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol


class ConnectionFactory(Factory):  # pylint: disable=too-few-public-methods
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
            job = parser.parse(sample_job_data, device, 0, None, dispatcher_config="",
                               output_dir=output_dir)
            job.logger = DummyLogger()
        return job

    def create_bbb_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(kvm_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "",
                               output_dir=output_dir)
            job.logger = DummyLogger()
        return job


class TestConnection(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestConnection, self).setUp()
        factory = ConnectionFactory()
        self.job = factory.create_ssh_job('sample_jobs/ssh-deploy.yaml', mkdtemp())
        self.guest_job = factory.create_bbb_job('sample_jobs/bbb-ssh-guest.yaml', mkdtemp())
        logging.getLogger('dispatcher').addHandler(logging.NullHandler())

    @unittest.skipIf(infrastructure_error('schroot'), "schroot not installed")
    def test_ssh_job(self):
        self.assertIsNotNone(self.job)
        self.job.validate()
        self.assertEqual([], self.job.pipeline.errors)
        # Check Pipeline
        description_ref = self.pipeline_reference('ssh-deploy.yaml')
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
            'ssh', '-o', 'Compression=yes',
            '-o', 'PasswordAuthentication=no',
            '-o', 'LogLevel=FATAL',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            '-i', identity,
            '-p', '8022'
        ]
        self.job.validate()
        login = [action for action in self.job.pipeline.actions if action.name == 'login-ssh'][0]
        self.assertIn('ssh-connection', [action.name for action in login.internal_pipeline.actions])
        primary = [action for action in login.internal_pipeline.actions if action.name == 'ssh-connection'][0]
        prepare = [action for action in login.internal_pipeline.actions if action.name == 'prepare-ssh'][0]
        self.assertTrue(prepare.primary)
        self.assertEqual(identity, primary.identity_file)
        self.assertEqual(primary.host, params['ssh']['host'])
        self.assertEqual(int(primary.ssh_port[1]), params['ssh']['port'])
        self.assertEqual(test_command, primary.command)
        # idempotency check
        self.job.validate()
        self.assertEqual(identity, primary.identity_file)
        self.assertEqual(test_command, primary.command)
        bad_port = {
            'host': 'localhost',
            'port': 'bob',
            'options': [
                '-o', 'Compression=yes', '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'PasswordAuthentication=no', '-o', 'StrictHostKeyChecking=no',
                '-o', 'LogLevel=FATAL'
            ],
            'identity_file': 'device/dynamic_vm_keys/lava'}
        self.job.device['actions']['deploy']['methods']['ssh'] = bad_port
        with self.assertRaises(JobError):
            self.job.validate()

    @unittest.skipIf(infrastructure_error('schroot'), "schroot not installed")
    def test_scp_command(self):
        self.job.validate()
        login = [action for action in self.guest_job.pipeline.actions if action.name == 'login-ssh'][0]
        scp = [action for action in login.internal_pipeline.actions if action.name == 'scp-deploy'][0]
        self.assertIsNotNone(scp)
        # FIXME: schroot needs to make use of scp
        self.assertNotIn('ssh', scp.scp)
        self.assertFalse(scp.primary)

    @unittest.skipIf(infrastructure_error('schroot'), "schroot not installed")
    def test_tar_command(self):
        self.job.validate()
        login = [item for item in self.job.pipeline.actions if item.name == 'login-ssh'][0]
        tar_flags = login.get_namespace_data(action='scp-overlay', label='scp-overlay', key='tar_flags')
        self.assertIsNotNone(tar_flags)
        self.assertEqual('--warning no-timestamp', tar_flags)

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

    def test_primary_ssh(self):
        factory = ConnectionFactory()
        job = factory.create_ssh_job('sample_jobs/primary-ssh.yaml', mkdtemp())
        job.validate()
        overlay = [action for action in job.pipeline.actions if action.name == 'scp-overlay'][0]
        self.assertIsNotNone(overlay.parameters['deployment_data'])
        tar_flags = overlay.parameters['deployment_data']['tar_flags'] if 'tar_flags' in overlay.parameters['deployment_data'].keys() else ''
        self.assertIsNotNone(tar_flags)

    def test_guest_ssh(self):  # pylint: disable=too-many-locals,too-many-statements
        self.assertIsNotNone(self.guest_job)
        description_ref = self.pipeline_reference('bbb-ssh-guest.yaml', job=self.guest_job)
        self.assertEqual(description_ref, self.guest_job.pipeline.describe(False))
        self.guest_job.validate()
        multinode = [protocol for protocol in self.guest_job.protocols if protocol.name == MultinodeProtocol.name][0]
        self.assertEqual(int(multinode.system_timeout.duration), 900)
        self.assertEqual([], self.guest_job.pipeline.errors)
        self.assertEqual(len([item for item in self.guest_job.pipeline.actions if item.name == 'scp-overlay']), 1)
        scp_overlay = [item for item in self.guest_job.pipeline.actions if item.name == 'scp-overlay'][0]
        prepare = [item for item in scp_overlay.internal_pipeline.actions if item.name == 'prepare-scp-overlay'][0]
        self.assertEqual(prepare.host_keys, ['ipv4'])
        self.assertEqual(prepare.get_namespace_data(action=prepare.name, label=prepare.name, key='overlay'), prepare.host_keys)
        params = prepare.parameters['protocols'][MultinodeProtocol.name]
        for call_dict in [call for call in params if 'action' in call and call['action'] == prepare.name]:
            del call_dict['yaml_line']
            if 'message' in call_dict:
                del call_dict['message']['yaml_line']
            if 'timeout' in call_dict:
                del call_dict['timeout']['yaml_line']
            self.assertEqual(
                call_dict, {
                    'action': 'prepare-scp-overlay',
                    'message': {'ipaddr': '$ipaddr'},
                    'messageID': 'ipv4', 'request': 'lava-wait',
                    'timeout': {'minutes': 5}
                },
            )
        login = [action for action in self.guest_job.pipeline.actions if action.name == 'login-ssh'][0]
        scp = [action for action in login.internal_pipeline.actions if action.name == 'scp-deploy'][0]
        self.assertFalse(scp.primary)
        ssh = [action for action in login.internal_pipeline.actions if action.name == 'prepare-ssh'][0]
        self.assertFalse(ssh.primary)
        self.assertIsNotNone(scp.scp)
        self.assertFalse(scp.primary)
        self.assertIn('host_key', login.parameters['parameters'])
        self.assertIn('hostID', login.parameters['parameters'])
        self.assertIn(  # ipv4
            login.parameters['parameters']['hostID'],
            prepare.host_keys)
        prepare.set_namespace_data(
            action=MultinodeProtocol.name, label=MultinodeProtocol.name,
            key='ipv4', value={'ipaddr': '172.16.200.165'})
        self.assertEqual(prepare.get_namespace_data(
            action=prepare.name, label=prepare.name, key='overlay'), prepare.host_keys)
        self.assertIn(
            login.parameters['parameters']['host_key'],
            prepare.get_namespace_data(
                action=MultinodeProtocol.name, label=MultinodeProtocol.name, key=login.parameters['parameters']['hostID']))
        host_data = prepare.get_namespace_data(
            action=MultinodeProtocol.name, label=MultinodeProtocol.name, key=login.parameters['parameters']['hostID'])
        self.assertEqual(
            host_data[login.parameters['parameters']['host_key']],
            '172.16.200.165'
        )
        data = scp_overlay.get_namespace_data(action=MultinodeProtocol.name, label=MultinodeProtocol.name, key='ipv4')
        if 'protocols' in scp_overlay.parameters:
            for params in scp_overlay.parameters['protocols'][MultinodeProtocol.name]:
                (replacement_key, placeholder) = [
                    (key, value)for key, value in params['message'].items() if key != 'yaml_line'][0]
                self.assertEqual(data[replacement_key], '172.16.200.165')
                self.assertEqual(placeholder, '$ipaddr')
        environment = scp_overlay.get_namespace_data(action=prepare.name, label='environment', key='env_dict')
        self.assertIsNotNone(environment)
        self.assertIn('LANG', environment.keys())
        self.assertIn('C', environment.values())
        overlay = [item for item in scp_overlay.internal_pipeline.actions if item.name == 'lava-overlay']
        self.assertIn('action', overlay[0].parameters['protocols'][MultinodeProtocol.name][0])
        self.assertIn('message', overlay[0].parameters['protocols'][MultinodeProtocol.name][0])
        self.assertIn('timeout', overlay[0].parameters['protocols'][MultinodeProtocol.name][0])
        msg_dict = overlay[0].parameters['protocols'][MultinodeProtocol.name][0]['message']
        for key, value in msg_dict.items():
            if key == 'yaml_line':
                continue
            self.assertTrue(value.startswith('$'))
            self.assertFalse(key.startswith('$'))
        self.assertIn('request', overlay[0].parameters['protocols'][MultinodeProtocol.name][0])
        multinode = [item for item in overlay[0].internal_pipeline.actions if item.name == 'lava-multinode-overlay']
        self.assertEqual(len(multinode), 1)
        # Check Pipeline
        description_ref = self.pipeline_reference('ssh-guest.yaml', job=self.guest_job)
        self.assertEqual(description_ref, self.guest_job.pipeline.describe(False))


class TestTimeouts(StdoutTestCase):
    """
    Test action and connection timeout parsing.
    """

    def create_custom_job(self, data, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        parser = JobParser()
        job = parser.parse(data, device, 4212, None, "",
                           output_dir=output_dir)
        return job

    def test_action_timeout(self):
        factory = ConnectionFactory()
        job = factory.create_bbb_job('sample_jobs/uboot-ramdisk.yaml')
        job.validate()
        deploy = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        test_action = [action for action in job.pipeline.actions if action.name == 'lava-test-retry'][0]
        test_shell = [action for action in test_action.internal_pipeline.actions if action.name == 'lava-test-shell'][0]
        self.assertEqual(test_shell.connection_timeout.duration, 240)  # job specifies 4 minutes
        self.assertEqual(test_shell.timeout.duration, 300)  # job (test action block) specifies 5 minutes
        self.assertEqual(deploy.timeout.duration, 120)  # job specifies 2 minutes
        self.assertNotEqual(deploy.connection_timeout.duration, Timeout.default_duration())
        self.assertNotEqual(deploy.connection_timeout.duration, test_shell.connection_timeout)
        self.assertEqual(test_action.timeout.duration, 300)
        uboot = [action for action in job.pipeline.actions if action.name == 'uboot-action'][0]
        retry = [action for action in uboot.internal_pipeline.actions if action.name == 'uboot-retry'][0]
        auto = [action for action in retry.internal_pipeline.actions if action.name == 'auto-login-action'][0]
        self.assertEqual(auto.timeout.duration / 60, 9)  # 9 minutes in the job def

    def test_job_connection_timeout(self):
        """
        Test connection timeout specified in the submission YAML
        """
        y_file = os.path.join(os.path.dirname(__file__), './sample_jobs/uboot-ramdisk.yaml')
        with open(y_file, 'r') as uboot_ramdisk:
            data = yaml.load(uboot_ramdisk)
        data['timeouts']['connection'] = {'seconds': 20}
        job = self.create_custom_job(yaml.dump(data))
        for action in job.pipeline.actions:
            if action.internal_pipeline:
                for check_action in action.internal_pipeline.actions:
                    if check_action.connection_timeout and check_action.name not in ['uboot-retry', 'lava-test-shell']:
                        # lava-test-shell and uboot-retry have overrides in this sample job
                        # lava-test-shell from the job, uboot-retry from the device
                        self.assertEqual(check_action.connection_timeout.duration, 20)
        deploy = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        self.assertIsNotNone(deploy)
        test_action = [action for action in job.pipeline.actions if action.name == 'lava-test-retry'][0]
        test_shell = [action for action in test_action.internal_pipeline.actions if action.name == 'lava-test-shell'][0]
        self.assertEqual(test_shell.connection_timeout.duration, 20)
        self.assertEqual(test_shell.timeout.duration, 300)
        uboot = [action for action in job.pipeline.actions if action.name == 'uboot-action'][0]
        retry = [action for action in uboot.internal_pipeline.actions if action.name == 'uboot-retry'][0]
        auto = [action for action in retry.internal_pipeline.actions if action.name == 'auto-login-action'][0]
        self.assertEqual(auto.connection_timeout.duration / 60, 12)

    def test_action_connection_timeout(self):
        """
        Test connection timeout specified for a particular action
        """
        y_file = os.path.join(os.path.dirname(__file__), './sample_jobs/uboot-ramdisk.yaml')
        with open(y_file, 'r') as uboot_ramdisk:
            data = yaml.load(uboot_ramdisk)
        connection_timeout = Timeout.parse(data['timeouts']['connection'])
        self.assertEqual(connection_timeout, 240)
        job = self.create_custom_job(yaml.dump(data))
        boot = [action for action in job.pipeline.actions if action.name == 'uboot-action'][0]
        retry = [action for action in boot.internal_pipeline.actions if action.name == 'uboot-retry'][0]
        self.assertEqual(retry.timeout.duration, 90)  # Set by the job global action timeout
        self.assertEqual(retry.connection_timeout.duration, 45)
