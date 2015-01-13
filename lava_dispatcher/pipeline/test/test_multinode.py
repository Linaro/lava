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
import uuid
import json
import unittest
from lava_dispatcher.pipeline.test.fake_coordinator import TestCoordinator
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.pipeline.actions.deploy.image import DeployImageAction
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction, MultinodeOverlayAction
from lava_dispatcher.pipeline.actions.test.multinode import MultinodeTestAction
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol
from lava_dispatcher.pipeline.action import TestError, JobError

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
        def __init__(self, coord, parameters):
            super(TestMultinode.TestClient, self).__init__(parameters)
            self.coord = coord
            self.debug_setup()
            self.client_name = "fake"

        def __call__(self, args):
            try:
                json.loads(args)
            except ValueError:
                raise TestError("Invalid arguments to %s protocol" % self.name)
            self._send(json.loads(args))

        def _send(self, msg, system=False):
            msg.update(self.base_message)
            return json.dumps(self.coord.dataReceived(msg))

    def test_multinode_jobs(self):
        self.assertIsNotNone(self.client_job)
        self.assertIsNotNone(self.server_job)
        self.client_job.validate()
        self.assertEqual(self.client_job.pipeline.errors, [])
        self.server_job.validate()
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
        self.client_job.validate()
        self.server_job.validate()
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
        deploy = [action for action in self.client_job.pipeline.actions if isinstance(action, DeployImageAction)][0]
        self.assertIsNotNone(deploy)
        overlay = [action for action in deploy.internal_pipeline.actions if isinstance(action, OverlayAction)][0]
        self.assertIsNotNone(overlay)
        client_multinode = [
            action for action in overlay.internal_pipeline.actions if isinstance(action, MultinodeOverlayAction)
        ][0]
        self.assertIsNotNone(client_multinode)
        client_multinode.validate()
        self.assertEqual(client_multinode.role, 'client')

        deploy = [action for action in self.server_job.pipeline.actions if isinstance(action, DeployImageAction)][0]
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
        self.assertEqual([client_name for client_name in client_protocol.parameters['protocols'][client_protocol.name]['roles']], ['kvm02', 'kvm01', 'yaml_line'])
        self.assertEqual([client_name for client_name in server_protocol.parameters['protocols'][server_protocol.name]['roles']], ['kvm02', 'kvm01', 'yaml_line'])
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
        self.assertIn(MultinodeProtocol.name, [protocol.name for protocol in testshell.protocols])
        protocol_names = [protocol for protocol in testshell.protocols if protocol in testshell.parameters]
        protocols = [protocol for protocol in testshell.job.protocols if protocol.name in protocol_names]
        for protocol in protocols:
            protocol.debug_setup()
            if isinstance(protocol, MultinodeProtocol):
                self.assertIsNotNone(protocol.base_message)
            self.assertIs(True, protocol.valid)
        self.assertIsNone(self.coord.dataReceived({}))

    def test_signal_director(self):
        """
        Test the setup of the Multinode signal director
        """
        testshell = [action for action in self.server_job.pipeline.actions if isinstance(action, MultinodeTestAction)][0]
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
        self.coord.conn.response = "ack"
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
        client = TestMultinode.TestClient(self.coord, self.client_job.parameters)
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
        client(json.dumps({
            'request': 'lava_wait',
            'messageID': 'test'
        }))

    def test_client_send_keyvalue(self):
        self.coord.newGroup(2)
        self.coord.addClient("completing")
        self.coord.addClient("completed")
        client = TestMultinode.TestClient(self.coord, self.client_job.parameters)
        client.settings['target'] = 'completed'
        client(json.dumps({
            'request': 'lava_send',
            'messageID': 'test',
            'message': {
                'key': 'value'
            }
        }))
        self.coord.expectResponse('ack')
        client(json.dumps({
            'request': 'lava_wait',
            'messageID': 'test'
        }))


class TestProtocol(unittest.TestCase):  # pylint: disable=too-many-public-methods

    coord = None

    def setUp(self):
        """
        Unable to test actually sending messages - need a genuine group with clients and roles
        """
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
        self.protocol = TestProtocol.FakeProtocol(self.coord, parameters)

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

        def recv(self, _):
            self.coord._waitResponse()

    class FakeProtocol(MultinodeProtocol):

        def __init__(self, fake_coordinator, parameters):
            super(TestProtocol.FakeProtocol, self).__init__(parameters)
            self.name = "fake-multinode"
            self.sock = TestProtocol.FakeClient(fake_coordinator)
            self.debug_setup()

        def _connect(self, delay):
            return True

        def __call__(self, *args, **kwargs):
            super(TestProtocol.FakeProtocol, self).__call__(*args, **kwargs)

    def test_fake_protocol(self):
        self.protocol._connect(1)

    def test_empty_data(self):
        with self.assertRaises(TestError):
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
            self.protocol(json.dumps(msg))

    def test_fail_aggregation(self):
        """
        test that the refactored protocol fails to implement bundle aggregation
        """
        msg = {
            'request': 'aggregate'
        }
        json.loads(json.dumps(msg))
        with self.assertRaises(NotImplementedError):
            self.protocol(json.dumps(msg))

    def test_unsupported_request(self):
        msg = {
            'request': 'unsupported',
            'port': 3,
            'blocksize': 8,
            'messageID': 7
        }
        json.loads(json.dumps(msg))
        with self.assertRaises(TestError):
            self.protocol(json.dumps(msg))

    def test_lava_send_fail(self):
        msg = {
            'request': 'lava_send',
            'port': 3,
            'blocksize': 8,
            'messageID': 'test-id'
        }
        json.loads(json.dumps(msg))
        with self.assertRaises(TestError):
            self.protocol(json.dumps(msg))
