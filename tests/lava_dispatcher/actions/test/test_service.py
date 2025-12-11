# Copyright (C) 2025 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import subprocess
from unittest.mock import MagicMock, patch

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.actions.commands import CommandAction
from lava_dispatcher.actions.test.service import TestServiceAction, TestServices
from lava_dispatcher.actions.test_strategy import TestService
from lava_dispatcher.device import PipelineDevice
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestTestServiceStrategy(LavaDispatcherTestCase):
    def setUp(self):
        self.device = PipelineDevice({})
        self.service = {
            "name": "srv1",
            "from": "git",
            "repository": "https://example.com/srv1.git",
            "path": "docker-compose.yaml",
        }
        self.required_params = ["name", "from", "repository", "path"]

    def test_accepts_true(self):
        self.assertEqual(
            TestService.accepts(self.device, {"services": [self.service]}),
            (True, "accepted"),
        )

    def test_accepts_true_empty(self):
        self.assertEqual(
            TestService.accepts(self.device, {"services": []}),
            (True, "accepted"),
        )

    def test_accepts_false(self):
        self.assertEqual(
            TestService.accepts(self.device, {}),
            (False, '"services" not in parameters'),
        )

    def test_accepts_false_missing_params(self):
        for param in self.required_params:
            invalid_service = self.service.copy()
            del invalid_service[param]
            self.assertEqual(
                TestService.accepts(self.device, {"services": [invalid_service]}),
                (False, f"missing required parameters {[param]}"),
            )


class TestTestservices(LavaDispatcherTestCase):
    def setUp(self):
        self.job = self.create_simple_job()
        self.job.device["parameters"] = {"allow_test_services": True}
        self.action = TestServices(self.job)
        self.action.section = "test"
        self.action.parameters = {
            "namespace": "common",
            "services": [
                {
                    "name": "srv1",
                    "from": "git",
                    "repository": "https://example.com/srv1.git",
                    "path": "docker-compose.yaml",
                }
            ],
        }

    def test_validate_allowed(self):
        self.action.validate()
        self.assertTrue(self.action.valid)

    def test_validate_not_allowed(self):
        self.job.device["parameters"] = {"allow_test_services": False}

        self.action.validate()
        self.assertFalse(self.action.valid)
        self.assertEqual(
            self.action.errors,
            [
                (
                    "Device 'allow_test_services' must be set to 'true' "
                    "for running test services on LAVA worker."
                )
            ],
        )

    def test_validate_unique_name(self):
        self.action.parameters["services"].append(
            {
                "name": "srv1",
                "from": "git",
                "repository": "https://example.com/srv1.git",
                "path": "docker-compose.yaml",
            }
        )
        self.action.validate()
        self.assertFalse(self.action.valid)
        self.assertEqual(self.action.errors, ["Test service names need to be unique."])

    def test_validate_invalid_name(self):
        invalid_name = "invalid.name"
        self.action.parameters["services"].append(
            {
                "name": invalid_name,
                "from": "git",
                "repository": "https://example.com/srv1.git",
                "path": "docker-compose.yaml",
            }
        )
        self.action.validate()
        self.assertFalse(self.action.valid)
        self.assertEqual(
            self.action.errors,
            [
                f"Invalid characters found in test service name {invalid_name!r}. "
                "Allowed: letters, digits, underscore and hyphen."
            ],
        )


class TestTestServiceAction(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.action_path = "lava_dispatcher.actions.test.service.TestServiceAction"
        self.tmp_path = "/tmp/test-services"
        with patch(
            f"{self.action_path}.mkdtemp",
            return_value=self.tmp_path,
        ):
            self.job = self.factory.create_job(
                "docker-02", "sample_jobs/docker-test-services.yaml"
            )
        self.job.job_id = 123

        self.test_service_actions = self.job.pipeline.find_all_actions(
            TestServiceAction
        )
        self.command_action = self.job.pipeline.find_action(CommandAction)

        self.start_cmd_srv1 = [
            "docker",
            "compose",
            "--project-name",
            "lava-123-1-1-1-test-service-srv1",
            "--file",
            "docker-compose.yaml",
            "up",
            "--detach",
            "srv1",
        ]
        self.start_cmd_srv2 = [
            "docker",
            "compose",
            "--project-name",
            "lava-123-1-2-1-test-service-srv2",
            "--file",
            "docker-compose.yml",
            "up",
            "--detach",
        ]
        self.stop_cmd_list = [
            [
                "docker",
                "compose",
                "--project-name",
                "lava-123-1-1-1-test-service-srv1",
                "--file",
                "/tmp/test-services/srv1/docker-compose.yaml",
                "down",
            ],
            [
                "docker",
                "compose",
                "--project-name",
                "lava-123-1-2-1-test-service-srv2",
                "--file",
                "/tmp/test-services/srv2/docker-compose.yml",
                "down",
            ],
        ]

    def test_pipeline(self):
        description_ref = self.pipeline_reference(
            "docker-test-services.yaml", job=self.job
        )
        self.assertEqual(description_ref, self.job.pipeline.describe())

    def test_validate(self):
        with patch(
            f"lava_dispatcher.actions.test.service.which",
            return_value="/usr/bin/docker",
        ), patch("lava_dispatcher.actions.test.service.subprocess.run"):
            self.test_service_actions[0].validate()
            self.test_service_actions[1].validate()

        for action in self.test_service_actions:
            self.assertTrue(action.valid)
            self.assertTrue(action.service_name)
            self.assertTrue(action.download_dir)
            self.assertTrue(action.repo_dir)
            self.assertTrue(action.project_name)
            self.assertTrue(action.stop_cmd)

        self.assertEqual(self.test_service_actions[0].start_cmd, self.start_cmd_srv1)
        self.assertEqual(self.test_service_actions[1].start_cmd, self.start_cmd_srv2)

        self.assertTrue(self.command_action.valid)
        stop_cmd_list = self.command_action.get_namespace_data(
            action="lava-test-service", label="stop-services", key="cmd-list"
        )
        self.assertEqual(stop_cmd_list, self.stop_cmd_list)

    def test_validate_compose_v1(self):
        action = self.test_service_actions[0]
        with patch(
            f"lava_dispatcher.actions.test.service.which",
            side_effect=["/usr/bin/docker", "/usr/bin/docker-compose"],
        ), patch(
            "lava_dispatcher.actions.test.service.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "docker compose version"),
        ):
            action.validate()

        self.assertEqual(action.start_cmd[0], "docker-compose")
        self.assertEqual(action.stop_cmd[0], "docker-compose")

    def test_run_from_url(self):
        srv1 = self.test_service_actions[0]
        srv1.pipeline = None
        srv1.repo_dir = f"{self.tmp_path}/srv1"
        srv1.start_cmd = self.start_cmd_srv1

        with self.subTest("Raise JobError"), self.assertRaisesRegex(
            JobError, "Repo archive not found."
        ):
            srv1.run(None, 420)

        self.assertFalse(srv1.started)
        fpath = f"{self.tmp_path}/lava-service/srv1.tar"
        with self.subTest("Run success"), patch(
            f"{self.action_path}.get_namespace_data",
            return_value=fpath,
        ), patch(
            "lava_dispatcher.actions.test.service.untar_file"
        ) as untar_file_mock, patch(
            f"{self.action_path}.run_cmd"
        ) as run_cmd_mock:
            srv1.run(None, 420)

        untar_file_mock.assert_called_once_with(fpath, srv1.repo_dir)
        run_cmd_mock.assert_called_once_with(
            srv1.start_cmd, allow_fail=False, cwd=srv1.repo_dir
        )
        self.assertTrue(srv1.started)

    def test_run_from_git(self):
        srv2 = self.test_service_actions[1]
        srv2.repo_dir = f"{self.tmp_path}/srv2"
        srv2.start_cmd = self.start_cmd_srv2

        with self.subTest("Raise error"), patch(
            "lava_dispatcher.actions.test.service.GitHelper"
        ) as GitHelper_mock:
            git_instance_mock = MagicMock()
            git_instance_mock.clone.return_value = None  # Simulate failure
            GitHelper_mock.return_value = git_instance_mock

            with self.assertRaisesRegex(
                InfrastructureError,
                "Unable to clone repo https://example.com/org/srv2.git",
            ):
                srv2.run(None, 420)

        self.assertFalse(srv2.started)
        fpath = f"{self.tmp_path}/lava-service/srv2"
        with self.subTest("Run success"), patch(
            f"{self.action_path}.get_namespace_data",
            return_value=fpath,
        ), patch(
            "lava_dispatcher.actions.test.service.GitHelper"
        ) as GitHelper_mock, patch(
            f"{self.action_path}.run_cmd"
        ) as run_cmd_mock:
            git_instance_mock = MagicMock()
            git_instance_mock.clone.return_value = "commitid"
            GitHelper_mock.return_value = git_instance_mock

            srv2.run(None, 420)

        GitHelper_mock.assert_called_once_with("https://example.com/org/srv2.git")

        git_instance_mock.clone.assert_called_once_with(
            srv2.repo_dir,
            shallow=True,
            revision=None,
            branch=None,
            history=True,
            recursive=False,
        )

        run_cmd_mock.assert_called_once_with(
            srv2.start_cmd, allow_fail=False, cwd=srv2.repo_dir
        )
        self.assertTrue(srv2.started)

    def test_run_from_unknown(self):
        srv = self.test_service_actions[1]
        repo_type = "unknown"
        srv.parameters["from"] = repo_type

        with self.assertRaisesRegex(
            JobError,
            f"Repository from {repo_type!r} is not supported. Allowed: 'git' and 'url'.",
        ):
            srv.run(None, 420)

    def test_cleanup(self):
        srv = self.test_service_actions[1]
        srv.repo_dir = f"{self.tmp_path}/srv"
        srv.stop_cmd = self.stop_cmd_list[1]

        with self.subTest("Service not started"), patch(
            f"{self.action_path}.run_cmd"
        ) as run_cmd_mock:
            srv.cleanup(None, None)
        run_cmd_mock.assert_not_called()

        with self.subTest("Service started"), patch(
            f"{self.action_path}.run_cmd"
        ) as run_cmd_mock:
            srv.started = True
            srv.cleanup(None, None)
        run_cmd_mock.assert_called_once_with(srv.stop_cmd, allow_fail=True)

        with self.subTest("Repo not created"), patch(
            "lava_dispatcher.actions.test.service.os.path.exists", return_value=False
        ), patch(
            "lava_dispatcher.actions.test.service.shutil.rmtree"
        ) as shutil_rmtree_mock:
            srv.cleanup(None, None)
        shutil_rmtree_mock.assert_not_called()

        with self.subTest("Repo created"), patch(
            "lava_dispatcher.actions.test.service.os.path.exists", return_value=True
        ), patch(
            "lava_dispatcher.actions.test.service.shutil.rmtree"
        ) as shutil_rmtree_mock:
            srv.cleanup(None, None)
        shutil_rmtree_mock.assert_called_once_with(srv.repo_dir)
