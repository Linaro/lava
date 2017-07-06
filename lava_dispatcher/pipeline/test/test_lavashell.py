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
import datetime
from lava_dispatcher.pipeline.action import (
    Action,
    InfrastructureError,
    Pipeline,
    JobError,
    LAVAError,
    Timeout
)
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.actions.deploy.testdef import get_test_action_namespaces
from lava_dispatcher.pipeline.test.utils import DummyLogger
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol
from lava_dispatcher.pipeline.protocols.vland import VlandProtocol
from lava_dispatcher.pipeline.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.pipeline.actions.test.shell import TestShellRetry, TestShellAction


# pylint: disable=duplicate-code,too-few-public-methods


class TestDefinitionHandlers(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionHandlers, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm.yaml')

    def test_testshell(self):
        testshell = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, TestShellRetry):
                testshell = action.pipeline.actions[0]
                break
        self.assertIsInstance(testshell, TestShellAction)
        self.assertTrue(testshell.valid)

        if 'timeout' in testshell.parameters:
            time_int = Timeout.parse(testshell.parameters['timeout'])
        else:
            time_int = Timeout.default_duration()
        self.assertEqual(
            datetime.timedelta(seconds=time_int).total_seconds(),
            testshell.timeout.duration
        )

    def test_missing_handler(self):
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/kvm01.yaml'))
        kvm_yaml = os.path.join(os.path.dirname(__file__), 'sample_jobs/kvm.yaml')
        parser = JobParser()
        with open(kvm_yaml) as sample_job_data:
            data = yaml.load(sample_job_data)
        data['actions'][2]['test']['definitions'][0]['from'] = 'unusable-handler'
        try:
            job = parser.parse(yaml.dump(data), device, 4212, None, "", output_dir='/tmp')
            job.logger = DummyLogger()
        except JobError:
            pass
        except Exception as exc:  # pylint: disable=broad-except
            self.fail(exc)
        else:
            self.fail('JobError not raised')

    def test_eventpatterns(self):
        testshell = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, TestShellRetry):
                testshell = action.pipeline.actions[0]
                break
        self.assertTrue(testshell.valid)
        self.assertFalse(testshell.check_patterns('exit', None, ''))
        self.assertRaises(InfrastructureError, testshell.check_patterns, 'eof', None, '')
        self.assertTrue(testshell.check_patterns('timeout', None, ''))


class X86Factory(Factory):

    def create_x86_job(self, filename, device, output_dir='/tmp/'):  # pylint: disable=no-self-use
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        parser = JobParser()
        try:
            with open(kvm_yaml) as sample_job_data:
                job = parser.parse(sample_job_data, device, 4212, None, "",
                                   output_dir=output_dir)
            job.logger = DummyLogger()
        except LAVAError as exc:
            print(exc)
            # some deployments listed in basics.yaml are not implemented yet
            return None
        return job


class TestMultiNodeOverlay(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestMultiNodeOverlay, self).setUp()
        factory = X86Factory()
        lng1 = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/lng-generator-01.yaml'))
        lng2 = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/lng-generator-02.yaml'))
        self.server_job = factory.create_x86_job('sample_jobs/test_action-1.yaml', lng1)
        self.client_job = factory.create_x86_job('sample_jobs/test_action-2.yaml', lng2)

    def test_action_namespaces(self):
        self.assertIsNotNone(self.server_job)
        self.assertIsNotNone(self.client_job)
        deploy_server = [action for action in self.server_job.pipeline.actions if action.name == 'tftp-deploy'][0]
        self.assertIn(MultinodeProtocol.name, deploy_server.parameters.keys())
        self.assertIn(VlandProtocol.name, deploy_server.parameters.keys())
        self.assertEqual(['common'], get_test_action_namespaces(self.server_job.parameters))
        namespace = self.server_job.parameters.get('namespace', None)
        self.assertIsNone(namespace)
        namespace = self.client_job.parameters.get('namespace', None)
        self.assertIsNone(namespace)
        deploy_client = [action for action in self.client_job.pipeline.actions if action.name == 'tftp-deploy'][0]
        self.assertIn(MultinodeProtocol.name, deploy_client.parameters.keys())
        self.assertIn(VlandProtocol.name, deploy_client.parameters.keys())
        key_list = []
        for block in self.client_job.parameters['actions']:
            key_list.extend(block.keys())
        self.assertEqual(key_list, ['deploy', 'boot', 'test'])  # order is important
        self.assertEqual(['common'], get_test_action_namespaces(self.client_job.parameters))
        key_list = []
        for block in self.server_job.parameters['actions']:
            key_list.extend(block.keys())
        self.assertEqual(key_list, ['deploy', 'boot', 'test'])  # order is important


class TestShellResults(StdoutTestCase):   # pylint: disable=too-many-public-methods

    class FakeJob(Job):

        def __init__(self, parameters):
            super(TestShellResults.FakeJob, self).__init__(parameters)

    class FakeDeploy(object):
        """
        Derived from object, *not* Deployment as this confuses python -m unittest discover
        - leads to the FakeDeploy being called instead.
        """
        def __init__(self, parent):
            self.__parameters__ = {}
            self.pipeline = parent
            self.job = parent.job
            self.action = TestShellResults.FakeAction()

    class FakePipeline(Pipeline):

        def __init__(self, parent=None, job=None):
            super(TestShellResults.FakePipeline, self).__init__(parent, job)

    class FakeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        def __init__(self):
            super(TestShellResults.FakeAction, self).__init__()
            self.count = 1
            self.name = "fake-action"
            self.summary = "fake action for unit tests"
            self.description = "fake, do not use outside unit tests"

        def run(self, connection, max_end_time, args=None):
            self.count += 1
            raise JobError("fake error")
