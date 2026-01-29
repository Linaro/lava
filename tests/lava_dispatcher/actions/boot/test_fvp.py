# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from unittest import mock

import pytest

from lava_common.exceptions import JobError
from lava_dispatcher.actions.boot.fvp import (
    CheckFVPVersionAction,
    RunFVPeRPCApp,
    RunFVPShellCommands,
)
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


@pytest.fixture
def factory():
    return Factory()


fvp_version_output = """ARM V8 Foundation Platformr0p0 [1.2.3]
Copyright 2000-2021 ARM Limited.
All Rights Reserved."""


class TestCheckFVPVersionAction:
    @pytest.fixture
    def action(self, factory):
        job = factory.create_job("fvp-01", "sample_jobs/fvp_foundation.yaml")
        return job.pipeline.actions[1].pipeline.actions[0].pipeline.actions[0]

    def test_action_class(self, action):
        assert isinstance(action, CheckFVPVersionAction)

    def test_basic(self, action, mocker):
        action.validate()
        action.logger = mocker.MagicMock()
        conn = mocker.MagicMock()
        run_cmd = mocker.patch(
            "lava_dispatcher.actions.boot.fvp.CheckFVPVersionAction.run_cmd",
            return_value=0,
        )
        parsed_command = mocker.patch(
            "lava_dispatcher.actions.boot.fvp.CheckFVPVersionAction.parsed_command",
            return_value=fvp_version_output,
        )
        conn2 = action.run(conn, 60)
        assert conn2 is conn
        action.logger.results.assert_called()
        entry = action.logger.results.call_args[0][0]
        assert entry["extra"]["fvp-version"] == "ARM V8 Foundation Platformr0p0 [1.2.3]"
        run_cmd.assert_called_once_with(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                "Image foundation:11.8 exists locally",
                "foundation:11.8",
            ],
            allow_fail=True,
        )
        parsed_command.assert_called_once_with(
            [
                "docker",
                "run",
                "--rm",
                "foundation:11.8",
                "/opt/model/Foundation_Platformpkg/models/Linux64_GCC-6.4/Foundation_Platform",
                "--version",
            ]
        )


class TestRunFVPeRPCApp(LavaDispatcherTestCase):
    def setUp(self, job="sample_jobs/fvp_erpc_app.yaml"):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job("fvp-01", job)
        self.action = self.job.pipeline.find_action(RunFVPeRPCApp)

    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_pipeline(self):
        description_ref = self.pipeline_reference("fvp_erpc_app.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    @mock.patch.object(RunFVPeRPCApp, "get_namespace_data")
    @mock.patch("lava_dispatcher.actions.boot.fvp.ShellCommand")
    @mock.patch("lava_dispatcher.actions.boot.fvp.ShellSession")
    @mock.patch.object(RunFVPeRPCApp, "set_namespace_data")
    def test_run(
        self,
        mock_set_namespace_data,
        mock_shell_session_class,
        mock_shell_command,
        mock_get_namespace_data,
    ):
        self.action.validate()

        mock_get_namespace_data.side_effect = [
            "test-container",
            "/path/to/erpc_main",
        ]

        mock_shell = mock.MagicMock()
        mock_shell_command.return_value = mock_shell

        mock_shell_session = mock.MagicMock()
        mock_shell_session_class.return_value = mock_shell_session

        result = self.action.run(None, None)

        mock_get_namespace_data.assert_has_calls(
            [
                mock.call(action="run-fvp", label="fvp", key="container"),
                mock.call(action="download-action", label="file", key=self.action.app),
            ]
        )

        expected_cmd = (
            "docker exec --tty test-container sh -c "
            "'chmod +x /test-container/erpc_main && /test-container/erpc_main'"
        )
        mock_shell_command.assert_called_once_with(
            expected_cmd, self.action.timeout, logger=self.action.logger
        )

        mock_shell_session_class.assert_called_once_with(mock_shell)
        mock_set_namespace_data.assert_called_once_with(
            action="shared", label="shared", key="connection", value=mock_shell_session
        )

        assert result == mock_shell_session


class TestRunFVPShellCommands(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job(
            "fvp-01", "sample_jobs/fvp-shell-commands.yaml"
        )
        self.action = self.job.pipeline.find_action(RunFVPShellCommands)

    def test_pipeline(self):
        description_ref = self.pipeline_reference(
            "fvp-shell-commands.yaml", job=self.job
        )
        self.assertEqual(description_ref, self.job.pipeline.describe())

    def test_validate(self):
        self.action.validate()

        self.assertTrue(self.action.valid)
        self.assertEqual(self.action.errors, [])

    def test_validate_invalid(self):
        self.action.parameters["commands"] = "not list"
        self.action.validate()

        self.assertFalse(self.action.valid)
        self.assertEqual(self.action.errors, ["'commands' must be a list"])

    def test_run(self):
        self.action.commands = ["cmd1", "cmd2"]

        new_connection = mock.MagicMock()

        with mock.patch.object(
            self.action, "get_namespace_data", return_value="fvp-container"
        ):
            with mock.patch(
                "lava_dispatcher.actions.boot.fvp.ShellCommand"
            ) as mock_shell_command:
                with mock.patch(
                    "lava_dispatcher.actions.boot.fvp.ShellSession",
                    return_value=new_connection,
                ):
                    connection = self.action.run(None, None)

                    mock_shell_command.assert_called_once_with(
                        "docker exec --tty fvp-container sh -c 'cmd1 && cmd2'",
                        self.action.timeout,
                        logger=self.action.logger,
                    )
                    assert connection == new_connection
