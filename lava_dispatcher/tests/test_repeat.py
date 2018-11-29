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

import time
import pytest

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.actions.boot.qemu import BootQEMUImageAction
from lava_dispatcher.actions.test.shell import TestShellRetry
from lava_dispatcher.tests.test_basic import Factory, StdoutTestCase
from lava_dispatcher.actions.deploy.testdef import get_deployment_testdefs
from lava_dispatcher.tests.test_defs import allow_missing_path


@pytest.fixture
def job():
    return Factory().create_kvm_job("sample_jobs/kvm-repeat.yaml")


def test_basic_structure(job):
    assert job is not None  # nosec - unit test support.
    job.validate()
    assert job.pipeline.errors == []  # nosec - unit test support.
    description_ref = StdoutTestCase.pipeline_reference("kvm-repeat.yaml")
    assert description_ref == job.pipeline.describe(False)  # nosec - unit test support.


def test_deploy_norepeat(job):
    deploy = [deploy for deploy in job.parameters["actions"] if "deploy" in deploy][0][
        "deploy"
    ]
    assert "repeat" not in deploy  # nosec - unit test support.


def test_repeat_yaml(job):
    assert ["repeat"] in [  # nosec - unit test support.
        list(actions.keys()) for actions in job.parameters["actions"]
    ]
    assert "repeat" in job.parameters["actions"][1]  # nosec - unit test support.
    repeat_block = job.parameters["actions"][1]["repeat"]
    assert "count" in repeat_block  # nosec - unit test support.
    # params is a list of default params for the actions, not a list of actions.
    params = [param for param in repeat_block if "count" not in param]
    assert "boot" in repeat_block["actions"][0]  # nosec - unit test support.
    assert "test" in repeat_block["actions"][1]  # nosec - unit test support.
    assert "boot" in repeat_block["actions"][2]  # nosec - unit test support.
    assert "test" in repeat_block["actions"][3]  # nosec - unit test support.
    # count the "namespace" parameter
    assert len(params) == 3  # nosec - unit test support.


def test_nested_structure(job):
    assert ["repeat"] in [  # nosec - unit test support.
        list(actions.keys()) for actions in job.parameters["actions"]
    ]
    # pull out the repeated actions and analyse those
    actions = [retries for retries in job.pipeline.actions if retries.valid]
    assert isinstance(actions[1], BootQEMUImageAction)  # nosec - unit test support.
    assert isinstance(actions[2], TestShellRetry)  # nosec - unit test support.
    assert isinstance(actions[4], TestShellRetry)  # nosec - unit test support.
    assert actions[1].max_retries == 1  # nosec - unit test support.
    assert actions[2].max_retries == 3  # nosec - unit test support.
    assert actions[3].max_retries == 2  # nosec - unit test support.
    assert "repeat-count" in actions[2].parameters  # nosec - unit test support.
    assert (  # nosec - unit test support.
        actions[6].parameters["repeat-count"] > actions[2].parameters["repeat-count"]
    )
    assert (  # nosec - unit test support.
        actions[9].parameters["repeat-count"] > actions[6].parameters["repeat-count"]
    )
    assert (  # nosec - unit test support.
        actions[20].parameters["repeat-count"] > actions[16].parameters["repeat-count"]
    )
    assert (  # nosec - unit test support.
        int([action.level for action in actions if "repeat" in action.parameters][0])
        > 25
    )
    assert "repeat" not in actions[2].parameters  # nosec - unit test support.


def test_single_repeat(job):
    assert ["boot"] in [  # nosec - unit test support.
        list(actions.keys()) for actions in job.parameters["actions"]
    ]
    repeat_actions = [
        action
        for action in job.pipeline.actions
        if isinstance(action, BootQEMUImageAction)
    ]
    boot = repeat_actions[-1]
    assert "repeat" in boot.parameters  # nosec - unit test support.
    assert "repeat-count" not in boot.parameters  # nosec - unit test support.
    repeat_yaml = [
        actions for actions in job.parameters["actions"] if "boot" in actions.keys()
    ][0]["boot"]
    assert "repeat" in repeat_yaml  # nosec - unit test support.
    assert repeat_yaml["repeat"] == 4  # nosec - unit test support.
    assert repeat_yaml["repeat"] == boot.max_retries  # nosec - unit test support.
    assert (  # nosec - unit test support.
        repeat_yaml["repeat"] == job.pipeline.actions[25].parameters["repeat"]
    )
    assert (  # nosec - unit test support.
        "repeat-count" not in job.pipeline.actions[25].parameters
    )


class DummyAction(Action):
    def __init__(self):
        super().__init__()
        self.ran = 0

    def run(self, connection, max_end_time):
        assert connection is None  # nosec - unit test support.
        assert max_end_time == 1  # nosec - unit test support.
        self.ran += 1


def test_repeat_action(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 0)
    ra = RetryAction()
    ra.parameters = {"repeat": 5}
    ra.level = "1"
    ra.internal_pipeline = Pipeline(parent=ra)
    ra.internal_pipeline.add_action(DummyAction())
    ra.run(None, 1)
    assert ra.internal_pipeline.actions[0].ran == 5  # nosec - unit test support.
