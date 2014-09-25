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
import glob
import stat
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.tests.helper import LavaDispatcherTestCase
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.testdef import (
    TestDefinitionAction,
    GitRepoAction,
    TestOverlayAction
)
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction


# Test the loading of test definitions within the deploy stage


class TestDefinitionHandlers(LavaDispatcherTestCase):  # pylint: disable=too-many-public-methods

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
        self.assertEqual(len(testdef.internal_pipeline.actions), 8)
        self.assertIsInstance(testdef, TestDefinitionAction)
        testdef.validate()
        self.assertTrue(testdef.valid)
        for repo_action in testdef.internal_pipeline.actions:
            if isinstance(repo_action, GitRepoAction):
                self.assertEqual(repo_action.default_pattern,
                                 "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))")
                self.assertEqual(repo_action.default_fixupdict,
                                 {'PASS': 'pass', 'FAIL': 'fail', 'SKIP': 'skip', 'UNKNOWN': 'unknown'})
                self.assertTrue(hasattr(repo_action, 'accepts'))
                self.assertTrue(hasattr(repo_action, 'priority'))
            elif isinstance(repo_action, TestOverlayAction):
                self.assertTrue(hasattr(repo_action, 'test_uuid'))
                self.assertFalse(hasattr(repo_action, 'accepts'))
                self.assertFalse(hasattr(repo_action, 'priority'))
            else:
                self.fail("%s does not match GitRepoAction or TestOverlayAction" % type(repo_action))
            repo_action.validate()
            self.assertTrue(repo_action.valid)
            # FIXME: needs deployment_data to be visible during validation
            # self.assertNotEqual(repo_action.runner, None)
        self.assertIsNotNone(testdef.parameters['deployment_data']['lava_test_results_dir'])
#        self.assertIsNotNone(testdef.job.device.parameters['hostname'])

    def test_overlay(self):

        script_list = [
            'lava-test-case',
            'lava-add-keys',
            'lava-install-packages',
            'lava-test-case-attach',
            'lava-os-build',
            'lava-test-shell',
            'lava-test-run-attach',
            'lava-test-case-metadata',
            'lava-installed-packages',
            'lava-test-runner',
            'lava-vm-groups-setup-host',  # FIXME: no need for this in the standard set
            'lava-add-sources',
            'lava-add-keys',
            'lava-install-packages',
            'lava-os-build',
            'lava-installed-packages',
            'lava-add-sources'
        ]

        overlay = None
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                for child in action.pipeline.children[action.pipeline]:
                    if isinstance(child, OverlayAction):
                        overlay = child
                        break
        self.assertIsInstance(overlay, OverlayAction)
        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(overlay.lava_test_dir, 'lava-*'))
        distro_support_dir = '%s/distro/%s' % (overlay.lava_test_dir, 'debian')
        for script in glob.glob(os.path.join(distro_support_dir, 'lava-*')):
            scripts_to_copy.append(script)
        check_list = [os.path.basename(scr) for scr in scripts_to_copy]
        self.assertEqual(check_list, script_list)

        self.assertEqual(overlay.xmod, stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH)
