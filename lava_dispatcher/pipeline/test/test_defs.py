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
import unittest
from lava_dispatcher.pipeline.power import FinalizeAction
from lava_dispatcher.pipeline.actions.test.shell import TestShellRetry
from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.testdef import (
    TestDefinitionAction,
    GitRepoAction,
    TestOverlayAction,
    TestInstallAction,
    TestRunnerAction,
)
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction


# pylint: disable=duplicate-code


# Test the loading of test definitions within the deploy stage


class TestDefinitionHandlers(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionHandlers, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm.yaml')

    def test_testdef(self):
        testdef = overlay = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, DeployAction):
                overlay = action.pipeline.children[action.pipeline][3]
                testdef = overlay.internal_pipeline.actions[1]
        self.assertEqual(len(overlay.internal_pipeline.actions), 3)
        self.assertIsInstance(testdef, TestDefinitionAction)
        testdef.validate()
        if not testdef.valid:
            # python3 compatible
            print(testdef.errors)  # pylint: disable=superfluous-parens
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
#        self.assertIsNotNone(testdef.job.device['hostname'])

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
            'lava-add-sources',
            'lava-background-process-start',
            'lava-background-process-stop'
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

        self.assertItemsEqual(check_list, script_list)
        self.assertEqual(overlay.xmod, stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH)


class TestDefinitionSimple(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionSimple, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-notest.yaml')

    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_job_without_tests(self):
        deploy = boot = finalize = None
        self.job.pipeline.validate_actions()
        for action in self.job.pipeline.actions:
            self.assertNotIsInstance(action, TestDefinitionAction)
            self.assertNotIsInstance(action, OverlayAction)
            deploy = self.job.pipeline.actions[0]
            boot = self.job.pipeline.actions[1]
            finalize = self.job.pipeline.actions[2]
        self.assertIsInstance(deploy, DeployAction)
        self.assertIsInstance(boot, BootAction)
        self.assertIsInstance(finalize, FinalizeAction)
        self.assertEqual(len(self.job.pipeline.actions), 3)  # deploy, boot, finalize
        apply_overlay = deploy.pipeline.children[deploy.pipeline][4]


class TestDefinitionParams(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionParams, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-params.yaml')

    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_job_without_tests(self):
        deploy = boot = finalize = overlay = test = None
        self.job.pipeline.validate_actions()
        for action in self.job.pipeline.actions:
            self.assertNotIsInstance(action, TestDefinitionAction)
            self.assertNotIsInstance(action, OverlayAction)
            deploy = self.job.pipeline.actions[0]
            boot = self.job.pipeline.actions[1]
            finalize = self.job.pipeline.actions[3]
            overlay = deploy.internal_pipeline.actions[3]
        self.assertIsInstance(overlay, OverlayAction)
        testdef = overlay.internal_pipeline.actions[1]
        self.assertIsInstance(testdef, TestDefinitionAction)
        test = testdef.internal_pipeline.actions[1]
        install = testdef.internal_pipeline.actions[2]
        runsh = testdef.internal_pipeline.actions[3]
        self.assertIsInstance(deploy, DeployAction)
        self.assertIsInstance(boot, BootAction)
        self.assertIsInstance(finalize, FinalizeAction)
        self.assertEqual(len(self.job.pipeline.actions), 4)  # deploy, boot, test, finalize
        self.assertNotIn('test_params', testdef.parameters)
        self.assertIsInstance(install, TestInstallAction)
        self.assertIsInstance(runsh, TestRunnerAction)
        self.assertIsNot(list(install.parameters.items()), [])
        testdef = {'params': {'VARIABLE_NAME_1': 'value_1', 'VARIABLE_NAME_2': 'value_2'}}
        content = test.handle_parameters(testdef)
        self.assertEqual(
            content,
            [
                '###default parameters from yaml###\n', "VARIABLE_NAME_1='value_1'\n", "VARIABLE_NAME_2='value_2'\n",
                '######\n', '###test parameters from json###\n', "VARIABLE_NAME_1='eth2'\n",
                "VARIABLE_NAME_2='wlan0'\n", '######\n'
            ]
        )


class TestDefinitionRepeat(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionRepeat, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-multi.yaml")

    def test_multiple_tests(self):
        deploy = []
        boot = []
        shell = []
        finalize = []
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                deploy.append(action)
            elif isinstance(action, BootAction):
                boot.append(action)
            elif isinstance(action, TestShellRetry):
                shell.append(action)
            elif isinstance(action, FinalizeAction):
                finalize.append(action)
            else:
                self.fail(action.name)
        self.assertEqual(len(deploy), 1)
        self.assertEqual(len(boot), 2)
        self.assertEqual(len(shell), 2)
        self.assertEqual(len(finalize), 1)
