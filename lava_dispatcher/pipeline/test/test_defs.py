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

import re
import os
import sys
import glob
import stat
import yaml
import pexpect
import unittest
from lava_dispatcher.pipeline.power import FinalizeAction
from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.action import InfrastructureError
from lava_dispatcher.pipeline.actions.test.shell import TestShellRetry, PatternFixup
from lava_dispatcher.pipeline.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.pipeline.test.test_uboot import UBootFactory
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.image import DeployImagesAction
from lava_dispatcher.pipeline.actions.deploy.testdef import (
    TestDefinitionAction,
    GitRepoAction,
    TestOverlayAction,
    TestInstallAction,
    TestRunnerAction,
)
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction
from lava_dispatcher.pipeline.actions.deploy.download import DownloaderAction
from lava_dispatcher.pipeline.utils.shell import infrastructure_error


# pylint: disable=duplicate-code
# Test the loading of test definitions within the deploy stage

def allow_missing_path(function, testcase, path):
    try:
        function()
    except InfrastructureError as exc:
        if not infrastructure_error(path):
            testcase.fail(exc)


def check_missing_path(testcase, exception, path):
    if isinstance(exception, InfrastructureError):
        if not infrastructure_error(path):
            testcase.fail(exception)


class TestDefinitionHandlers(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionHandlers, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm.yaml')
        with open(os.path.join(os.path.dirname(__file__), 'testdefs', 'params.yaml'), 'r') as params:
            self.testdef = yaml.safe_load(params)

    def test_testdef(self):
        testdef = overlay = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, DeployAction):
                overlay = action.pipeline.actions[3]
                testdef = overlay.internal_pipeline.actions[2]
        self.assertEqual(len(overlay.internal_pipeline.actions), 5)
        self.assertIsInstance(testdef, TestDefinitionAction)
        testdef.validate()
        self.assertEqual(testdef.run_levels,
                         {'smoke-tests': 0, 'singlenode-advanced': 1})
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
            # FIXME
            # if hasattr(repo_action, 'uuid'):
            #     repo_action.data['test'] = {repo_action.uuid: {}}
            #     repo_action.store_testdef(self.testdef, 'git', 'abcdef')
            #     self.assertEqual(
            #         repo_action.data['test'][repo_action.uuid]['testdef_pattern'],
            #         self.testdef['parse'])
            self.assertTrue(repo_action.valid)
            # FIXME: needs deployment_data to be visible during validation
            # self.assertNotEqual(repo_action.runner, None)
        self.assertIsNotNone(testdef.parameters['deployment_data']['lava_test_results_dir'])
#        self.assertIsNotNone(testdef.job.device['hostname'])

    def test_name(self):
        deploy = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        overlay = [action for action in deploy.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        testdef = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        testdef.validate()
        self.assertEqual([], testdef.errors)
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/kvm01.yaml'))
        kvm_yaml = os.path.join(os.path.dirname(__file__), 'sample_jobs/kvm.yaml')
        parser = JobParser()
        with open(kvm_yaml, 'r') as sample_job_data:
            content = yaml.load(sample_job_data)
        data = [block['test'] for block in content['actions'] if 'test' in block][0]
        definitions = [block for block in data['definitions'] if 'path' in block][0]
        definitions['name'] = 'smoke tests'
        job = parser.parse(yaml.dump(content), device, 4212, None, "",
                           output_dir='/tmp/')
        deploy = [action for action in job.pipeline.actions if action.name == 'deployimages'][0]
        overlay = [action for action in deploy.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        testdef = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        testdef.validate()
        self.assertNotEqual([], testdef.errors)
        self.assertIn('Invalid characters found in test definition name: smoke tests', job.pipeline.errors)

    def test_vcs_parameters(self):
        deploy = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        overlay = [action for action in deploy.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        testdef = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        git_repos = [action for action in testdef.internal_pipeline.actions if action.name == 'git-repo-action']
        for git_repo in git_repos:
            if git_repo.parameters['repository'] == 'http://git.linaro.org/lava-team/lava-functional-tests.git':
                self.assertIn('revision', git_repo.parameters)
            else:
                self.assertNotIn('revision', git_repo.parameters)

    def test_overlay(self):

        script_list = [
            'lava-test-case',
            'lava-add-keys',
            'lava-echo-ipv4',
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
            'lava-background-process-stop',
            'lava-test-set'
        ]

        overlay = None
        for action in self.job.pipeline.actions:
            if isinstance(action, DeployAction):
                for child in action.pipeline.actions:
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

        if sys.version_info[0] == 2:
            self.assertItemsEqual(check_list, script_list)
        elif sys.version_info[0] == 3:
            self.assertCountEqual(check_list, script_list)  # pylint: disable=no-member
        self.assertEqual(overlay.xmod, stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH)


class TestDefinitionSimple(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionSimple, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-notest.yaml')

    def test_job_without_tests(self):
        deploy = boot = finalize = None
        allow_missing_path(self.job.pipeline.validate_actions, self, 'qemu-system-x86_64')
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
        self.assertIsInstance(deploy.pipeline.actions[0], DownloaderAction)
        self.assertEqual(len(deploy.pipeline.actions), 1)  # deploy without test only needs DownloaderAction


class TestDefinitionParams(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestDefinitionParams, self).setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/kvm-params.yaml')

    def test_job_without_tests(self):
        boot = finalize = None
        allow_missing_path(self.job.pipeline.validate_actions, self, 'qemu-system-x86_64')
        deploy = [action for action in self.job.pipeline.actions if action.name == 'deployimages'][0]
        overlay = [action for action in deploy.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        testdef = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        for action in self.job.pipeline.actions:
            self.assertNotIsInstance(action, TestDefinitionAction)
            self.assertNotIsInstance(action, OverlayAction)
            boot = self.job.pipeline.actions[1]
            finalize = self.job.pipeline.actions[3]
        self.assertIsInstance(overlay, OverlayAction)
        self.assertIsInstance(testdef, TestDefinitionAction)
        test = testdef.internal_pipeline.actions[1]
        install = testdef.internal_pipeline.actions[2]
        runsh = testdef.internal_pipeline.actions[3]
        self.assertIsInstance(deploy, DeployImagesAction)
        self.assertIsInstance(boot, BootAction)
        self.assertIsInstance(finalize, FinalizeAction)
        self.assertEqual(len(self.job.pipeline.actions), 4)  # deploy, boot, test, finalize
        self.assertNotIn('test_params', testdef.parameters)
        self.assertIsInstance(install, TestInstallAction)
        self.assertIsInstance(runsh, TestRunnerAction)
        self.assertIsNot(list(install.parameters.items()), [])
        testdef = {'params': {'VARIABLE_NAME_1': 'value_1',
                              'VARIABLE_NAME_2': 'value_2'}}
        content = test.handle_parameters(testdef)
        self.assertEqual(
            set(content),
            {
                '###default parameters from test definition###\n',
                "VARIABLE_NAME_1='value_1'\n", "VARIABLE_NAME_2='value_2'\n",
                '######\n', '###test parameters from job submission###\n',
                "VARIABLE_NAME_1='eth2'\n", "VARIABLE_NAME_2='wlan0'\n",
                '######\n'
            }
        )
        testdef = {'parameters': {'VARIABLE_NAME_1': 'value_1',
                                  'VARIABLE_NAME_2': 'value_2'}}
        content = test.handle_parameters(testdef)
        self.assertEqual(
            set(content),
            {
                '###default parameters from test definition###\n',
                "VARIABLE_NAME_1='value_1'\n", "VARIABLE_NAME_2='value_2'\n",
                '######\n', '###test parameters from job submission###\n',
                "VARIABLE_NAME_1='eth2'\n", "VARIABLE_NAME_2='wlan0'\n",
                '######\n'
            }
        )


class TestDefinitionRepeat(StdoutTestCase):  # pylint: disable=too-many-public-methods

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


class TestSkipInstall(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestSkipInstall, self).setUp()
        factory = UBootFactory()
        self.job = factory.create_bbb_job("sample_jobs/bbb-skip-install.yaml")

    def test_skip_install_params(self):
        self.assertIsNotNone(self.job)
        deploy = [action for action in self.job.pipeline.actions if action.name == 'tftp-deploy'][0]
        prepare = [action for action in deploy.internal_pipeline.actions if action.name == 'prepare-tftp-overlay'][0]
        lava_apply = [action for action in prepare.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        testoverlay = [action for action in lava_apply.internal_pipeline.actions if action.name == 'test-definition'][0]
        testdefs = [action for action in testoverlay.internal_pipeline.actions if action.name == 'test-install-overlay']
        ubuntu_testdef = None
        single_testdef = None
        for testdef in testdefs:
            if testdef.parameters['path'] == 'ubuntu/smoke-tests-basic.yaml':
                ubuntu_testdef = testdef
            elif testdef.parameters['path'] == 'lava-test-shell/single-node/singlenode03.yaml':
                single_testdef = testdef
            else:
                self.fail('Unexpected test definition in sample job.')
        self.assertNotIn('skip_install', ubuntu_testdef.parameters)
        self.assertIn('skip_install', single_testdef.parameters)
        self.job.validate()
        self.assertEqual(
            single_testdef.skip_list,
            ['keys', 'sources', 'deps', 'steps', 'git-repos', 'all']
        )
        self.assertEqual(single_testdef.skip_options, ['deps'])


class TestDefinitions(StdoutTestCase):
    """
    For compatibility until the V1 code is removed and we can start
    cleaning up Lava Test Shell.
    Parsing patterns in the Test Shell Definition YAML are problematic,
    difficult to debug and rely on internal python syntax.
    The fixupdict is even more confusing for all concerned.
    """

    def setUp(self):
        super(TestDefinitions, self).setUp()
        self.testdef = os.path.join(os.path.dirname(__file__), 'testdefs', 'params.yaml')
        self.res_data = os.path.join(os.path.dirname(__file__), 'testdefs', 'result-data.txt')
        factory = UBootFactory()
        self.job = factory.create_bbb_job("sample_jobs/bbb-nfs-url.yaml")

    def test_pattern(self):
        self.assertTrue(os.path.exists(self.testdef))
        with open(self.testdef, 'r') as par:
            params = yaml.load(par)
        self.assertIn('parse', params.keys())
        line = 'test1a: pass'
        self.assertEqual(
            r'(?P<test_case_id>.*-*):\s+(?P<result>(pass|fail))',
            params['parse']['pattern'])
        match = re.search(params['parse']['pattern'], line)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(), line)
        self.assertEqual(match.group(1), 'test1a')
        self.assertEqual(match.group(2), 'pass')

    def test_v1_defaults(self):
        pattern = PatternFixup(testdef=None, count=0)
        # without a name from a testdef, the pattern is not valid.
        self.assertFalse(pattern.valid())
        with open(self.testdef, 'r') as par:
            params = yaml.load(par)
        pattern = PatternFixup(testdef=params, count=0)
        self.assertTrue(pattern.valid())

    def test_definition_lists(self):
        self.job.validate()
        tftp_deploy = [action for action in self.job.pipeline.actions if action.name == 'tftp-deploy'][0]
        prepare = [action for action in tftp_deploy.internal_pipeline.actions if action.name == 'prepare-tftp-overlay'][0]
        overlay = [action for action in prepare.internal_pipeline.actions if action.name == 'lava-overlay'][0]
        definition = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        definition = [action for action in overlay.internal_pipeline.actions if action.name == 'test-definition'][0]
        git_repos = [action for action in definition.internal_pipeline.actions if action.name == 'git-repo-action']
        self.assertIn('common', self.job.context)
        self.assertIn("test-definition", self.job.context['common'])
        self.assertIsNotNone(definition.get_namespace_data(action=definition.name, label='test-definition', key='testdef_index'))
        self.assertEqual(
            definition.get_namespace_data(action=definition.name, label='test-definition', key='testdef_index'),
            ['smoke-tests', 'singlenode-advanced']
        )
        self.assertEqual(
            git_repos[0].get_namespace_data(action='test-runscript-overlay', label='test-runscript-overlay', key='testdef_levels'),
            {
                '1.3.2.4.4': '0_smoke-tests',
                '1.3.2.4.8': '1_singlenode-advanced'
            }
        )
        self.assertEqual(
            {repo.uuid for repo in git_repos},
            {'4212_1.3.2.4.1', '4212_1.3.2.4.5'}
        )
        self.assertEqual(
            set(git_repos[0].get_namespace_data(action='test-runscript-overlay', label='test-runscript-overlay', key='testdef_levels').values()),
            {'1_singlenode-advanced', '0_smoke-tests'}
        )
        # fake up a run step
        with open(self.testdef, 'r') as par:
            params = yaml.load(par)
        self.assertEqual(
            r'(?P<test_case_id>.*-*):\s+(?P<result>(pass|fail))',
            params['parse']['pattern'])
        self.job.context.setdefault('test', {})
        for git_repo in git_repos:
            self.job.context['test'].setdefault(git_repo.uuid, {})
            self.job.context['test'][git_repo.uuid]['testdef_pattern'] = {'pattern': params['parse']['pattern']}
        self.assertEqual(
            self.job.context['test'],
            {
                '4212_1.3.2.4.5': {'testdef_pattern': {'pattern': '(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))'}},
                '4212_1.3.2.4.1': {'testdef_pattern': {'pattern': '(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))'}}}
        )
        testdef_index = self.job.context['common']['test-definition']['test-definition']['testdef_index']
        start_run = '0_smoke-tests'
        uuid_list = definition.get_namespace_data(action='repo-action', label='repo-action', key='uuid-list')
        self.assertIsNotNone(uuid_list)
        for key, value in enumerate(testdef_index):
            if start_run == "%s_%s" % (key, value):
                self.assertEqual('4212_1.3.2.4.1', uuid_list[key])
                self.assertEqual(
                    self.job.context['test'][uuid_list[key]]['testdef_pattern']['pattern'],
                    '(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))'
                )

    @unittest.skipIf(sys.version > '3', 'pexpect issues in python3')
    def test_defined_pattern(self):
        """
        For python3 support, need to resolve:
        TypeError: cannot use a bytes pattern on a string-like object
        TypeError: cannot use a string pattern on a bytes-like object
        whilst retaining re_pat as a compiled regular expression in the
        pexpect support.
        """
        data = """test1a: pass
test2a: fail
test3a: skip
\"test4a:\" \"unknown\"
        """
        with open(self.testdef, 'r') as par:
            params = yaml.load(par)
        pattern = params['parse']['pattern']
        re_pat = re.compile(pattern, re.M)
        match = re.search(re_pat, data)
        if match:
            self.assertEqual(match.groupdict(), {'test_case_id': 'test1a', 'result': 'pass'})
        child = pexpect.spawn('cat', [self.res_data])
        child.expect([re_pat, pexpect.EOF])
        self.assertEqual(child.after, b'test1a: pass')
        child.expect([re_pat, pexpect.EOF])
        self.assertEqual(child.after, b'test2a: fail')
        child.expect([re_pat, pexpect.EOF])
        self.assertEqual(child.after, pexpect.EOF)
