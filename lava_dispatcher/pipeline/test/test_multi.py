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
from lava_dispatcher.pipeline.test.test_basic import StdoutTestCase
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.action import Pipeline, Timeout
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.test.test_uboot import UBootFactory
from lava_dispatcher.pipeline.test.utils import DummyLogger

# pylint: disable=too-many-public-methods,too-few-public-methods


class TestMultiDeploy(StdoutTestCase):

    def setUp(self):
        super(TestMultiDeploy, self).setUp()
        self.parameters = {}
        self.parsed_data = {  # fake parsed YAML
            'device_type': 'fake',
            'job_name': 'fake_job',
            'timeouts': {
                'job': {
                    'minutes': 2
                }
            },
            'priority': 'medium',
            'actions': [
                {
                    'deploy': {
                        'to': 'fake_to',
                        'example': 'nowhere'
                    }
                },
                {
                    'deploy': {
                        'to': 'destination',
                        'parameters': 'faked'
                    }
                },
                {
                    'deploy': {
                        'to': 'tftp',
                        'parameters': 'valid'
                    }
                }
            ]
        }

    class FakeDevice(NewDevice):

        def check_config(self, job):
            pass

        def __init__(self):
            filename = os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml')
            super(TestMultiDeploy.FakeDevice, self).__init__(filename)

    class TestDeploy(object):  # cannot be a subclass of Deployment without a full select function.
        def __init__(self, parent, parameters, job):
            super(TestMultiDeploy.TestDeploy, self).__init__()
            self.action = TestMultiDeploy.TestDeployAction()
            self.action.job = job
            self.action.section = 'internal'
            parent.add_action(self.action, parameters)

    class TestDeployAction(DeployAction):

        def __init__(self):
            super(TestMultiDeploy.TestDeployAction, self).__init__()
            self.name = "fake-deploy"
            self.summary = "fake deployment"
            self.description = "fake for tests only"

        def validate(self):
            super(TestMultiDeploy.TestDeployAction, self).validate()

        def run(self, connection, max_end_time, args=None):
            self.data[self.name] = self.parameters
            return connection  # no actual connection during this fake job

    class TestJob(Job):
        def __init__(self):
            super(TestMultiDeploy.TestJob, self).__init__(4122, 0, self.parameters)

    def test_multi_deploy(self):
        self.assertIsNotNone(self.parsed_data)
        job = Job(4212, self.parsed_data, None)
        job.timeout = Timeout("Job", Timeout.parse({'minutes': 2}))
        pipeline = Pipeline(job=job)
        device = TestMultiDeploy.FakeDevice()
        self.assertIsNotNone(device)
        job.device = device
        job.parameters['output_dir'] = mkdtemp()
        job.logger = DummyLogger()
        job.pipeline = pipeline
        counts = {}
        for action_data in self.parsed_data['actions']:
            for name in action_data:
                counts.setdefault(name, 1)
                parameters = action_data[name]
                test_deploy = TestMultiDeploy.TestDeploy(pipeline, parameters, job)
                self.assertEqual(
                    {},
                    test_deploy.action.data
                )
                counts[name] += 1
        # check that only one action has the example set
        self.assertEqual(
            ['nowhere'],
            [detail['deploy']['example'] for detail in self.parsed_data['actions'] if 'example' in detail['deploy']]
        )
        self.assertEqual(
            ['faked', 'valid'],
            [detail['deploy']['parameters'] for detail in self.parsed_data['actions'] if 'parameters' in detail['deploy']]
        )
        self.assertIsInstance(pipeline.actions[0], TestMultiDeploy.TestDeployAction)
        self.assertIsInstance(pipeline.actions[1], TestMultiDeploy.TestDeployAction)
        self.assertIsInstance(pipeline.actions[2], TestMultiDeploy.TestDeployAction)
        job.validate()
        self.assertEqual([], job.pipeline.errors)
        self.assertEqual(job.run(), 0)
        self.assertNotEqual(pipeline.actions[0].data, {'fake-deploy': pipeline.actions[0].parameters})
        self.assertEqual(pipeline.actions[1].data, {'fake-deploy': pipeline.actions[2].parameters})
        # check that values from previous DeployAction run actions have been cleared
        self.assertEqual(pipeline.actions[2].data, {'fake-deploy': pipeline.actions[2].parameters})


class TestMultiDefinition(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestMultiDefinition, self).setUp()
        self.device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/bbb-01.yaml'))
        bbb_yaml = os.path.join(os.path.dirname(__file__), 'sample_jobs/uboot-nfs.yaml')
        with open(bbb_yaml) as sample_job_data:
            self.job_data = yaml.load(sample_job_data)

    def test_multidefinition(self):
        block = [testblock['test'] for testblock in self.job_data['actions'] if 'test' in testblock][0]
        self.assertIn('definitions', block)
        block['definitions'][1] = block['definitions'][0]
        self.assertEqual(len(block['definitions']), 2)
        self.assertEqual(block['definitions'][1], block['definitions'][0])
        parser = JobParser()
        job = parser.parse(yaml.dump(self.job_data), self.device, 4212, None, "",
                           output_dir='/tmp/')
        self.assertIsNotNone(job)
        deploy = [action for action in job.pipeline.actions if action.name == 'tftp-deploy'][0]
        tftp = [action for action in deploy.internal_pipeline.actions if action.name == 'prepare-tftp-overlay'][0]
        overlay = [action for action in tftp.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        testdef = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        runscript = [action for action in testdef.internal_pipeline.actions if action.name == 'test-runscript-overlay'][0]
        testdef_index = runscript.get_namespace_data(action='test-definition', label='test-definition', key='testdef_index')
        self.assertEqual(len(block['definitions']), len(testdef_index))
        runscript.validate()
        self.assertIsNotNone(runscript.errors)
        self.assertIn('Test definition names need to be unique.', runscript.errors)


class TestMultiUBoot(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestMultiUBoot, self).setUp()
        factory = UBootFactory()
        self.job = factory.create_bbb_job('sample_jobs/uboot-multiple.yaml')
        self.assertIsNotNone(self.job)
        self.assertIsNone(self.job.validate())
        self.assertEqual(self.job.device['device_type'], 'beaglebone-black')

    def test_multi_uboot(self):
        self.assertIsNotNone(self.job)
        description_ref = self.pipeline_reference('uboot-multiple.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))
