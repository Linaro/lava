# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import pytest

from lava_dispatcher.actions.boot.fvp import CheckFVPVersionAction
from tests.lava_dispatcher.test_basic import Factory


@pytest.fixture
def factory():
    return Factory()


fvp_version_output = """ARM V8 Foundation Platformr0p0 [1.2.3]
Copyright 2000-2021 ARM Limited.
All Rights Reserved."""


class TestCheckFVPVersionAction:
    @pytest.fixture
    def action(self, factory):
        job = factory.create_job("fvp-01.jinja2", "sample_jobs/fvp_foundation.yaml")
        return job.pipeline.actions[1].pipeline.actions[0].pipeline.actions[0]

    def test_action_class(self, action):
        assert type(action) is CheckFVPVersionAction

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
                "sh",
                "-c",
                "docker run --rm foundation:11.8 /opt/model/Foundation_Platformpkg/models/Linux64_GCC-6.4/Foundation_Platform --version",
            ]
        )
