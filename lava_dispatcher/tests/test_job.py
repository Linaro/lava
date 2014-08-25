# Copyright (C) 2014 Linaro Limited
#
# Author: Linaro Validation Team <linaro-dev@lists.linaro.org>
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
# along with this program; if not, see <http://www.gnu.org/licenses>.

import atexit
import sys
import os
import json
import uuid
import lava_dispatcher.config
from lava_dispatcher import utils
from shutil import rmtree
from tempfile import mkdtemp
from lava_dispatcher.device.qemu import QEMUTarget
from lava_dispatcher.device.dynamic_vm import DynamicVmTarget
from lava_dispatcher.context import LavaContext
from lava_dispatcher.actions import get_all_cmds

from lava_dispatcher.tests.helper import (
    LavaDispatcherTestCase,
    create_device_config,
    create_config,
)
from lava_dispatcher.job import (
    LavaTestJob,
    validate_job_data,
)

tmpdir = mkdtemp()
atexit.register(rmtree, tmpdir)


def get_config():
    config = lava_dispatcher.config.get_config()
    config.lava_image_tmpdir = os.path.join(tmpdir, 'images')
    if not os.path.exists(config.lava_image_tmpdir):
        utils.ensure_directory(config.lava_image_tmpdir)
    return config


class DispatcherFactory(object):

    def __init__(self):
        self.data = {
            'health_check': False,
            'timeout': 60,
            'job_name': 'dispatcher-factory-unit-test',
            'actions': [
                {
                    'command': 'dummy_deploy',
                    'parameters': {'target_type': 'ubuntu'}
                }
            ]
        }

    def create_qemu_target(self, name, extra_device_config={}):
        """
        create a device just for the test suite in /tmp
        :param name: hostname to check against the returned target
        :param extra_device_config: hash of device config values
        :return: a fake QEMU target using the specified hostname
        """
        fake_qemu = os.path.join(os.path.dirname(__file__), 'test-config', 'bin', 'fake-qemu')
        create_config('lava-dispatcher.conf', {
            'LAVA_SERVER_IP': '99.99.99.99',
        })
        extra_device_config.update({'qemu_binary': fake_qemu})
        device_config_data = {'device_type': 'qemu'}
        device_config_data.update(extra_device_config)
        device_config = create_device_config(name, device_config_data)

        dispatcher_config = get_config()
        self.data['target'] = name

        context = LavaContext(name, dispatcher_config, None, None, None)
        return QEMUTarget(context, device_config)

    def create_vm_target(self, name, extra_device_config={}):
        fake_qemu = os.path.join(os.path.dirname(__file__), 'test-config', 'bin', 'fake-qemu')
        create_config('lava-dispatcher.conf', {
            'LAVA_SERVER_IP': '99.99.99.99',
        })
        extra_device_config.update({'qemu_binary': fake_qemu})
        device_config_data = {'device_type': 'dynamic-vm'}
        device_config_data.update(extra_device_config)
        device_config = create_device_config(name, device_config_data)

        dispatcher_config = get_config()
        self.data['target'] = name

        context = LavaContext(name, dispatcher_config, None, None, None)
        return DynamicVmTarget(context, device_config)

    def singlenode_jobdata(self):
        """
        Create a JSON structure suitable for LavaTestJob
        using the currently configured data populated by
        the target already created.
        :return: string dump of the job data
        """
        return json.dumps(self.data)

    def multinode_jobdata(self, length):
        """
        Extends the job data for multinode job using a
        list of devices.
        """
        self.data['target_group'] = str(uuid.uuid4())
        self.data['group_size'] = length
        self.data['sub_id'] = ''
        self.data['role'] = 'test_role'
        return json.dumps(self.data)

    def vmhost_jobdata(self, group):
        """
        Extends a multinode job to vmhost
        """
        self.data['target_group'] = group
        self.data['group_size'] = 2
        self.data['sub_id'] = ''
        self.data['role'] = 'test_host'
        self.data['is_vmhost'] = True
        return json.dumps(self.data)

    def vmguest_jobdata(self, group):
        """
        Extends a multinode job to vmguest
        """
        self.data['target_group'] = group
        self.data['group_size'] = 2
        self.data['sub_id'] = ''
        self.data['role'] = 'test_guest'
        self.data['is_vmhost'] = False
        return json.dumps(self.data)


class TestLavaSingleNodeJob(LavaDispatcherTestCase):

    name = 'device01'

    def test_device_create(self):
        factory = DispatcherFactory()
        target = factory.create_qemu_target(self.name, {})
        self.assertTrue(target)

    def test_job_create_singlenode(self):
        """
        Test the creation of a LavaTestJob within the
        dispatcher to identify issues before the job has
        started to run.
        """
        factory = DispatcherFactory()
        target = factory.create_qemu_target(self.name, {})
        self.assertEqual(target.config.hostname, self.name)
        json_str = factory.singlenode_jobdata()
        self.assertNotEqual(json_str, None)
        jobdata = json.loads(json_str)
        self.assertEqual(jobdata['health_check'], False)
        validate_job_data(jobdata)
        # single node
        self.assertNotIn('target_group', jobdata)
        self.assertNotIn('is_vmhost', jobdata)
        job = LavaTestJob(json_str, sys.stderr, get_config(), None)
        self.assertEqual(job.target, target.config.hostname)
        self.assertIsNotNone(get_all_cmds())
        # FIXME: would be useful to not have the metadata population only accessible via LavaTestJob.run()
        job.run()
        self.assertEqual(job.context.test_data.metadata['target'], self.name)
        self.assertEqual(job.context.test_data.metadata['target.hostname'], self.name)
        self.assertNotIn('is_vmhost', job.context.test_data.metadata)
        self.assertNotIn('host_ip', job.context.test_data.metadata)
        self.assertNotIn('target_group', job.context.test_data.metadata)
        self.assertNotIn('vm_group', job.context.test_data.metadata)


class TestLavaMultiNodeJob(LavaDispatcherTestCase):

    device_names = [
        'device01',
        'device02'
    ]

    def test_device_create(self):
        factory = DispatcherFactory()
        for name in self.device_names:
            target = factory.create_qemu_target(name, {})
            self.assertTrue(target)

    def test_job_create_multinode(self):
        """
        Test the creation of a MultiNode LavaTestJob within
        the dispatcher to identify issues before the job has
        started to run and without needing to talk to the
        lava-coordinator.
        This job is only one part of a MultiNode job - it
        cannot be expected to run as-is.
        """
        factory = DispatcherFactory()
        for name in self.device_names:
            target = factory.create_qemu_target(name, {})
            json_str = factory.multinode_jobdata(len(self.device_names))
            self.assertEqual(target.config.hostname, name)
            self.assertNotEqual(json_str, None)
            jobdata = json.loads(json_str)
            self.assertEqual(jobdata['health_check'], False)
            validate_job_data(jobdata)
            # multi node
            self.assertIn('target_group', jobdata)
            self.assertNotIn('is_vmhost', jobdata)
            job = LavaTestJob(json_str, sys.stderr, get_config(), None)
            self.assertEqual(job.target, target.config.hostname)


class TestLavaVMGroupJob(LavaDispatcherTestCase):

    vm_name = "vm1-testjob"
    host = "device03"

    def test_vmdevice_create(self):
        factory = DispatcherFactory()
        vmdevice = factory.create_vm_target(self.vm_name, {})
        self.assertTrue(vmdevice)

    def test_job_create_vmgroup(self):
        factory = DispatcherFactory()
        vmhost = factory.create_qemu_target(self.host, {})
        self.assertEqual(vmhost.config.hostname, self.host)
        json_str = factory.multinode_jobdata(2)
        self.assertNotEqual(json_str, None)
        jobdata = json.loads(json_str)
        self.assertEqual(jobdata['health_check'], False)
        validate_job_data(jobdata)
        self.assertIn('target_group', jobdata)
        self.assertNotIn('is_vmhost', jobdata)

        json_str = factory.vmhost_jobdata(jobdata['target_group'])
        self.assertNotEqual(json_str, None)
        jobdata = json.loads(json_str)
        self.assertEqual(jobdata['health_check'], False)
        validate_job_data(jobdata)
        self.assertIn('target_group', jobdata)
        self.assertIn('is_vmhost', jobdata)
        self.assertTrue(jobdata['is_vmhost'])

        vmguest = factory.create_vm_target(self.vm_name, {})
        self.assertEqual(vmguest.config.hostname, self.vm_name)
        json_str = factory.vmguest_jobdata(jobdata['target_group'])
        self.assertNotEqual(json_str, None)
        jobdata = json.loads(json_str)
        self.assertEqual(jobdata['health_check'], False)
        validate_job_data(jobdata)
        self.assertIn('target_group', jobdata)
        self.assertIn('is_vmhost', jobdata)
        self.assertFalse(jobdata['is_vmhost'])
