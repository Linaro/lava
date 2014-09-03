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

from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.tests.helper import LavaDispatcherTestCase
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.testdef import TestDefinitionAction, GitRepoAction

# Test the loading of test definitions within the deploy stage


class TestDefinitionHandlers(LavaDispatcherTestCase):

    def setUp(self):
        super(TestDefinitionHandlers, self).setUp()
        factory = Factory()
        self.job = factory.create_job('sample_jobs/kvm.yaml', self.config_dir)

    def test_testdef(self):
        testdef = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, DeployAction):
                testdef = action.pipeline.children[action.pipeline][4]
        self.assertEqual(len(testdef.internal_pipeline.actions), 2)
        self.assertIsInstance(testdef, TestDefinitionAction)
        testdef.validate()
        self.assertTrue(testdef.valid)
        for repo_action in testdef.internal_pipeline.actions:
            self.assertIsInstance(repo_action, GitRepoAction)
            repo_action.validate()
            self.assertTrue(repo_action.valid)
            # FIXME: needs deployment_data to be visible during validation
            # self.assertNotEqual(repo_action.runner, None)
