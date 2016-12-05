# Copyright (C) 2016 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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
import glob
import yaml
import unittest

from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.action import JobError
from lava_dispatcher.pipeline.test.test_basic import pipeline_reference
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.lxc import LxcCreateAction
from lava_dispatcher.pipeline.actions.boot.lxc import BootAction
from lava_dispatcher.pipeline.actions.deploy.testdef import identify_test_definitions
from lava_dispatcher.pipeline.actions.deploy.overlay import get_test_action_namespaces


class Factory(object):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_lxc_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__),
                                        '../devices/lxc-01.yaml'))
        lxc_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(lxc_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4577, None, None, None,
                               output_dir=output_dir)
        return job

    def create_bbb_lxc_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__),
                                        '../devices/bbb-01.yaml'))
        lxc_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(lxc_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4577, None, None, None,
                               output_dir=output_dir)
        return job


class TestLxcDeploy(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestLxcDeploy, self).setUp()
        factory = Factory()
        self.job = factory.create_lxc_job('sample_jobs/lxc.yaml', mkdtemp())

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = pipeline_reference('lxc.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

    @unittest.skipIf(infrastructure_error('lxc-create'),
                     'lxc-create not installed')
    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    @unittest.skipIf(infrastructure_error('lxc-create'),
                     'lxc-create not installed')
    def test_create(self):
        for action in self.job.pipeline.actions:
            if isinstance(action, LxcCreateAction):
                self.assertEqual(action.lxc_data['lxc_name'],
                                 'pipeline-lxc-test-4577')
                self.assertEqual(action.lxc_data['lxc_distribution'], 'debian')
                self.assertEqual(action.lxc_data['lxc_release'], 'sid')
                self.assertEqual(action.lxc_data['lxc_arch'], 'amd64')
                self.assertEqual(action.lxc_data['lxc_template'], 'debian')
                self.assertEqual(action.lxc_data['lxc_mirror'],
                                 'http://ftp.us.debian.org/debian/')
                self.assertEqual(action.lxc_data['lxc_security_mirror'],
                                 'http://mirror.csclub.uwaterloo.ca/debian-security/')

    @unittest.skipIf(infrastructure_error('lxc-start'),
                     'lxc-start not installed')
    def test_boot(self):
        for action in self.job.pipeline.actions:
            if isinstance(action, BootAction):
                # get the action & populate it
                self.assertEqual(action.parameters['method'], 'lxc')
                self.assertEqual(action.parameters['prompts'], ['root@(.*):/#'])

    def test_testdefinitions(self):
        for action in self.job.pipeline.actions:
            if action.name == 'test':
                # get the action & populate it
                self.assertEqual(len(action.parameters['definitions']), 2)


class TestLxcWithDevices(unittest.TestCase):

    def setUp(self):
        super(TestLxcWithDevices, self).setUp()
        factory = Factory()
        self.job = factory.create_bbb_lxc_job('sample_jobs/bbb-lxc.yaml', mkdtemp())

    def test_lxc_with_device(self):
        self.assertIsNotNone(self.job)
        # validate with two test actions, lxc and device
        self.job.validate()
        lxc_yaml = os.path.join(os.path.dirname(__file__), 'sample_jobs/bbb-lxc.yaml')
        with open(lxc_yaml) as sample_job_data:
            data = yaml.load(sample_job_data)
        lxc_deploy = [action for action in self.job.pipeline.actions if action.name == 'lxc-deploy'][0]
        overlay = [action for action in lxc_deploy.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        test_def = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        self.assertIsNotNone(test_def.level, test_def.test_list)
        runner = [action for action in test_def.internal_pipeline.actions if action.name == 'test-runscript-overlay'][0]
        self.assertIsNotNone(runner.testdef_levels)
        tftp_deploy = [action for action in self.job.pipeline.actions if action.name == 'tftp-deploy'][0]
        prepare = [action for action in tftp_deploy.internal_pipeline.actions if action.name == 'prepare-tftp-overlay'][0]
        overlay = [action for action in prepare.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        test_def = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        namespace = test_def.parameters.get('namespace', None)
        self.assertIsNotNone(namespace)
        test_actions = [action for action in self.job.parameters['actions'] if 'test' in action]
        for action in test_actions:
            if 'namespace' in action['test']:
                if action['test']['namespace'] == namespace:
                    self.assertEqual(action['test']['definitions'][0]['name'], 'smoke-tests-bbb')
        namespace_tests = [action['test']['definitions'] for action in test_actions
                           if 'namespace' in action['test'] and action['test']['namespace'] == namespace]
        self.assertEqual(len(namespace_tests), 1)
        self.assertEqual(len(test_actions), 2)
        self.assertEqual('smoke-tests-bbb', namespace_tests[0][0]['name'])
        self.assertEqual(
            'smoke-tests-bbb',
            identify_test_definitions(self.job.parameters, namespace)[0][0]['name'])
        print(get_test_action_namespaces(self.job.parameters))
        self.assertIsNotNone(test_def.level, test_def.test_list)
        runner = [action for action in test_def.internal_pipeline.actions if action.name == 'test-runscript-overlay'][0]
        self.assertIsNotNone(runner.testdef_levels)
        # remove the second test action
        data['actions'].pop()
        test_actions = [action for action in data['actions'] if 'test' in action]
        self.assertEqual(len(test_actions), 1)
        self.assertEqual(test_actions[0]['test']['namespace'], 'probe')
        parser = JobParser()
        device = NewDevice(os.path.join(os.path.dirname(__file__),
                                        '../devices/bbb-01.yaml'))
        job = parser.parse(yaml.dump(data), device, 4577, None, None, None,
                           output_dir=mkdtemp())
        job.validate()
        lxc_deploy = [action for action in self.job.pipeline.actions if action.name == 'lxc-deploy'][0]
        overlay = [action for action in lxc_deploy.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        test_def = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        self.assertIsNotNone(test_def.level, test_def.test_list)
        runner = [action for action in test_def.internal_pipeline.actions if action.name == 'test-runscript-overlay'][0]
        self.assertIsNotNone(runner.testdef_levels)
