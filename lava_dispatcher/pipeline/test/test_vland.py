# Copyright (C) 2015 Linaro Limited
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
import socket
import unittest
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.action import JobError
from lava_dispatcher.pipeline.connection import Protocol
from lava_dispatcher.pipeline.protocols.vland import VlandProtocol
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol
from lava_dispatcher.pipeline.test.test_basic import pipeline_reference

# pylint: disable=superfluous-parens


class TestVland(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestVland, self).setUp()
        self.filename = os.path.join(os.path.dirname(__file__), 'sample_jobs/bbb-group-vland-alpha.yaml')
        self.beta_filename = os.path.join(os.path.dirname(__file__), 'sample_jobs/bbb-group-vland-beta.yaml')
        self.device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        self.job_id = "100"

    def test_file_structure(self):
        with open(self.filename) as yaml_data:
            alpha_data = yaml.load(yaml_data)
        self.assertIn('protocols', alpha_data)
        self.assertTrue(VlandProtocol.accepts(alpha_data))
        level_tuple = Protocol.select_all(alpha_data)
        self.assertEqual(len(level_tuple), 2)
        self.assertEqual(
            VlandProtocol,
            [
                item[0] for item in sorted(level_tuple, key=lambda data: data[1])
            ][1]
        )
        vprotocol = VlandProtocol(alpha_data, self.job_id)
        self.assertIn(
            'arbit',
            vprotocol.base_group,
        )
        self.assertNotIn(
            'group',
            vprotocol.base_group,
        )
        vprotocol.set_up()
        self.assertIn('port', vprotocol.settings)
        self.assertIn('poll_delay', vprotocol.settings)
        self.assertIn('vland_hostname', vprotocol.settings)
        self.assertEqual(
            vprotocol.base_message,
            {
                "port": vprotocol.settings['port'],
                "poll_delay": vprotocol.settings["poll_delay"],
                "host": vprotocol.settings['vland_hostname'],
                "client_name": socket.gethostname(),
            }
        )
        for name in vprotocol.names:
            vlan = vprotocol.params[name]
            self.assertIn('tags', vlan)

    def test_device(self):
        self.assertIsNotNone(self.device)
        self.assertIn('eth0', self.device['parameters']['interfaces'])
        self.assertIn('eth1', self.device['parameters']['interfaces'])
        self.assertIn('sysfs', self.device['parameters']['interfaces']['eth0'])
        self.assertIn('mac', self.device['parameters']['interfaces']['eth0'])
        self.assertIn('switch', self.device['parameters']['interfaces']['eth0'])
        self.assertIn('port', self.device['parameters']['interfaces']['eth0'])
        self.assertIn('tags', self.device['parameters']['interfaces']['eth0'])
        self.assertIn('sysfs', self.device['parameters']['interfaces']['eth1'])
        self.assertIn('mac', self.device['parameters']['interfaces']['eth1'])
        self.assertIn('switch', self.device['parameters']['interfaces']['eth1'])
        self.assertIn('port', self.device['parameters']['interfaces']['eth1'])
        self.assertIn('tags', self.device['parameters']['interfaces']['eth1'])
        self.assertIsInstance(self.device['parameters']['interfaces']['eth1']['tags'], list)
        self.assertIsInstance(self.device['parameters']['interfaces']['eth0']['tags'], list)
        csv_list = []
        for interface in self.device['parameters']['interfaces']:
            csv_list.extend(
                [
                    self.device['parameters']['interfaces'][interface]['sysfs'],
                    self.device['parameters']['interfaces'][interface]['mac'],
                    interface
                ]
            )
        self.assertEqual(
            set(csv_list),
            {
                '/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1', '00:24:d7:9b:c0:8c', 'eth1',
                '/sys/devices/pci0000:00/0000:00:19.0/net/eth0', 'f0:de:f1:46:8c:21', 'eth0'
            }
        )
        tag_list = []
        for interface in self.device['parameters']['interfaces']:
            for tag in self.device['parameters']['interfaces'][interface]['tags']:
                tag_list.extend([interface, tag])
        self.assertEqual(set(tag_list), {'RJ45', '100M', 'eth1', '10M'})

    def test_configure(self):
        with open(self.filename) as yaml_data:
            alpha_data = yaml.load(yaml_data)
        self.assertIn('protocols', alpha_data)
        self.assertTrue(VlandProtocol.accepts(alpha_data))
        vprotocol = VlandProtocol(alpha_data, self.job_id)
        vprotocol.set_up()
        with open(self.filename) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, self.device, 4212, None, None, None,
                               output_dir='/tmp/')
        ret = vprotocol.configure(self.device, job)
        if not ret:
            print(vprotocol.errors)
        self.assertTrue(ret)
        nodes = {}
        for name in vprotocol.names:
            vlan = vprotocol.params[name]
            # self.assertNotIn('tags', vlan)
            uid = ' '.join([vlan['switch'], str(vlan['port'])])
            nodes[uid] = name
        self.assertEqual(len(nodes.keys()), len(vprotocol.names))
        self.assertIn('vlan_one', vprotocol.names)
        self.assertNotIn('vlan_two', vprotocol.names)
        self.assertIn('switch', vprotocol.params['vlan_one'])
        self.assertIn('port', vprotocol.params['vlan_one'])
        self.assertIsNotNone(vprotocol.multinode_protocol)

        bbb2 = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        bbb2['hostname'] = 'bbb2'
        bbb2['parameters']['interfaces']['eth0']['switch'] = '192.168.0.2'
        bbb2['parameters']['interfaces']['eth0']['port'] = '6'
        bbb2['parameters']['interfaces']['eth1']['switch'] = '192.168.0.2'
        bbb2['parameters']['interfaces']['eth1']['port'] = '4'
        self.assertEqual(
            vprotocol.params, {
                'vlan_one': {'switch': '192.168.0.1', 'iface': 'eth1', 'port': 7, 'tags': ['100M', 'RJ45', '10M']}
            }
        )
        # already configured the vland protocol in the same job
        self.assertTrue(vprotocol.configure(bbb2, job))
        self.assertEqual(
            vprotocol.params, {
                'vlan_one': {
                    'switch': '192.168.0.1', 'iface': 'eth1', 'port': 7, 'tags': ['100M', 'RJ45', '10M']}
            }
        )
        self.assertTrue(vprotocol.valid)
        self.assertEqual(vprotocol.names, {'vlan_one': '4212vlanone'})

    def test_job(self):
        with open(self.filename) as yaml_data:
            alpha_data = yaml.load(yaml_data)
        self.assertIn('protocols', alpha_data)
        self.assertIn(VlandProtocol.name, alpha_data['protocols'])
        with open(self.filename) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, self.device, 4212, None, None, None,
                               output_dir='/tmp/')
        description_ref = pipeline_reference('bbb-group-vland-alpha.yaml')
        self.assertEqual(description_ref, job.pipeline.describe(False))
        job.validate()
        self.assertNotEqual([], [protocol.name for protocol in job.protocols if protocol.name == MultinodeProtocol.name])
        ret = {"message": {"kvm01": {"vlan_name": "name", "vlan_tag": 6}}, "response": "ack"}
        self.assertEqual(('name', 6), (ret['message']['kvm01']['vlan_name'], ret['message']['kvm01']['vlan_tag'],))
        self.assertIn('protocols', job.parameters)
        self.assertIn(VlandProtocol.name, job.parameters['protocols'])
        self.assertIn(MultinodeProtocol.name, job.parameters['protocols'])
        vprotocol = [vprotocol for vprotocol in job.protocols if vprotocol.name == VlandProtocol.name][0]
        self.assertTrue(vprotocol.valid)
        self.assertEqual(vprotocol.names, {'vlan_one': '4212vlanone'})
        self.assertFalse(vprotocol.check_timeout(120, {'request': 'no call'}))
        self.assertRaises(JobError, vprotocol.check_timeout, 60, 'deploy_vlans')
        self.assertRaises(JobError, vprotocol.check_timeout, 60, {'request': 'deploy_vlans'})
        self.assertTrue(vprotocol.check_timeout(120, {'request': 'deploy_vlans'}))
        for vlan_name in job.parameters['protocols'][VlandProtocol.name]:
            if vlan_name == 'yaml_line':
                continue
            self.assertIn(vlan_name, vprotocol.params)
            self.assertIn('switch', vprotocol.params[vlan_name])
            self.assertIn('port', vprotocol.params[vlan_name])
            self.assertIn('iface', vprotocol.params[vlan_name])
        params = job.parameters['protocols'][vprotocol.name]
        names = []
        for key, _ in params.items():
            if key == 'yaml_line':
                continue
            names.append(",".join([key, vprotocol.params[key]['iface']]))
        # this device only has one interface with interface tags
        self.assertEqual(names, ['vlan_one,eth1'])

    def test_job_no_tags(self):
        with open(self.filename) as yaml_data:
            alpha_data = yaml.load(yaml_data)
        for vlan_key, _ in alpha_data['protocols'][VlandProtocol.name].items():
            alpha_data['protocols'][VlandProtocol.name][vlan_key] = {'tags': []}
        # removed tags from original job to simulate job where any interface tags will be acceptable
        self.assertEqual(
            alpha_data['protocols'][VlandProtocol.name],
            {'vlan_one': {'tags': []}}
        )
        parser = JobParser()
        job = parser.parse(yaml.dump(alpha_data), self.device, 4212, None, None, None, output_dir='/tmp/')
        job.validate()
        vprotocol = [vprotocol for vprotocol in job.protocols if vprotocol.name == VlandProtocol.name][0]
        self.assertTrue(vprotocol.valid)
        self.assertEqual(vprotocol.names, {'vlan_one': '4212vlanone'})
        self.assertFalse(vprotocol.check_timeout(120, {'request': 'no call'}))
        self.assertRaises(JobError, vprotocol.check_timeout, 60, 'deploy_vlans')
        self.assertRaises(JobError, vprotocol.check_timeout, 60, {'request': 'deploy_vlans'})
        self.assertTrue(vprotocol.check_timeout(120, {'request': 'deploy_vlans'}))
        for vlan_name in job.parameters['protocols'][VlandProtocol.name]:
            if vlan_name == 'yaml_line':
                continue
            self.assertIn(vlan_name, vprotocol.params)
            self.assertIn('switch', vprotocol.params[vlan_name])
            self.assertIn('port', vprotocol.params[vlan_name])

    def test_job_bad_tags(self):
        with open(self.filename) as yaml_data:
            alpha_data = yaml.load(yaml_data)
        for vlan_key, _ in alpha_data['protocols'][VlandProtocol.name].items():
            alpha_data['protocols'][VlandProtocol.name][vlan_key] = {'tags': ['spurious']}
        # replaced tags from original job to simulate job where an unsupported tag is specified
        self.assertEqual(
            alpha_data['protocols'][VlandProtocol.name],
            {'vlan_one': {'tags': ['spurious']}}
        )
        parser = JobParser()
        job = parser.parse(yaml.dump(alpha_data), self.device, 4212, None, None, None, output_dir='/tmp/')
        self.assertRaises(JobError, job.validate)

    def test_primary_interface(self):
        with open(self.filename) as yaml_data:
            alpha_data = yaml.load(yaml_data)
        for interface in self.device['parameters']['interfaces']:
            # jinja2 processing of tags: [] results in tags:
            if self.device['parameters']['interfaces'][interface]['tags'] == []:
                self.device['parameters']['interfaces'][interface]['tags'] = None
        parser = JobParser()
        job = parser.parse(yaml.dump(alpha_data), self.device, 4212, None, None, None, output_dir='/tmp/')
        deploy = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        prepare = [action for action in deploy.internal_pipeline.actions if action.name == 'prepare-tftp-overlay'][0]
        overlay = [action for action in prepare.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        vland_overlay = [action for action in overlay.internal_pipeline.actions if action.name == 'lava-vland-overlay'][0]
        vland_overlay.validate()
        job.validate()

    # pylint: disable=protected-access
    def demo(self):
        with open(self.filename) as yaml_data:
            alpha_data = yaml.load(yaml_data)
        vprotocol = VlandProtocol(alpha_data, 422)
        vprotocol.settings = vprotocol.read_settings()
        self.assertIn('port', vprotocol.settings)
        self.assertIn('poll_delay', vprotocol.settings)
        self.assertIn('vland_hostname', vprotocol.settings)
        vprotocol.base_message = {
            "port": vprotocol.settings['port'],
            "poll_delay": vprotocol.settings["poll_delay"],
            "host": vprotocol.settings['vland_hostname'],
            "client_name": socket.gethostname(),
        }
        count = 0
        print("\nTesting vland live using connections.")
        for friendly_name in vprotocol.parameters['protocols'][vprotocol.name]:
            print("Processing VLAN: %s" % friendly_name)
            vprotocol.names[friendly_name] = vprotocol.base_group + '%02d' % count
            count += 1
            vprotocol.vlans[friendly_name], tag = vprotocol._create_vlan(friendly_name)
            print("[%s] Created vlan with id %s" % (friendly_name, vprotocol.vlans[friendly_name]))
            print("[%s] tag: %s" % (friendly_name, tag))
            for hostname in vprotocol.parameters['protocols'][vprotocol.name][friendly_name]:
                params = vprotocol.parameters['protocols'][vprotocol.name][friendly_name][hostname]
                print("[%s] to use switch %s and port %s" % (friendly_name, params['switch'], params['port']))
                self.assertIn('switch', params)
                self.assertIn('port', params)
                self.assertIsNotNone(params['switch'])
                self.assertIsNotNone(params['port'])
                switch_id = vprotocol._lookup_switch_id(params['switch'])
                self.assertIsNotNone(switch_id)
                print("[%s] Using switch ID %s" % (friendly_name, switch_id))
                port_id = vprotocol._lookup_port_id(switch_id, params['port'])
                print("%s Looked up port ID %s for %s" % (friendly_name, port_id, params['port']))
                vprotocol._set_port_onto_vlan(vprotocol.vlans[friendly_name], port_id)
                vprotocol.ports.append(port_id)
        print("Finalising - tearing down vlans")
        vprotocol.finalise_protocol()
