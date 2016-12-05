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
import uuid
import json
import logging
import unittest
from lava_dispatcher.pipeline.test.fake_coordinator import TestCoordinator
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.pipeline.actions.deploy.image import DeployImagesAction
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction, MultinodeOverlayAction, CustomisationAction
from lava_dispatcher.pipeline.actions.boot.qemu import BootQemuRetry, CallQemuAction
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.test.multinode import MultinodeTestAction
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol
from lava_dispatcher.pipeline.action import (
    TestError,
    JobError,
    Timeout,
    InfrastructureError,
)
from lava_dispatcher.pipeline.utils.constants import LAVA_MULTINODE_SYSTEM_TIMEOUT
from lava_dispatcher.pipeline.test.test_defs import allow_missing_path


# pylint: disable=protected-access,superfluous-parens


class TestMultinode(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        """
        Attempt to setup a valid group with clients and test the protocol
        """
        super(TestMultinode, self).setUp()
        factory = Factory()
        self.client_job = factory.create_kvm_job('sample_jobs/kvm-multinode-client.yaml')
        self.server_job = factory.create_kvm_job('sample_jobs/kvm-multinode-server.yaml')
        self.job_id = "100"
        self.coord = TestCoordinator()

    def _cleanup(self):
        old_name = self.coord.group_name
        while self.coord.group_size > 0:
            self.coord._clearGroupData({"group_name": old_name})
            self.coord.group_size -= 1
        self.assertTrue(self.coord.group['group'] != old_name)
        self.assertTrue(self.coord.group['group'] == '')
        self.coord.conn.clearPasses()

    class TestClient(MultinodeProtocol):
        """
        Override the socket calls to simply pass messages directly to the TestCoordinator
        """
        def __init__(self, coord, parameters, job_id):
            super(TestMultinode.TestClient, self).__init__(parameters, job_id)
            self.coord = coord
            self.debug_setup()
            self.client_name = "fake"

        def __call__(self, args):
            try:
                json.loads(args)
            except ValueError:
                raise TestError("Invalid arguments to %s protocol" % self.name)
            return self._send(json.loads(args))

        def _send(self, msg, system=False):
            msg.update(self.base_message)
            return json.dumps(self.coord.dataReceived(msg))

    def test_multinode_jobs(self):
        self.assertIsNotNone(self.client_job)
        self.assertIsNotNone(self.server_job)
        allow_missing_path(self.client_job.validate, self, 'qemu-system-x86_64')
        allow_missing_path(self.server_job.validate, self, 'qemu-system-x86_64')
        self.assertEqual(self.client_job.pipeline.errors, [])
        self.assertEqual(self.server_job.pipeline.errors, [])

    def test_protocol(self):
        self.assertEqual(
            ['lava-multinode'],
            [protocol.name for protocol in self.client_job.protocols])
        client_protocol = [protocol for protocol in self.client_job.protocols][0]
        server_protocol = [protocol for protocol in self.server_job.protocols][0]
        self.assertEqual(client_protocol.name, server_protocol.name)
        self.assertIn('target_group', client_protocol.parameters['protocols'][client_protocol.name].keys())
        self.assertIn('actions', self.client_job.parameters.keys())
        try:
            self.client_job.validate()
            self.server_job.validate()
        except InfrastructureError:
            pass
        self.assertIn('role', client_protocol.parameters['protocols'][client_protocol.name].keys())
        self.assertEqual([], self.client_job.pipeline.errors)
        self.assertEqual([], self.server_job.pipeline.errors)

    def test_settings(self):
        """
        If lava-coordinator is configured, test that the config can be loaded.
        """
        filename = "/etc/lava-coordinator/lava-coordinator.conf"
        if not os.path.exists(filename):
            self.skipTest("Coordinator not configured")
        self.assertTrue(os.path.exists(filename))
        client_protocol = [protocol for protocol in self.client_job.protocols][0]
        settings = client_protocol.read_settings(filename)
        self.assertIn('blocksize', settings)
        self.assertIn("coordinator_hostname", settings)

    def test_multinode_pipeline(self):
        deploy = [action for action in self.client_job.pipeline.actions if isinstance(action, DeployImagesAction)][0]
        self.assertIsNotNone(deploy)
        overlay = [action for action in deploy.internal_pipeline.actions if isinstance(action, OverlayAction)][0]
        self.assertIsNotNone(overlay)
        client_multinode = [
            action for action in overlay.internal_pipeline.actions if isinstance(action, MultinodeOverlayAction)
        ][0]
        self.assertIsNotNone(client_multinode)
        client_multinode.validate()
        self.assertEqual(client_multinode.role, 'client')

        deploy = [action for action in self.server_job.pipeline.actions if isinstance(action, DeployImagesAction)][0]
        self.assertIsNotNone(deploy)
        overlay = [action for action in deploy.internal_pipeline.actions if isinstance(action, OverlayAction)][0]
        self.assertIsNotNone(overlay)
        server_multinode = [
            action for action in overlay.internal_pipeline.actions if isinstance(action, MultinodeOverlayAction)
        ][0]
        self.assertIsNotNone(server_multinode)
        server_multinode.validate()
        self.assertEqual(server_multinode.role, 'server')

        client_protocol = [protocol for protocol in self.client_job.protocols][0]
        server_protocol = [protocol for protocol in self.server_job.protocols][0]
        self.assertEqual(
            set([client_name for client_name in
                 client_protocol.parameters['protocols'][client_protocol.name]['roles']]),
            {'kvm02', 'kvm01', 'yaml_line'})
        self.assertEqual(
            set([client_name for client_name in
                 server_protocol.parameters['protocols'][server_protocol.name]['roles']]),
            {'kvm02', 'kvm01', 'yaml_line'})
        self.assertEqual(client_protocol.parameters['protocols'][client_protocol.name]['roles']['kvm01'], 'client')
        self.assertEqual(client_protocol.parameters['protocols'][client_protocol.name]['roles']['kvm02'], 'server')
        self.assertEqual(server_protocol.parameters['protocols'][client_protocol.name]['roles']['kvm01'], 'client')
        self.assertEqual(server_protocol.parameters['protocols'][client_protocol.name]['roles']['kvm02'], 'server')
        self.assertEqual(client_multinode.lava_multi_node_cache_file, '/tmp/lava_multi_node_cache.txt')
        self.assertIsNotNone(client_multinode.lava_multi_node_test_dir)
        self.assertTrue(os.path.exists(client_multinode.lava_multi_node_test_dir))

    def test_multinode_test_protocol(self):
        """
        Test multinode procotol message handling against TestCoordinator
        """
        testshell = [action for action in self.server_job.pipeline.actions if isinstance(action, MultinodeTestAction)][0]
        self.assertIsNotNone(testshell)
        testshell.validate()
        self.assertIsNotNone(testshell.protocols)
        self.assertEqual(testshell.timeout.duration, 30)
        self.assertIn(MultinodeProtocol.name, [protocol.name for protocol in testshell.protocols])
        protocol_names = [protocol.name for protocol in testshell.protocols if protocol in testshell.protocols]
        self.assertNotEqual(protocol_names, [])
        protocols = [protocol for protocol in testshell.job.protocols if protocol.name in protocol_names]
        self.assertNotEqual(protocols, [])
        multinode_dict = {'multinode': '<LAVA_MULTI_NODE> <LAVA_(\\S+) ([^>]+)>'}
        self.assertEqual(multinode_dict, testshell.multinode_dict)
        self.assertIn('multinode', testshell.patterns)
        self.assertEqual(testshell.patterns['multinode'], multinode_dict['multinode'])
        testshell._reset_patterns()
        self.assertIn('multinode', testshell.patterns)
        self.assertEqual(testshell.patterns['multinode'], multinode_dict['multinode'])
        for protocol in protocols:
            protocol.debug_setup()
            if isinstance(protocol, MultinodeProtocol):
                self.assertIsNotNone(protocol.base_message)
            else:
                self.fail("Unexpected protocol")
            self.assertIs(True, protocol.valid)
        self.assertIsNone(self.coord.dataReceived({}))

    def test_multinode_description(self):
        self.assertIsNotNone(self.client_job)
        allow_missing_path(self.client_job.validate, self, 'qemu-system-x86_64')
        # check that the description can be re-loaded as valid YAML
        for action in self.client_job.pipeline.actions:
            data = action.explode()
            data_str = yaml.dump(data)
            yaml.load(data_str)

    def test_multinode_timeout(self):
        """
        Test the protocol timeout is assigned to the action
        """
        testshell = [action for action in self.client_job.pipeline.actions if isinstance(action, MultinodeTestAction)][0]
        testshell.validate()
        self.assertIn(30, [p.poll_timeout.duration for p in testshell.protocols])
        self.assertIn('minutes', testshell.parameters['lava-multinode']['timeout'])
        self.assertEqual(10, testshell.parameters['lava-multinode']['timeout']['minutes'])
        self.assertEqual(
            testshell.signal_director.base_message['timeout'],
            Timeout.parse(testshell.parameters['lava-multinode']['timeout'])
        )

    def test_signal_director(self):
        """
        Test the setup of the Multinode signal director
        """
        testshell = [action for action in self.server_job.pipeline.actions if isinstance(action, MultinodeTestAction)][0]
        testshell.validate()
        self.assertEqual(30, testshell.timeout.duration)
        self.assertIsNotNone(testshell.signal_director)
        self.assertIsNotNone(testshell.signal_director.protocol)
        self.assertIs(type(testshell.protocols), list)
        self.assertIsNot(type(testshell.signal_director.protocol), list)
        self.assertIsInstance(testshell.signal_director.protocol, MultinodeProtocol)

    def test_empty_poll(self):
        """ Check that an empty message gives an empty response
        """
        self.assertIsNone(self.coord.dataReceived({}))

    def test_empty_receive(self):
        """ Explicitly expect an empty response with an empty message
        """
        self.assertIsNone(self.coord.expectResponse(None))
        self.coord.dataReceived({})

    def test_start_group_incomplete(self):
        """ Create a group but fail to populate it with enough devices and cleanup
        """
        self.coord.group_name = str(uuid.uuid4())
        self.coord.group_size = 2
        self.coord.conn.response = {'response': "ack"}
        self.coord.client_name = "incomplete"
        ret = self.coord._updateData(
            {"client_name": self.coord.client_name,
             "group_size": self.coord.group_size,
             "role": "tester",
             "hostname": "localhost",
             "group_name": self.coord.group_name})
        self.assertEqual(self.coord.client_name, 'incomplete')
        self.assertEqual(1, len(self.coord.group['clients']))
        self.coord.group_size = 1
        self.assertTrue(ret == "incomplete")
        self._cleanup()

    def test_start_group_complete(self):
        """ Create a group with enough devices and check for no errors.
        """
        self.coord.newGroup(2)
        ret = self.coord.addClient("completing")
        self.assertTrue(ret == "completing")
        ret = self.coord.addClient("completed")
        self.assertTrue(ret == "completed")

    def test_client(self):
        client = TestMultinode.TestClient(self.coord,
                                          self.client_job.parameters,
                                          self.job_id)
        client.settings['target'] = 'completed'
        self.coord.expectResponse('wait')
        client.initialise_group()
        self.coord.expectResponse('nack')
        client(json.dumps({
            'request': 'lava-send',  # deliberate typo
            'messageID': 'test',
            'message': 'testclient'
        }))
        self.coord.expectResponse('wait')
        reply = json.loads(client(json.dumps({
            'request': 'lava_wait',
            'messageID': 'test'
        })))
        self.assertIn('wait', reply['response'])

    def test_client_send_keyvalue(self):
        self.coord.newGroup(2)
        self.coord.addClient("completing")
        self.coord.addClient("completed")
        client = TestMultinode.TestClient(self.coord,
                                          self.client_job.parameters,
                                          self.job_id)
        TestMultinode.TestClient(self.coord, self.server_job.parameters,
                                 self.job_id)
        self.coord.expectResponse('wait')
        client.initialise_group()
        client.settings['target'] = 'completed'
        self.coord.expectResponse('ack')
        client(json.dumps({
            'request': 'lava_send',
            'messageID': 'test',
            'message': {
                'key': 'value'
            }
        }))
        self.coord.expectResponse('ack')
        reply = json.loads(client(json.dumps({
            'request': 'lava_wait',
            'messageID': 'test'
        })))
        self.assertEqual(
            {"message": {"kvm01": {"key": "value"}}, "response": "ack"},
            reply
        )

    def test_wait(self):
        client = TestMultinode.TestClient(self.coord,
                                          self.client_job.parameters,
                                          self.job_id)
        server = TestMultinode.TestClient(self.coord,
                                          self.server_job.parameters,
                                          self.job_id)
        client.settings['target'] = 'completed'
        self.coord.expectResponse('wait')
        client.initialise_group()
        self.coord.expectResponse('wait')
        client(json.dumps({
            'request': 'lava_wait',
            'messageID': 'test_wait',
        }))
        self.coord.expectResponse('wait')
        client(json.dumps({
            'request': 'lava_wait',
            'messageID': 'test_wait',
        }))
        self.coord.expectResponse('wait')
        client(json.dumps({
            'request': 'lava_wait',
            'messageID': 'test_wait',
        }))
        self.coord.expectResponse('ack')
        server(json.dumps({
            'request': 'lava_send',
            'messageID': 'test_wait',
        }))
        self.coord.expectResponse('ack')
        client(json.dumps({
            'request': 'lava_wait',
            'messageID': 'test_wait',
        }))

    def test_wait_all(self):
        client = TestMultinode.TestClient(self.coord,
                                          self.client_job.parameters,
                                          self.job_id)
        server = TestMultinode.TestClient(self.coord,
                                          self.server_job.parameters,
                                          self.job_id)
        client.settings['target'] = 'completed'
        self.coord.expectResponse('wait')
        client.initialise_group()
        client(json.dumps({
            'request': 'lava_wait_all',
            'messageID': 'test_wait_all',
        }))
        self.coord.expectResponse('wait')
        client(json.dumps({
            'request': 'lava_wait_all',
            'messageID': 'test_wait_all'
        }))
        self.coord.expectResponse('wait')
        client(json.dumps({
            'request': 'lava_wait_all',
            'messageID': 'test_wait_all'
        }))
        self.coord.expectResponse('ack')
        server(json.dumps({
            'request': 'lava_send',
            'messageID': 'test_wait_all',
        }))

    def test_wait_all_role(self):
        client = TestMultinode.TestClient(self.coord,
                                          self.client_job.parameters,
                                          self.job_id)
        server = TestMultinode.TestClient(self.coord,
                                          self.server_job.parameters,
                                          self.job_id)
        client.settings['target'] = 'completed'
        self.coord.expectResponse('wait')
        client.initialise_group()
        client(json.dumps({
            'request': 'lava_wait_all',
            'waitrole': 'server',
            'messageID': 'test_wait_all_role',
        }))
        self.coord.expectResponse('wait')
        client(json.dumps({
            'request': 'lava_wait_all',
            'waitrole': 'server',
            'messageID': 'test_wait_all_role'
        }))
        self.coord.expectResponse('wait')
        client(json.dumps({
            'request': 'lava_wait_all',
            'waitrole': 'server',
            'messageID': 'test_wait_all_role'
        }))
        self.coord.expectResponse('ack')
        server(json.dumps({
            'request': 'lava_send',
            'messageID': 'test_wait_all_role',
        }))

    def test_protocol_action(self):
        deploy = [action for action in self.client_job.pipeline.actions if isinstance(action, DeployImagesAction)][0]
        customise = [action for action in deploy.internal_pipeline.actions if isinstance(action, CustomisationAction)][0]
        self.assertIn('protocols', deploy.parameters)
        self.assertIn('protocols', customise.parameters)
        self.assertIn(MultinodeProtocol.name, customise.parameters['protocols'])
        customise_params = [
            params for params in customise.parameters['protocols'][MultinodeProtocol.name] if params['action'] == customise.name
        ][0]
        self.assertIn('action', customise_params)
        self.assertEqual(customise.name, customise_params['action'])
        multinode_protocol = [protocol for protocol in customise.job.protocols if protocol.name == MultinodeProtocol.name][0]
        self.assertIs(multinode_protocol.name, MultinodeProtocol.name)

        # yaml_line gets ignored by the api
        self.assertEqual(
            customise_params,
            {
                'action': customise.name,
                'request': 'lava-send',
                'messageID': 'test',
                'yaml_line': 48,
                'message': {
                    'key': 'value',
                    'yaml_line': 50
                },
            }
        )
        client_calls = {}
        for action in deploy.internal_pipeline.actions:
            if 'protocols' in action.parameters:
                for protocol in action.job.protocols:
                    for params in action.parameters['protocols'][protocol.name]:
                        api_calls = [params for name in params if name == 'action' and params[name] == action.name]
                        for call in api_calls:
                            client_calls.update(call)
        self.assertEqual(
            client_calls,
            {
                'action': 'customise',
                'message': {
                    'key': 'value',
                    'yaml_line': 50
                },
                'messageID': 'test',
                'request': 'lava-send',
                'yaml_line': 48
            }
        )

    def test_protocol_variables(self):  # pylint: disable=too-many-locals
        boot = [action for action in self.client_job.pipeline.actions if isinstance(action, BootAction)][0]
        self.assertIsNotNone(boot)
        retry = [action for action in boot.internal_pipeline.actions if isinstance(action, BootQemuRetry)][0]
        self.assertIsNotNone(retry)
        qemu_boot = [action for action in retry.internal_pipeline.actions if isinstance(action, CallQemuAction)][0]
        self.assertIsNotNone(qemu_boot)
        self.assertIn('protocols', qemu_boot.parameters)
        self.assertIn(MultinodeProtocol.name, qemu_boot.parameters['protocols'])
        mn_protocol = [protocol for protocol in qemu_boot.job.protocols if protocol.name == MultinodeProtocol.name][0]
        params = qemu_boot.parameters['protocols'][MultinodeProtocol.name]
        # params is a list - multiple actions can exist
        self.assertEqual(
            params,
            [{
                'action': 'execute-qemu',
                'message': {
                    'ipv4': '$IPV4',
                    'yaml_line': 67
                },
                'messageID': 'test',
                'request': 'lava-wait',
                'yaml_line': 64
            }])
        client_calls = {}
        for action in retry.internal_pipeline.actions:
            if 'protocols' in action.parameters:
                for protocol in action.job.protocols:
                    for params in action.parameters['protocols'][protocol.name]:
                        api_calls = [params for name in params if name == 'action' and params[name] == action.name]
                        for call in api_calls:
                            action.set_namespace_data(action=protocol.name, label=protocol.name, key=action.name, value=call)
                            client_calls.update(call)

        # now pretend that another job has called lava-send with the same messageID, this would be the reply to the
        # :lava-wait
        reply = {"/tmp/lava-dispatcher/slave/8833/device.yaml": {"ipaddr": "10.15.206.133"}}
        cparams = {'timeout': {'minutes': 5, 'yaml_line': 11}, 'messageID': 'ipv4', 'action': 'prepare-scp-overlay', 'message': {'ipaddr': '$ipaddr'}, 'request': 'lava-wait'}
        self.assertEqual(
            ('ipv4', {'ipaddr': '10.15.206.133'}),
            mn_protocol.collate(reply, cparams)
        )
        reply = {
            "message": {
                "kvm01": {
                    "ipv4": "192.168.0.2"
                }
            },
            "response": "ack"
        }
        self.assertEqual(
            ('test', {'ipv4': '192.168.0.2'}),
            mn_protocol.collate(reply, params)
        )

        replaceables = [key for key, value in params['message'].items()
                        if key != 'yaml_line' and value.startswith('$')]
        for item in replaceables:
            target_list = [val for val in reply['message'].items()]
            data = target_list[0][1]
            params['message'][item] = data[item]

        self.assertEqual(
            client_calls,
            {
                'action': 'execute-qemu',
                'message': {
                    'ipv4': reply['message'][self.client_job.device.target]['ipv4'],
                    'yaml_line': 67
                },
                'yaml_line': 64,
                'request': 'lava-wait',
                'messageID': 'test'
            }
        )


class TestProtocol(unittest.TestCase):  # pylint: disable=too-many-public-methods

    coord = None

    def setUp(self):
        """
        Unable to test actually sending messages - need a genuine group with clients and roles
        """
        self.job_id = "100"
        parameters = {
            'target': 'kvm01',
            'protocols': {
                'fake-multinode': {
                    'sub_id': 1,
                    'target_group': 'arbitrary-group-id',
                    'role': 'client',
                    'group_size': 2,
                    'roles': {
                        'kvm01': 'client',
                        'kvm02': 'server'
                    }
                }
            }
        }
        self.coord = TestCoordinator()
        self.protocol = TestProtocol.FakeProtocol(self.coord, parameters,
                                                  self.job_id)
        logging.getLogger('dispatcher').addHandler(logging.NullHandler())

    def _wrap_message(self, message, role):
        base_msg = {
            "timeout": 90,
            "client_name": self.coord.client_name,
            "group_name": self.coord.group_name,
            "role": role
        }
        base_msg.update(message)
        return base_msg

    def _cleanup(self):
        old_name = self.coord.group_name
        self.coord.expectResponse("ack")
        self.coord.expectMessage(None)
        while self.coord.group_size > 0:
            self.coord._clearGroupData({"group_name": old_name})
            self.coord.group_size -= 1
        # clear the group name and data
        self.assertTrue(self.coord.group['group'] != old_name)
        self.assertTrue(self.coord.group['group'] == '')
        self.coord.conn.clearPasses()

    class FakeClient(object):
        """
        acts as the client socket, passing data to the fake coordinator dataReceived() call
        """
        def __init__(self, fake_coordinator):
            self.coord = fake_coordinator
            self.header = True
            self.data = None
            self.coord.newGroup(2)
            self.coord.addClientRole("kvm01", "server")
            self.coord.addClientRole("kvm02", "client")

        def send(self, msg):
            if self.header:
                self.header = False
                assert(int(msg, 16) < 0xFFFE)
            else:
                message = json.loads(msg)
                self.coord.dataReceived(message)
                self.header = True

        def shutdown(self, how):
            pass

        def close(self):
            pass

        def recv(self, msg):
            """
            Allow the fake to send a properly formatted response.
            """
            if self.header:
                self.header = False
                return '1000'  # int('1000', 16) == 4096
            else:
                self.header = True
                return json.dumps({'response': 'ack'})

    class FakeProtocol(MultinodeProtocol):

        def __init__(self, fake_coordinator, parameters, job_id):
            # set the name before passing in the parameters based on that name
            self.name = "fake-multinode"
            super(TestProtocol.FakeProtocol, self).__init__(parameters, job_id)
            self.sock = TestProtocol.FakeClient(fake_coordinator)
            self.debug_setup()

        def _connect(self, delay):
            return True

        def finalise_protocol(self, device=None):
            """
            Allow the fake coordinator to finalise the protocol
            """
            pass

        def __call__(self, *args, **kwargs):
            super(TestProtocol.FakeProtocol, self).__call__(*args, **kwargs)

    def test_fake_protocol(self):
        self.protocol._connect(1)

    def test_empty_data(self):
        with self.assertRaises(JobError):
            self.protocol(None)

    def test_json_failure(self):
        msg = 'bad json'
        with self.assertRaises(ValueError):
            json.loads(msg)
        with self.assertRaises(JobError):
            self.protocol(msg)

    def test_missing_request(self):
        msg = {
            "None": ""
        }
        json.loads(json.dumps(msg))
        with self.assertRaises(JobError):
            self.protocol(msg)

    def test_fail_aggregation(self):
        """
        test that the refactored protocol fails to implement bundle aggregation
        """
        msg = {
            'request': 'aggregate'
        }
        json.loads(json.dumps(msg))
        with self.assertRaises(JobError):
            self.protocol(msg)

    def test_unsupported_request(self):
        msg = {
            'request': 'unsupported',
            'port': 3,
            'blocksize': 8,
            'messageID': 7
        }
        msg.update(self.protocol.base_message)
        with self.assertRaises(TestError):
            self.protocol(msg)

    def test_lava_send_too_long(self):
        msg = {
            'request': 'lava_send',
            'port': 3,
            'blocksize': 8,
            'messageID': 'a' * (int('0xFFFE', 16) + 10)
        }
        msg.update(self.protocol.base_message)
        self.coord.expectResponse("ack")
        with self.assertRaises(JobError):
            self.protocol(msg)


class TestDelayedStart(unittest.TestCase):  # pylint: disable=too-many-public-methods

    coord = None

    def setUp(self):
        """
        Unable to test actually sending messages - need a genuine group with clients and roles
        """
        job_id = "100"
        client_parameters = {
            'target': 'kvm01',
            'protocols': {
                'fake-multinode': {
                    'sub_id': 0,
                    'target_group': 'arbitrary-group-id',
                    'role': 'client',
                    'group_size': 2,
                    'roles': {
                        'kvm01': 'client',
                        'kvm02': 'server'
                    },
                    'request': 'lava-start',
                    'expect_role': 'server',
                    'timeout': {
                        'minutes': 10
                    }
                }
            }
        }
        bad_parameters = {
            'target': 'kvm01',
            'protocols': {
                'fake-multinode': {
                    'sub_id': 0,
                    'target_group': 'arbitrary-group-id',
                    'role': 'client',
                    'group_size': 2,
                    'roles': {
                        'kvm01': 'client',
                        'kvm02': 'server'
                    },
                    'request': 'lava-start',
                    'expect_role': 'client',
                    'timeout': {
                        'minutes': 10
                    }
                }
            }
        }
        server_parameters = {
            'target': 'kvm02',
            'protocols': {
                'fake-multinode': {
                    'sub_id': 0,
                    'target_group': 'arbitrary-group-id',
                    'role': 'server',
                    'group_size': 2,
                    'roles': {
                        'kvm01': 'client',
                        'kvm02': 'server'
                    }
                }
            }
        }
        self.coord = TestCoordinator()
        self.client_protocol = TestProtocol.FakeProtocol(self.coord,
                                                         client_parameters,
                                                         job_id)
        self.server_protocol = TestProtocol.FakeProtocol(self.coord,
                                                         server_parameters,
                                                         job_id)
        self.bad_protocol = TestProtocol.FakeProtocol(self.coord,
                                                      bad_parameters,
                                                      job_id)

    def test_lava_start(self):
        self.assertTrue(self.client_protocol.delayed_start)
        self.assertEqual(self.client_protocol.system_timeout.duration, 600)
        self.assertEqual(self.server_protocol.system_timeout.duration, LAVA_MULTINODE_SYSTEM_TIMEOUT)
        self.assertFalse(self.server_protocol.delayed_start)
        self.assertFalse(self.bad_protocol.valid)
