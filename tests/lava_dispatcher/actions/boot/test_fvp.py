# -*- coding: utf-8 -*-
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.


import pytest
from tests.lava_dispatcher.test_basic import Factory
from lava_dispatcher.actions.boot.fvp import CheckFVPVersionAction


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
        parsed_command = mocker.patch(
            "lava_dispatcher.actions.boot.fvp.CheckFVPVersionAction.parsed_command",
            return_value=fvp_version_output,
        )
        conn2 = action.run(conn, 60)
        assert conn2 is conn
        action.logger.results.assert_called()
        entry = action.logger.results.call_args[0][0]
        assert entry["extra"]["fvp-version"] == "ARM V8 Foundation Platformr0p0 [1.2.3]"
