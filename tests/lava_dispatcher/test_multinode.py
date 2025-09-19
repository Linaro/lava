# Copyright (C) 2014-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
from json import dumps as json_dumps
from json import loads as json_loads
from random import randint
from socket import socket
from typing import Any
from unittest.mock import Mock

from lava_common.exceptions import InfrastructureError, JobError
from lava_common.timeout import Timeout
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.actions.boot.qemu import BootQemuRetry, CallQemuAction
from lava_dispatcher.actions.deploy.image import DeployImagesAction
from lava_dispatcher.actions.deploy.overlay import MultinodeOverlayAction
from lava_dispatcher.actions.test.multinode import MultinodeTestAction
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.lava_dispatcher.test_defs import allow_missing_path
from tests.utils import DummyLogger


class TestMultinode(LavaDispatcherTestCase):
    def setUp(self):
        """
        Attempt to setup a valid group with clients and test the protocol
        """
        super().setUp()
        factory = Factory()
        self.client_job = factory.create_kvm_job(
            "sample_jobs/kvm-multinode-client.yaml"
        )
        self.server_job = factory.create_kvm_job(
            "sample_jobs/kvm-multinode-server.yaml"
        )
        self.client_job.logger = DummyLogger()
        self.server_job.logger = DummyLogger()
        self.job_id = "100"

    def test_multinode_jobs(self):
        self.assertIsNotNone(self.client_job)
        self.assertIsNotNone(self.server_job)
        allow_missing_path(self.client_job.validate, self, "qemu-system-x86_64")
        allow_missing_path(self.server_job.validate, self, "qemu-system-x86_64")
        self.assertEqual(self.client_job.pipeline.errors, [])
        self.assertEqual(self.server_job.pipeline.errors, [])

    def test_protocol(self):
        self.assertEqual(
            ["lava-multinode"],
            [protocol.name for protocol in self.client_job.protocols],
        )
        client_protocol = [protocol for protocol in self.client_job.protocols][0]
        server_protocol = [protocol for protocol in self.server_job.protocols][0]
        self.assertEqual(client_protocol.name, server_protocol.name)
        self.assertIn(
            "target_group",
            client_protocol.parameters["protocols"][client_protocol.name].keys(),
        )
        self.assertIn("actions", self.client_job.parameters.keys())
        try:
            self.client_job.validate()
            self.server_job.validate()
        except InfrastructureError:
            pass
        self.assertIn(
            "role", client_protocol.parameters["protocols"][client_protocol.name].keys()
        )
        self.assertEqual([], self.client_job.pipeline.errors)
        self.assertEqual([], self.server_job.pipeline.errors)

    def test_settings(self):
        """
        If lava-coordinator is configured, test that the config can be loaded.
        """
        filename = "/etc/lava-coordinator/lava-coordinator.conf"
        if not os.path.exists(filename):
            filename = os.path.join(
                os.path.dirname(__file__), "../../etc/lava-coordinator.conf"
            )
        self.assertTrue(os.path.exists(filename))
        client_protocol = [protocol for protocol in self.client_job.protocols][0]
        settings = client_protocol.read_settings(filename)
        self.assertIn("blocksize", settings)
        self.assertIn("coordinator_hostname", settings)

    def test_multinode_pipeline(self):
        client_multinode = self.client_job.pipeline.find_action(MultinodeOverlayAction)
        self.assertIsNotNone(client_multinode)
        client_multinode.validate()
        self.assertEqual(client_multinode.role, "client")

        server_multinode = self.server_job.pipeline.find_action(MultinodeOverlayAction)
        self.assertIsNotNone(server_multinode)
        server_multinode.validate()
        self.assertEqual(server_multinode.role, "server")

        client_protocol = [protocol for protocol in self.client_job.protocols][0]
        server_protocol = [protocol for protocol in self.server_job.protocols][0]
        self.assertEqual(
            {
                client_name
                for client_name in client_protocol.parameters["protocols"][
                    client_protocol.name
                ]["roles"]
            },
            {"kvm02", "kvm01"},
        )
        self.assertEqual(
            {
                client_name
                for client_name in server_protocol.parameters["protocols"][
                    server_protocol.name
                ]["roles"]
            },
            {"kvm02", "kvm01"},
        )
        self.assertEqual(
            client_protocol.parameters["protocols"][client_protocol.name]["roles"][
                "kvm01"
            ],
            "client",
        )
        self.assertEqual(
            client_protocol.parameters["protocols"][client_protocol.name]["roles"][
                "kvm02"
            ],
            "server",
        )
        self.assertEqual(
            server_protocol.parameters["protocols"][client_protocol.name]["roles"][
                "kvm01"
            ],
            "client",
        )
        self.assertEqual(
            server_protocol.parameters["protocols"][client_protocol.name]["roles"][
                "kvm02"
            ],
            "server",
        )
        self.assertEqual(
            client_multinode.lava_multi_node_cache_file,
            "/tmp/lava_multi_node_cache.txt",  # nosec - replicating DUT behaviour.
        )
        self.assertIsNotNone(client_multinode.lava_multi_node_test_dir)
        self.assertTrue(os.path.exists(client_multinode.lava_multi_node_test_dir))

    def test_multinode_test_protocol(self):
        """
        Test multinode protocol message handling against TestCoordinator
        """
        testshell = self.server_job.pipeline.find_action(MultinodeTestAction)
        testshell.validate()
        self.assertEqual(30, testshell.character_delay)
        self.assertEqual(30, testshell.signal_director.character_delay)
        self.assertIsNotNone(testshell.protocols)
        self.assertEqual(testshell.timeout.duration, 180)
        self.assertIn(
            MultinodeProtocol.name, [protocol.name for protocol in testshell.protocols]
        )
        protocol_names = [
            protocol.name
            for protocol in testshell.protocols
            if protocol in testshell.protocols
        ]
        self.assertNotEqual(protocol_names, [])
        protocols = [
            protocol
            for protocol in testshell.job.protocols
            if protocol.name in protocol_names
        ]
        self.assertNotEqual(protocols, [])
        multinode_dict = {"multinode": "<LAVA_MULTI_NODE> <LAVA_(\\S+) ([^>]+)>"}
        self.assertEqual(multinode_dict, testshell.multinode_dict)
        self.assertIn("multinode", testshell.patterns)
        self.assertEqual(testshell.patterns["multinode"], multinode_dict["multinode"])
        testshell._reset_patterns()
        self.assertIn("multinode", testshell.patterns)
        self.assertEqual(testshell.patterns["multinode"], multinode_dict["multinode"])
        for protocol in protocols:
            protocol.debug_setup()
            if isinstance(protocol, MultinodeProtocol):
                self.assertIsNotNone(protocol.base_message)
            else:
                self.fail("Unexpected protocol")
            self.assertIs(True, protocol.valid)

    def test_multinode_description(self):
        self.assertIsNotNone(self.client_job)
        allow_missing_path(self.client_job.validate, self, "qemu-system-x86_64")
        # check that the description can be re-loaded as valid YAML
        data = self.client_job.pipeline.describe()
        data_str = yaml_safe_dump(data)
        yaml_safe_load(data_str)

    def test_multinode_timeout(self):
        """
        Test the protocol timeout is assigned to the action
        """
        testshell = self.client_job.pipeline.find_action(MultinodeTestAction)
        testshell.validate()
        self.assertIn(30, [p.poll_timeout.duration for p in testshell.protocols])
        self.assertIn("minutes", testshell.parameters["lava-multinode"]["timeout"])
        self.assertEqual(
            10, testshell.parameters["lava-multinode"]["timeout"]["minutes"]
        )
        self.assertEqual(
            testshell.signal_director.base_message["timeout"],
            Timeout.parse(testshell.parameters["lava-multinode"]["timeout"]),
        )

    def test_signal_director(self):
        """
        Test the setup of the Multinode signal director
        """
        testshell = self.server_job.pipeline.find_action(MultinodeTestAction)
        testshell.validate()
        self.assertEqual(180, testshell.timeout.duration)
        self.assertIsNotNone(testshell.signal_director)
        self.assertIsNotNone(testshell.signal_director.protocol)
        self.assertIs(type(testshell.protocols), list)
        self.assertIsNot(type(testshell.signal_director.protocol), list)
        self.assertIsInstance(testshell.signal_director.protocol, MultinodeProtocol)

    def test_protocol_action(self):
        deploy = self.client_job.pipeline.find_action(DeployImagesAction)
        self.assertIn("protocols", deploy.parameters)
        client_calls = {}
        for action in deploy.pipeline.actions:
            if "protocols" in action.parameters:
                for protocol in action.job.protocols:
                    for params in action.parameters["protocols"][protocol.name]:
                        api_calls = [
                            params
                            for name in params
                            if name == "action" and params[name] == action.name
                        ]
                        for call in api_calls:
                            client_calls.update(call)

    def test_protocol_variables(self):
        retry = self.client_job.pipeline.find_action(BootQemuRetry)
        qemu_boot = retry.pipeline.find_action(CallQemuAction)
        self.assertIn("protocols", qemu_boot.parameters)
        self.assertIn(MultinodeProtocol.name, qemu_boot.parameters["protocols"])
        mn_protocol = [
            protocol
            for protocol in qemu_boot.job.protocols
            if protocol.name == MultinodeProtocol.name
        ][0]
        params = qemu_boot.parameters["protocols"][MultinodeProtocol.name]
        # params is a list - multiple actions can exist
        self.assertEqual(
            params,
            [
                {
                    "action": "execute-qemu",
                    "message": {"ipv4": "$IPV4"},
                    "messageID": "test",
                    "request": "lava-wait",
                }
            ],
        )
        client_calls = {}
        for action in retry.pipeline.actions:
            if "protocols" in action.parameters:
                for protocol in action.job.protocols:
                    for params in action.parameters["protocols"][protocol.name]:
                        api_calls = [
                            params
                            for name in params
                            if name == "action" and params[name] == action.name
                        ]
                        for call in api_calls:
                            action.set_namespace_data(
                                action=protocol.name,
                                label=protocol.name,
                                key=action.name,
                                value=call,
                            )
                            client_calls.update(call)

        # now pretend that another job has called lava-send with the same messageID,
        # this would be the reply to the lava-wait
        reply = {mn_protocol.job_id: {"ipaddr": "10.15.206.133"}}
        cparams = {
            "timeout": {"minutes": 5},
            "messageID": "ipv4",
            "action": "prepare-scp-overlay",
            "message": {"ipaddr": "$ipaddr"},
            "request": "lava-wait",
        }
        self.assertEqual(
            ("ipv4", {"ipaddr": "10.15.206.133"}), mn_protocol.collate(reply, cparams)
        )
        reply = {
            "message": {mn_protocol.job_id: {"ipv4": "192.168.0.2"}},
            "response": "ack",
        }
        self.assertEqual(
            ("test", {"ipv4": "192.168.0.2"}), mn_protocol.collate(reply, params)
        )

        replaceables = [
            key for key, value in params["message"].items() if value.startswith("$")
        ]
        for item in replaceables:
            target_list = [val for val in reply["message"].items()]
            data = target_list[0][1]
            params["message"][item] = data[item]

        self.assertEqual(
            client_calls,
            {
                "action": "execute-qemu",
                "message": {"ipv4": reply["message"][mn_protocol.job_id]["ipv4"]},
                "request": "lava-wait",
                "messageID": "test",
            },
        )


class TestMultinodeProtocol(LavaDispatcherTestCase):
    def init_protocol(
        self, params: dict[str, Any] = {}, recv_object: dict[str, Any] = {}
    ) -> MultinodeProtocol:
        class MultinodeProtocolSocketMock(MultinodeProtocol):
            def _connect(self, delay):
                self.sock = Mock(spec=socket)
                return True

            def _recv_message(self):
                return json_dumps(recv_object)

        base_params = {
            "target_group": "test",
            "role": "test",
        }
        base_params.update(params)
        new_protocol = MultinodeProtocolSocketMock(
            {"protocols": {MultinodeProtocolSocketMock.name: base_params}},
            str(randint(0, 2**31)),
        )
        new_protocol.debug_setup()
        new_protocol._connect(0)
        return new_protocol

    def test_multinode_protocol_init(self) -> None:
        self.init_protocol()

    def test_multinode_protocol_init_equal_roles(self) -> None:
        protocol = self.init_protocol(
            {"request": "lava-start", "expect_role": "test", "role": "test"}
        )
        self.assertFalse(protocol.valid)

    def test_multinode_protocol_called_without_data(self) -> None:
        protocol = self.init_protocol()
        with self.assertRaisesRegex(JobError, "No data to be sent over protocol"):
            protocol({})

    def test_multinode_protocol_send_empty_message(self) -> None:
        test_message = {"response": "success"}
        protocol = self.init_protocol(recv_object=test_message)
        self.assertEqual(
            json_loads(protocol.request_send("test_id")),
            test_message,
        )
