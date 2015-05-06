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
import unittest
from lava_dispatcher.pipeline.actions.boot.qemu import BootQEMUImageAction
from lava_dispatcher.pipeline.actions.test.shell import TestShellRetry
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.test.test_basic import Factory, pipeline_reference
from lava_dispatcher.pipeline.actions.deploy.testdef import get_deployment_testdefs


class TestRepeatBootTest(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """
    Test repeat counts with nested test stanzas
    """
    def setUp(self):
        super(TestRepeatBootTest, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-repeat.yaml', mkdtemp())

    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_basic_structure(self):
        self.assertIsNotNone(self.job)
        self.job.validate()
        self.assertEqual([], self.job.pipeline.errors)
        description_ref = pipeline_reference('kvm-repeat.yaml')
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

    def test_deploy_norepeat(self):
        deploy = [deploy for deploy in self.job.parameters['actions'] if 'deploy' in deploy][0]['deploy']
        self.assertNotIn('repeat', deploy)

    def test_repeat_yaml(self):
        self.assertIn(['repeat'], [actions.keys() for actions in self.job.parameters['actions']])
        self.assertIn('repeat', self.job.parameters['actions'][1])
        repeat_block = self.job.parameters['actions'][1]['repeat']
        self.assertIn('count', repeat_block)
        actions = [action for action in repeat_block if 'count' not in action]
        self.assertIn('boot', repeat_block['actions'][0])
        self.assertIn('test', repeat_block['actions'][1])
        self.assertIn('boot', repeat_block['actions'][2])
        self.assertIn('test', repeat_block['actions'][3])
        self.assertEqual(len(actions), 4)

    def test_nested_structure(self):
        self.assertIn(['repeat'], [actions.keys() for actions in self.job.parameters['actions']])
        # pull out the repeated actions and analyse those
        actions = [retries for retries in self.job.pipeline.actions if retries.valid]
        self.assertIsInstance(actions[1], BootQEMUImageAction)
        self.assertIsInstance(actions[2], TestShellRetry)
        self.assertIsInstance(actions[4], TestShellRetry)
        self.assertEqual(actions[1].max_retries, 1)
        self.assertEqual(actions[2].max_retries, 3)
        self.assertEqual(actions[3].max_retries, 2)
        self.assertIn('repeat-count', actions[2].parameters)
        self.assertGreater(actions[6].parameters['repeat-count'], actions[2].parameters['repeat-count'])
        self.assertGreater(actions[9].parameters['repeat-count'], actions[6].parameters['repeat-count'])
        self.assertGreater(actions[20].parameters['repeat-count'], actions[16].parameters['repeat-count'])
        self.assertLess(25, [action.level for action in actions if 'repeat' in action.parameters][0])
        self.assertNotIn('repeat', actions[2].parameters)

    def test_single_repeat(self):
        self.assertIn(['boot'], [actions.keys() for actions in self.job.parameters['actions']])
        repeat_actions = [action for action in self.job.pipeline.actions if isinstance(action, BootQEMUImageAction)]
        boot = repeat_actions[-1]
        self.assertIn('repeat', boot.parameters)
        self.assertNotIn('repeat-count', boot.parameters)
        repeat_yaml = [actions for actions in self.job.parameters['actions'] if 'boot' in actions.keys()][0]['boot']
        self.assertIn('repeat', repeat_yaml)
        self.assertEqual(repeat_yaml['repeat'], 4)
        self.assertEqual(repeat_yaml['repeat'], boot.max_retries)
        self.assertEqual(repeat_yaml['repeat'], self.job.pipeline.actions[25].parameters['repeat'])
        self.assertNotIn('repeat-count', self.job.pipeline.actions[25].parameters)

    def test_test_definitions(self):
        if not self.job.parameters:
            self.skipTest("Missing job parameters")
        test_dict = get_deployment_testdefs(self.job.parameters)
        names = []
        # first deployment
        for testdefs in test_dict[test_dict.keys()[0]]:
            for testdef in testdefs:
                names.append(testdef['name'])
        self.assertEqual(names, [
            'smoke-tests-repeating',
            'singlenode-advanced',
            'smoke-tests-end',
            'singlenode-intermediate',
        ])
        # second deployment
        names = []
        for testdefs in test_dict[test_dict.keys()[1]]:
            for testdef in testdefs:
                names.append(testdef['name'])
        self.assertEqual(names, [
            'smoke-tests-single',
            'singlenode-basic'
        ])

        deploy_list = [action for action in self.job.parameters['actions'] if 'deploy' in action]
        self.assertEqual(len(deploy_list), len(test_dict.keys()))
        test_list = [action['test']['definitions'] for action in self.job.parameters['actions'] if 'test' in action]
        repeat_list = [action['repeat'] for action in self.job.parameters['actions'] if 'repeat' in action]
        if repeat_list:
            test_list.extend([testdef['test']['definitions'] for testdef in repeat_list[0]['actions'] if 'test' in testdef])
