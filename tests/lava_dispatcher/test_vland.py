# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import os
import socket
from unittest.mock import patch

from lava_common.exceptions import JobError
from lava_dispatcher.actions.deploy.overlay import VlandOverlayAction
from lava_dispatcher.actions.deploy.tftp import TftpAction
from lava_dispatcher.connection import Protocol
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from lava_dispatcher.protocols.vland import VlandProtocol
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestVland(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job(
            "bbb-01",
            "sample_jobs/bbb-group-vland-alpha.yaml",
            validate=False,
        )

    def test_file_structure(self):
        self.assertIn("protocols", self.job.parameters)
        self.assertTrue(VlandProtocol.accepts(self.job.parameters))
        level_tuple = Protocol.select_all(self.job.parameters)
        self.assertEqual(len(level_tuple), 2)
        self.assertEqual(
            VlandProtocol,
            [item[0] for item in sorted(level_tuple, key=lambda data: data[1])][1],
        )
        vprotocol = VlandProtocol(self.job.parameters, self.job.job_id)
        self.assertIn("arbit", vprotocol.base_group)
        self.assertNotIn("group", vprotocol.base_group)
        vprotocol.set_up()
        self.assertIn("port", vprotocol.settings)
        self.assertIn("poll_delay", vprotocol.settings)
        self.assertIn("vland_hostname", vprotocol.settings)
        self.assertEqual(
            vprotocol.base_message,
            {
                "port": vprotocol.settings["port"],
                "poll_delay": vprotocol.settings["poll_delay"],
                "host": vprotocol.settings["vland_hostname"],
                "client_name": socket.gethostname(),
            },
        )
        for name in vprotocol.names:
            vlan = vprotocol.params[name]
            self.assertIn("tags", vlan)

    def test_device(self):
        device = self.job.device
        self.assertIsNotNone(device)
        self.assertIn("eth0", device["parameters"]["interfaces"])
        self.assertIn("eth1", device["parameters"]["interfaces"])
        self.assertIn("sysfs", device["parameters"]["interfaces"]["eth0"])
        self.assertIn("mac", device["parameters"]["interfaces"]["eth0"])
        self.assertIn("switch", device["parameters"]["interfaces"]["eth0"])
        self.assertIn("port", device["parameters"]["interfaces"]["eth0"])
        self.assertIn("tags", device["parameters"]["interfaces"]["eth0"])
        self.assertIn("sysfs", device["parameters"]["interfaces"]["eth1"])
        self.assertIn("mac", device["parameters"]["interfaces"]["eth1"])
        self.assertIn("switch", device["parameters"]["interfaces"]["eth1"])
        self.assertIn("port", device["parameters"]["interfaces"]["eth1"])
        self.assertIn("tags", device["parameters"]["interfaces"]["eth1"])
        self.assertIsInstance(device["parameters"]["interfaces"]["eth1"]["tags"], list)
        self.assertIsNone(device["parameters"]["interfaces"]["eth0"]["tags"])
        csv_list = []
        for interface in device["parameters"]["interfaces"]:
            csv_list.extend(
                [
                    device["parameters"]["interfaces"][interface]["sysfs"],
                    device["parameters"]["interfaces"][interface]["mac"],
                    interface,
                ]
            )
        self.assertEqual(
            set(csv_list),
            {
                "/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1",
                "00:24:d7:9b:c0:8c",
                "eth1",
                "/sys/devices/pci0000:00/0000:00:19.0/net/eth0",
                "f0:de:f1:46:8c:21",
                "eth0",
            },
        )
        tag_list = []
        for interface in device["parameters"]["interfaces"]:
            if interface == "eth0":
                continue
            for tag in device["parameters"]["interfaces"][interface]["tags"]:
                tag_list.extend([interface, tag])
        self.assertEqual(set(tag_list), {"RJ45", "100M", "eth1", "10M"})

    def test_configure(self):
        self.assertIn("protocols", self.job.parameters)
        self.assertTrue(VlandProtocol.accepts(self.job.parameters))
        vprotocol = VlandProtocol(self.job.parameters, self.job.job_id)
        vprotocol.set_up()

        ret = vprotocol.configure(self.job.device, self.job)
        if not ret:
            print(vprotocol.errors)
        self.assertTrue(ret)
        nodes = {}
        for name in vprotocol.names:
            vlan = vprotocol.params[name]
            # self.assertNotIn('tags', vlan)
            uid = " ".join([vlan["switch"], str(vlan["port"])])
            nodes[uid] = name
        self.assertEqual(len(nodes.keys()), len(vprotocol.names))
        self.assertIn("vlan_one", vprotocol.names)
        self.assertNotIn("vlan_two", vprotocol.names)
        self.assertIn("switch", vprotocol.params["vlan_one"])
        self.assertIn("port", vprotocol.params["vlan_one"])
        self.assertIsNotNone(vprotocol.multinode_protocol)

        bbb2 = self.job.device
        bbb2["parameters"]["interfaces"]["eth0"]["switch"] = "192.168.0.2"
        bbb2["parameters"]["interfaces"]["eth0"]["port"] = "6"
        bbb2["parameters"]["interfaces"]["eth1"]["switch"] = "192.168.0.2"
        bbb2["parameters"]["interfaces"]["eth1"]["port"] = "4"
        self.assertEqual(
            vprotocol.params,
            {
                "vlan_one": {
                    "switch": "192.168.0.2",
                    "iface": "eth1",
                    "port": 7,
                    "tags": ["100M", "RJ45", "10M"],
                }
            },
        )
        # already configured the vland protocol in the same job
        self.assertTrue(vprotocol.configure(bbb2, self.job))
        self.assertEqual(
            vprotocol.params,
            {
                "vlan_one": {
                    "switch": "192.168.0.2",
                    "iface": "eth1",
                    "port": 7,
                    "tags": ["100M", "RJ45", "10M"],
                }
            },
        )
        self.assertTrue(vprotocol.valid)
        self.assertEqual(
            vprotocol.names, {"vlan_one": f"{self.job.job_id[-8:]}vlanone"}
        )

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_job(self, which_mock):
        self.assertIn("protocols", self.job.parameters)
        self.assertIn(VlandProtocol.name, self.job.parameters["protocols"])

        description_ref = self.pipeline_reference(
            "bbb-group-vland-alpha.yaml", job=self.job
        )
        self.assertEqual(description_ref, self.job.pipeline.describe())
        self.job.validate()
        self.assertNotEqual(
            [],
            [
                protocol.name
                for protocol in self.job.protocols
                if protocol.name == MultinodeProtocol.name
            ],
        )
        ret = {
            "message": {"kvm01": {"vlan_name": "name", "vlan_tag": 6}},
            "response": "ack",
        }
        self.assertEqual(
            ("name", 6),
            (ret["message"]["kvm01"]["vlan_name"], ret["message"]["kvm01"]["vlan_tag"]),
        )
        self.assertIn("protocols", self.job.parameters)
        self.assertIn(VlandProtocol.name, self.job.parameters["protocols"])
        self.assertIn(MultinodeProtocol.name, self.job.parameters["protocols"])
        vprotocol = [
            vprotocol
            for vprotocol in self.job.protocols
            if vprotocol.name == VlandProtocol.name
        ][0]
        self.assertTrue(vprotocol.valid)
        self.assertEqual(
            vprotocol.names, {"vlan_one": f"{self.job.job_id[-8:]}vlanone"}
        )
        self.assertFalse(vprotocol.check_timeout(120, {"request": "no call"}))
        self.assertRaises(JobError, vprotocol.check_timeout, 60, "deploy_vlans")
        self.assertRaises(
            JobError, vprotocol.check_timeout, 60, {"request": "deploy_vlans"}
        )
        self.assertTrue(vprotocol.check_timeout(120, {"request": "deploy_vlans"}))
        for vlan_name in self.job.parameters["protocols"][VlandProtocol.name]:
            self.assertIn(vlan_name, vprotocol.params)
            self.assertIn("switch", vprotocol.params[vlan_name])
            self.assertIn("port", vprotocol.params[vlan_name])
            self.assertIn("iface", vprotocol.params[vlan_name])
        params = self.job.parameters["protocols"][vprotocol.name]
        names = []
        for key, _ in params.items():
            names.append(",".join([key, vprotocol.params[key]["iface"]]))
        # this device only has one interface with interface tags
        self.assertEqual(names, ["vlan_one,eth1"])

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_vland_overlay(self, which_mock):
        for vlan_key, _ in self.job.parameters["protocols"][VlandProtocol.name].items():
            self.job.parameters["protocols"][VlandProtocol.name][vlan_key] = {
                "tags": []
            }
        # removed tags from original job to simulate job where any interface
        # tags will be acceptable
        self.assertEqual(
            self.job.parameters["protocols"][VlandProtocol.name],
            {"vlan_one": {"tags": []}},
        )
        self.job.validate()

        tftp_deploy = self.job.pipeline.find_action(TftpAction)
        vland = tftp_deploy.pipeline.find_action(VlandOverlayAction)
        self.assertTrue(os.path.exists(vland.lava_vland_test_dir))
        vland_files = os.listdir(vland.lava_vland_test_dir)
        self.assertIn("lava-vland-names", vland_files)
        self.assertIn("lava-vland-tags", vland_files)
        self.assertIn("lava-vland-self", vland_files)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_job_no_tags(self, which_mock):
        for vlan_key, _ in self.job.parameters["protocols"][VlandProtocol.name].items():
            self.job.parameters["protocols"][VlandProtocol.name][vlan_key] = {
                "tags": []
            }
        # removed tags from original job to simulate job where any interface
        # tags will be acceptable
        self.assertEqual(
            self.job.parameters["protocols"][VlandProtocol.name],
            {"vlan_one": {"tags": []}},
        )
        self.job.validate()
        vprotocol = [
            vprotocol
            for vprotocol in self.job.protocols
            if vprotocol.name == VlandProtocol.name
        ][0]
        self.assertTrue(vprotocol.valid)
        self.assertEqual(
            vprotocol.names, {"vlan_one": f"{self.job.job_id[-8:]}vlanone"}
        )
        self.assertFalse(vprotocol.check_timeout(120, {"request": "no call"}))
        self.assertRaises(JobError, vprotocol.check_timeout, 60, "deploy_vlans")
        self.assertRaises(
            JobError, vprotocol.check_timeout, 60, {"request": "deploy_vlans"}
        )
        self.assertTrue(vprotocol.check_timeout(120, {"request": "deploy_vlans"}))
        for vlan_name in self.job.parameters["protocols"][VlandProtocol.name]:
            self.assertIn(vlan_name, vprotocol.params)
            self.assertIn("switch", vprotocol.params[vlan_name])
            self.assertIn("port", vprotocol.params[vlan_name])

    def test_job_bad_tags(self):
        for vlan_key, _ in self.job.parameters["protocols"][VlandProtocol.name].items():
            self.job.parameters["protocols"][VlandProtocol.name][vlan_key] = {
                "tags": ["spurious"]
            }
        # replaced tags from original job to simulate job
        # where an unsupported tag is specified
        self.assertEqual(
            self.job.parameters["protocols"][VlandProtocol.name],
            {"vlan_one": {"tags": ["spurious"]}},
        )
        self.assertRaises(JobError, self.job.validate)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_primary_interface(self, which_mock):
        for interface in self.job.device["parameters"]["interfaces"]:
            # jinja2 processing of tags: [] results in tags:
            if self.job.device["parameters"]["interfaces"][interface]["tags"] == []:
                self.job.device["parameters"]["interfaces"][interface]["tags"] = None

        tftp_deploy = self.job.pipeline.find_action(TftpAction)
        vland_overlay = tftp_deploy.pipeline.find_action(VlandOverlayAction)
        vland_overlay.validate()
        self.job.validate()
