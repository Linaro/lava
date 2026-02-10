# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import glob
import os
import re
import shutil
import stat
import tempfile
import unittest
from unittest.mock import call, patch

import pexpect

from lava_common.exceptions import InfrastructureError
from lava_common.yaml import yaml_safe_load
from lava_dispatcher.actions.deploy.apply_overlay import ApplyOverlayTftp
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.fastboot import FastbootAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.actions.deploy.testdef import (
    GitRepoAction,
    RepoAction,
    TestDefinitionAction,
    TestInstallAction,
    TestOverlayAction,
    TestRunnerAction,
)
from lava_dispatcher.actions.test.shell import PatternFixup
from lava_dispatcher.power import FinalizeAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.lava_dispatcher.test_uboot import UBootFactory
from tests.utils import infrastructure_error, infrastructure_error_multi_paths

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


class TestDefinitionHandlers(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job("qemu01", "sample_jobs/kvm.yaml")
        with open(
            os.path.join(os.path.dirname(__file__), "testdefs", "params.yaml")
        ) as params:
            self.testdef = yaml_safe_load(params)

    def test_testdef(self):
        testdef = overlay = None
        action = self.job.pipeline.actions[0]
        overlay = action.pipeline.actions[0]
        testdef = overlay.pipeline.actions[2]
        self.assertEqual(len(overlay.pipeline.actions), 4)
        self.assertIsInstance(testdef, TestDefinitionAction)
        testdef.validate()
        self.assertEqual(
            testdef.run_levels, {"smoke-tests": 0, "singlenode-advanced": 0}
        )
        if not testdef.valid:
            print(testdef.errors)
        self.assertTrue(testdef.valid)
        for repo_action in testdef.pipeline.actions:
            if isinstance(repo_action, GitRepoAction):
                self.assertTrue(hasattr(repo_action, "accepts"))
                self.assertTrue(hasattr(repo_action, "priority"))
            elif isinstance(repo_action, TestOverlayAction):
                self.assertTrue(hasattr(repo_action, "test_uuid"))
                self.assertFalse(hasattr(repo_action, "accepts"))
                self.assertFalse(hasattr(repo_action, "priority"))
            else:
                self.fail(
                    "%s does not match GitRepoAction or TestOverlayAction"
                    % type(repo_action)
                )
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
        self.assertIsNotNone(
            testdef.parameters["deployment_data"]["lava_test_results_dir"]
        )

    def test_name(self):
        testdef = self.job.pipeline.find_action(TestDefinitionAction)
        testdef.validate()
        self.assertEqual([], testdef.errors)
        job = self.factory.create_job("kvm01", "sample_jobs/kvm.yaml")
        testdef = job.pipeline.find_action(TestDefinitionAction)
        testdef.test_list[0][0]["name"] = "smoke tests"  # Introduce match error
        testdef.validate()
        self.assertNotEqual([], testdef.errors)
        self.assertIn(
            "Invalid characters found in test definition name: smoke tests",
            job.pipeline.errors,
        )

    def test_vcs_parameters(self):
        git_repos = self.job.pipeline.find_all_actions(GitRepoAction)
        for git_repo in git_repos:
            if (
                git_repo.parameters["repository"]
                == "http://git.linaro.org/lava-team/lava-functional-tests.git"
            ):
                self.assertIn("revision", git_repo.parameters)
                self.assertIn("branch", git_repo.parameters)
            else:
                self.assertNotIn("revision", git_repo.parameters)
                self.assertNotIn("branch", git_repo.parameters)

    def test_overlay(self):
        script_list = [
            "lava-add-keys",
            "lava-add-sources",
            "lava-background-process-start",
            "lava-background-process-stop",
            "lava-echo-ipv4",
            "lava-install-packages",
            "lava-installed-packages",
            "lava-os-build",
            "lava-probe-channel",
            "lava-probe-ip",
            "lava-target-ip",
            "lava-target-mac",
            "lava-target-storage",
            "lava-test-case",
            "lava-test-event",
            "lava-test-feedback",
            "lava-test-reference",
            "lava-test-runner",
            "lava-test-set",
            "lava-test-shell",
            "lava-test-raise",
            "lava-common-functions",
        ]

        overlay = self.job.pipeline.find_action(OverlayAction)
        self.assertIsInstance(overlay, OverlayAction)
        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(overlay.lava_test_dir, "lava-*"))
        distro_support_dir = "%s/distro/%s" % (overlay.lava_test_dir, "debian")
        for script in glob.glob(os.path.join(distro_support_dir, "lava-*")):
            scripts_to_copy.append(script)
        check_list = list({os.path.basename(scr) for scr in scripts_to_copy})

        self.assertCountEqual(check_list, script_list)
        self.assertEqual(
            overlay.xmod,
            stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH,
        )

    def test_overlay_override(self):
        job = self.factory.create_job("qemu01", "sample_jobs/kvm-context.yaml")
        overlay = job.pipeline.find_action(OverlayAction)
        self.assertEqual(
            "/sysroot/lava-%s", overlay.get_constant("lava_test_results_dir", "posix")
        )


class TestDefinitionSimple(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-notest.yaml")

    def test_job_without_tests(self):
        allow_missing_path(
            self.job.pipeline.validate_actions, self, "qemu-system-x86_64"
        )

        self.assertEqual(len(self.job.pipeline.actions), 3)  # deploy, boot, finalize
        deploy, boot, finalize = self.job.pipeline.actions
        self.assertEqual(deploy.name, "deployimages")
        self.assertEqual(boot.section, "boot")
        self.assertIsInstance(finalize, FinalizeAction)
        self.assertIsInstance(deploy.pipeline.actions[0], DownloaderAction)
        self.assertEqual(
            len(deploy.pipeline.actions), 1
        )  # deploy without test only needs DownloaderAction


class TestDefinitionParams(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_kvm_job("sample_jobs/kvm-params.yaml")

    def test_job_without_tests(self):
        allow_missing_path(
            self.job.pipeline.validate_actions, self, "qemu-system-x86_64"
        )

        self.assertEqual(
            len(self.job.pipeline.actions), 4
        )  # deploy, boot, test, finalize
        self.assertIsInstance(self.job.pipeline.actions[3], FinalizeAction)

        testdef = self.job.pipeline.find_action(TestDefinitionAction)
        test = testdef.pipeline.actions[1]
        install = testdef.pipeline.actions[2]
        runsh = testdef.pipeline.actions[3]

        self.assertNotIn("test_params", testdef.parameters)
        self.assertIsInstance(install, TestInstallAction)
        self.assertIsInstance(runsh, TestRunnerAction)
        self.assertIsNot(list(install.parameters.items()), [])
        testdef = {
            "params": {"VARIABLE_NAME_1": "value_1", "VARIABLE_NAME_2": "value_2"}
        }
        content = test.handle_parameters(testdef)
        self.assertEqual(
            set(content),
            {
                "###default parameters from test definition###\n",
                "VARIABLE_NAME_1='value_1'\n",
                "VARIABLE_NAME_2='value_2'\n",
                "######\n",
                "###test parameters from job submission###\n",
                "VARIABLE_NAME_1='eth2'\n",
                "VARIABLE_NAME_2='wlan0'\n",
            },
        )
        testdef = {
            "parameters": {"VARIABLE_NAME_1": "value_1", "VARIABLE_NAME_2": "value_2"}
        }
        content = test.handle_parameters(testdef)
        self.assertEqual(
            set(content),
            {
                "###default parameters from test definition###\n",
                "VARIABLE_NAME_1='value_1'\n",
                "VARIABLE_NAME_2='value_2'\n",
                "######\n",
                "###test parameters from job submission###\n",
                "VARIABLE_NAME_1='eth2'\n",
                "VARIABLE_NAME_2='wlan0'\n",
            },
        )

    @patch("lava_dispatcher.actions.deploy.testdef.GitHelper")
    @unittest.skipIf(infrastructure_error("git"), "git not installed")
    def test_install_repos(self, GitHelper):
        job = self.factory.create_kvm_job("sample_jobs/kvm-install.yaml")
        allow_missing_path(job.pipeline.validate_actions, self, "qemu-system-x86_64")

        testdef = job.pipeline.find_action(TestDefinitionAction)
        test_install = testdef.pipeline.find_action(TestInstallAction)
        self.assertIsNotNone(test_install)
        yaml_file = os.path.join(os.path.dirname(__file__), "./testdefs/install.yaml")
        self.assertTrue(os.path.exists(yaml_file))
        with open(yaml_file) as test_file:
            testdef = yaml_safe_load(test_file)
        repos = testdef["install"].get("git-repos", [])
        self.assertIsNotNone(repos)
        self.assertIsInstance(repos, list)
        for repo in repos:
            self.assertIsNotNone(repo)
        runner_path = tempfile.mkdtemp()
        test_install.install_git_repos(testdef, runner_path)
        shutil.rmtree(runner_path)


class TestSkipInstall(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = UBootFactory()
        self.job = factory.create_bbb_job("sample_jobs/bbb-skip-install.yaml")

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_skip_install_params(self, which_mock):
        testdefs = self.job.pipeline.find_all_actions(TestInstallAction)
        ubuntu_testdef = None
        single_testdef = None
        for testdef in testdefs:
            if testdef.parameters["path"] == "lava-test-shell/smoke-tests-basic.yaml":
                ubuntu_testdef = testdef
            elif (
                testdef.parameters["path"]
                == "lava-test-shell/single-node/singlenode03.yaml"
            ):
                single_testdef = testdef
            else:
                self.fail("Unexpected test definition in sample job.")
        self.assertNotIn("skip_install", ubuntu_testdef.parameters)
        self.assertIn("skip_install", single_testdef.parameters)
        self.job.validate()
        self.assertEqual(
            single_testdef.skip_list,
            ["keys", "sources", "deps", "steps", "git-repos", "all"],
        )
        self.assertEqual(single_testdef.skip_options, ["deps"])


class TestDefinitions(LavaDispatcherTestCase):
    """
    For compatibility until the V1 code is removed and we can start
    cleaning up Lava Test Shell.
    Parsing patterns in the Test Shell Definition YAML are problematic,
    difficult to debug and rely on internal python syntax.
    The fixupdict is even more confusing for all concerned.
    """

    def setUp(self):
        super().setUp()
        self.testdef = os.path.join(
            os.path.dirname(__file__), "testdefs", "params.yaml"
        )
        self.res_data = os.path.join(
            os.path.dirname(__file__), "testdefs", "result-data.txt"
        )
        self.factory = UBootFactory()
        self.job = self.factory.create_bbb_job("sample_jobs/bbb-nfs-url.yaml")

    def test_pattern(self):
        self.assertTrue(os.path.exists(self.testdef))
        with open(self.testdef) as par:
            params = yaml_safe_load(par)
        self.assertIn("parse", params.keys())
        line = "test1a: pass"
        self.assertEqual(
            r"(?P<test_case_id>.*-*):\s+(?P<result>(pass|fail))",
            params["parse"]["pattern"],
        )
        match = re.search(params["parse"]["pattern"], line)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(), line)
        self.assertEqual(match.group(1), "test1a")
        self.assertEqual(match.group(2), "pass")

    def test_v1_defaults(self):
        pattern = PatternFixup(testdef=None, count=0)
        # without a name from a testdef, the pattern is not valid.
        self.assertFalse(pattern.valid())
        with open(self.testdef) as par:
            params = yaml_safe_load(par)
        pattern = PatternFixup(testdef=params, count=0)
        self.assertTrue(pattern.valid())

    def test_definition_lists(self):
        with patch(
            "lava_dispatcher.actions.deploy.tftp.which",
            return_value="/usr/bin/in.tftpd",
        ), patch(
            "lava_dispatcher.actions.deploy.apply_overlay.rpcinfo_nfs",
            return_value=None,
        ):
            self.job.validate()

        apply_o = self.job.pipeline.find_action(ApplyOverlayTftp)
        self.assertIsInstance(apply_o.parameters.get("persistent_nfs"), dict)
        self.assertIsInstance(apply_o.parameters["persistent_nfs"].get("address"), str)

        definition = self.job.pipeline.find_action(TestDefinitionAction)
        git_repos = self.job.pipeline.find_all_actions(GitRepoAction)
        self.assertIn("common", self.job.context)
        self.assertIn("test-definition", self.job.context["common"])
        self.assertIsNotNone(
            definition.get_namespace_data(
                action=definition.name, label="test-definition", key="testdef_index"
            )
        )
        self.assertEqual(
            definition.get_namespace_data(
                action=definition.name, label="test-definition", key="testdef_index"
            ),
            ["smoke-tests", "singlenode-advanced"],
        )
        self.assertEqual(
            git_repos[0].get_namespace_data(
                action="test-runscript-overlay",
                label="test-runscript-overlay",
                key="testdef_levels",
            ),
            {"1.1.4.4": "0_smoke-tests", "1.1.4.8": "1_singlenode-advanced"},
        )
        self.assertEqual(
            {repo.uuid for repo in git_repos},
            {f"{self.job.job_id}_1.1.4.1", f"{self.job.job_id}_1.1.4.5"},
        )
        self.assertEqual(
            set(
                git_repos[0]
                .get_namespace_data(
                    action="test-runscript-overlay",
                    label="test-runscript-overlay",
                    key="testdef_levels",
                )
                .values()
            ),
            {"1_singlenode-advanced", "0_smoke-tests"},
        )
        # fake up a run step
        with open(self.testdef) as par:
            params = yaml_safe_load(par)
        self.assertEqual(
            r"(?P<test_case_id>.*-*):\s+(?P<result>(pass|fail))",
            params["parse"]["pattern"],
        )
        self.job.context.setdefault("test", {})
        for git_repo in git_repos:
            self.job.context["test"].setdefault(git_repo.uuid, {})
            self.job.context["test"][git_repo.uuid]["testdef_pattern"] = {
                "pattern": params["parse"]["pattern"]
            }
        self.assertEqual(
            self.job.context["test"],
            {
                f"{self.job.job_id}_1.1.4.1": {
                    "testdef_pattern": {
                        "pattern": "(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))"
                    }
                },
                f"{self.job.job_id}_1.1.4.5": {
                    "testdef_pattern": {
                        "pattern": "(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))"
                    }
                },
            },
        )
        testdef_index = self.job.context["common"]["test-definition"][
            "test-definition"
        ]["testdef_index"]
        start_run = "0_smoke-tests"
        uuid_list = definition.get_namespace_data(
            action="repo-action", label="repo-action", key="uuid-list"
        )
        self.assertIsNotNone(uuid_list)
        for key, value in enumerate(testdef_index):
            if start_run == "%s_%s" % (key, value):
                self.assertEqual(f"{self.job.job_id}_1.1.4.1", uuid_list[key])
                self.assertEqual(
                    self.job.context["test"][uuid_list[key]]["testdef_pattern"][
                        "pattern"
                    ],
                    "(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))",
                )

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
        with open(self.testdef) as par:
            params = yaml_safe_load(par)
        pattern = params["parse"]["pattern"]
        re_pat = re.compile(pattern, re.M)
        match = re.search(re_pat, data)
        if match:
            self.assertEqual(
                match.groupdict(), {"test_case_id": "test1a", "result": "pass"}
            )
        child = pexpect.spawn("cat", [self.res_data], encoding="utf-8")
        child.expect([re_pat, pexpect.EOF])
        self.assertEqual(child.after.encode("utf-8"), b"test1a: pass")
        child.expect([re_pat, pexpect.EOF])
        self.assertEqual(child.after.encode("utf-8"), b"test2a: fail")
        child.expect([re_pat, pexpect.EOF])
        self.assertEqual(child.after, pexpect.EOF)


class TestRunScript(LavaDispatcherTestCase):
    def setUp(self):
        self.job = self.create_simple_job()

        self.action = TestRunnerAction(self.job)
        self.action.section = "test"
        # Set by TestDefinitionAction to: JobID_RepoActionPipelineLevel
        self.action.test_uuid = "1_1.1.4.5"
        # TestDefinitionAction populate the below pipeline for each testdef:
        # UrlRepoAction->TestOverlayAction->TestInstallAction->TestRunnerAction
        self.action.level = "1.1.4.8"

        self.action.parameters = {
            "name": "test1",
            "path": "test1.yaml",
            "from": "git",
            "repository": "http://example.com/repo.git",
            # populated by TestDefinitionAction.
            "test_name": "1_test1",
        }

        self.testdef = {
            "parameters": {"key1": "value1"},
            "run": {"steps": ["step1", "step2"]},
        }

    def test_validate(self):
        with patch(
            "lava_dispatcher.actions.deploy.testdef.TestRunnerAction.get_namespace_data",
            side_effect=[["test0", "test1"], None],
        ):
            with patch(
                "lava_dispatcher.actions.deploy.testdef.TestRunnerAction.set_namespace_data"
            ) as mock_set_testdef_levels:
                self.action.validate()
                mock_set_testdef_levels.assert_called_once_with(
                    action="test-runscript-overlay",
                    key="testdef_levels",
                    label="test-runscript-overlay",
                    value={"1.1.4.8": "1_test1"},
                )
                self.assertTrue(self.action.valid)

    def test_validate_unique_names(self):
        with patch(
            "lava_dispatcher.actions.deploy.testdef.TestRunnerAction.get_namespace_data",
            side_effect=[["test1", "test1"], None],
        ):
            with patch(
                "lava_dispatcher.actions.deploy.testdef.TestRunnerAction.set_namespace_data"
            ):
                self.action.validate()
                self.assertFalse(self.action.valid)
                self.assertIn(
                    "Test definition names need to be unique.", self.action.errors
                )

    def test_validate_update_testdef_levels(self):
        with patch(
            "lava_dispatcher.actions.deploy.testdef.TestRunnerAction.get_namespace_data",
            side_effect=[["test0", "test1"], {"1.1.4.4": "0_test0"}],
        ):
            with patch(
                "lava_dispatcher.actions.deploy.testdef.TestRunnerAction.set_namespace_data"
            ) as mock_set_testdef_levels:
                self.action.validate()
                mock_set_testdef_levels.assert_called_once_with(
                    action="test-runscript-overlay",
                    key="testdef_levels",
                    label="test-runscript-overlay",
                    value={"1.1.4.4": "0_test0", "1.1.4.8": "1_test1"},
                )
                self.assertTrue(self.action.valid)

    @patch(
        "lava_dispatcher.actions.deploy.testdef.TestRunnerAction.get_namespace_data",
        side_effect=[
            "/overlay/runner/path",
            {"1.1.4.4": "0_test0", "1.1.4.8": "1_test1"},
            "/lava-1/1/tests/1_test1",
        ],
    )
    @patch("lava_dispatcher.actions.deploy.testdef.TestOverlayAction.run")
    def test_run(
        self,
        mock_super_run,
        mock_get_ns_data,
    ):
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            with patch(
                "lava_dispatcher.actions.deploy.testdef.yaml_safe_load",
                return_value=self.testdef,
            ):
                self.action.run(None, None)

                mock_file().write.assert_has_calls(
                    [
                        call("###default parameters from test definition###\n"),
                        call("key1='value1'\n"),
                        call("######\n"),
                        call("###test parameters from job submission###\n"),
                        call("######\n"),
                        call("set -e\n"),
                        call("set -x\n"),
                        call("export TESTRUN_ID=1_test1\n"),
                        call("cd /lava-1/1/tests/1_test1\n"),
                        call('UUID="$(cat uuid)"\n'),
                        call("set +x\n"),
                        call('echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"\n'),
                        call("set -x\n"),
                        call("step1\n"),
                        call("step2\n"),
                        call("set +x\n"),
                        call('echo "<LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>"\n'),
                    ]
                )

                self.assertEqual(self.action.results["uuid"], "1_1.1.4.5")
                self.assertEqual(self.action.results["name"], "test1")
                self.assertEqual(self.action.results["path"], "test1.yaml")
                self.assertEqual(self.action.results["from"], "git")
                self.assertEqual(
                    self.action.results["repository"],
                    "http://example.com/repo.git",
                )

    @patch(
        "lava_dispatcher.actions.deploy.testdef.TestRunnerAction.get_namespace_data",
        side_effect=[
            "/overlay/runner/path",
            {"1.1.4.4": "0_test0", "1.1.4.8": "1_test1"},
            "/lava-1/1/tests/1_test1",
        ],
    )
    @patch("lava_dispatcher.actions.deploy.testdef.TestOverlayAction.run")
    def test_run_kmsg_signal(
        self,
        mock_super_run,
        mock_get_ns_data,
    ):
        self.action.parameters["lava-signal"] = "kmsg"

        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            with patch(
                "lava_dispatcher.actions.deploy.testdef.yaml_safe_load",
                return_value=self.testdef,
            ):
                self.action.run(None, None)

                mock_file().write.assert_has_calls(
                    [
                        call("###default parameters from test definition###\n"),
                        call("key1='value1'\n"),
                        call("######\n"),
                        call("###test parameters from job submission###\n"),
                        call("######\n"),
                        call("set -e\n"),
                        call("set -x\n"),
                        call("export TESTRUN_ID=1_test1\n"),
                        call("cd /lava-1/1/tests/1_test1\n"),
                        call('UUID="$(cat uuid)"\n'),
                        call("set +x\n"),
                        call("export KMSG=true\n"),
                        call(
                            'echo "<0><LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>" > /dev/kmsg\n'
                        ),
                        call("set -x\n"),
                        call("step1\n"),
                        call("step2\n"),
                        call("set +x\n"),
                        call("unset KMSG\n"),
                        call(
                            'echo "<0><LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>" > /dev/kmsg\n'
                        ),
                    ]
                )

    @patch(
        "lava_dispatcher.actions.deploy.testdef.TestRunnerAction.get_namespace_data",
        side_effect=[
            "/overlay/runner/path",
            {"1.1.4.4": "0_test0", "1.1.4.8": "1_test1"},
            "/lava-1/1/tests/1_test1",
        ],
    )
    @patch("lava_dispatcher.actions.deploy.testdef.TestOverlayAction.run")
    def test_run_character_delay(
        self,
        mock_super_run,
        mock_get_ns_data,
    ):
        self.action.parameters["needs_character_delay"] = True
        self.job.device["character_delays"] = {"test": "10"}

        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            with patch(
                "lava_dispatcher.actions.deploy.testdef.yaml_safe_load",
                return_value=self.testdef,
            ):
                self.action.run(None, None)

                mock_file().write.assert_has_calls(
                    [
                        call("###default parameters from test definition###\n"),
                        call("key1='value1'\n"),
                        call("######\n"),
                        call("###test parameters from job submission###\n"),
                        call("######\n"),
                        call("set -e\n"),
                        call("set -x\n"),
                        call("export TESTRUN_ID=1_test1\n"),
                        call("cd /lava-1/1/tests/1_test1\n"),
                        call('UUID="$(cat uuid)"\n'),
                        call("set +x\n"),
                        call("export CHARACTER_DELAY=0.01\n"),
                        call("sleep 0.01\n"),
                        call('echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"\n'),
                        call("set -x\n"),
                        call("step1\n"),
                        call("step2\n"),
                        call("set +x\n"),
                        call("sleep 0.01\n"),
                        call('echo "<LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>"\n'),
                    ]
                )


class TestStoreTestdefExpectedList(LavaDispatcherTestCase):
    def setUp(self):
        self.job = self.create_simple_job()
        self.action = RepoAction(self.job)
        self.action.uuid = "UUID"
        self.action.parameters = {
            "namespace": "common",
            "repository": "https://gitlab.com/lava/functional-tests.git",
            "from": "git",
            "path": "posix/smoke-tests-basic.yaml",
            "name": "smoke-tests",
        }
        self.testdef: dict[str, dict | list] = {
            "metadata": {
                "format": "Lava-Test Test Definition 1.0",
                "name": "test-expected-test-case-list",
            }
        }

    def tes_no_expected_list(self):
        data = self.action.get_namespace_data(
            action="test", label="UUID", key="testdef_expected"
        )

        self.assertIsNone(data)

    def test_empty_expected_list(self):
        self.testdef["expected"] = []

        self.action.store_testdef(self.testdef, "git")

        data = self.action.get_namespace_data(
            action="test", label="UUID", key="testdef_expected"
        )

        self.assertIsNone(data)

    def test_expected_list_from_testdef(self):
        self.testdef["expected"] = ["tc1", "tc2", "tc3"]

        self.action.store_testdef(self.testdef, "git")

        data = self.action.get_namespace_data(
            action="test", label="UUID", key="testdef_expected"
        )

        self.assertEqual(data, self.testdef["expected"])

    def test_expected_list_from_jobdef(self):
        self.action.parameters["expected"] = ["tc2", "tc3", "tc4"]

        self.action.store_testdef(self.testdef, "git")

        data = self.action.get_namespace_data(
            action="test", label="UUID", key="testdef_expected"
        )

        self.assertEqual(data, self.action.parameters["expected"])

    def test_jobdef_overwrites_testdef_expected_list(self):
        self.testdef["expected"] = ["tc1", "tc2", "tc3"]
        self.action.parameters["expected"] = ["tc2", "tc3", "tc4"]

        self.action.store_testdef(self.testdef, "git")

        data = self.action.get_namespace_data(
            action="test", label="UUID", key="testdef_expected"
        )

        self.assertEqual(data, self.action.parameters["expected"])
