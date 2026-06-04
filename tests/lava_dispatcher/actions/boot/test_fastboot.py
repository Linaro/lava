# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from lava_dispatcher.actions.boot.fastboot import BootFastbootAction, PreOs
from tests.lava_dispatcher.test_basic import Factory


@pytest.fixture
def factory():
    return Factory()


def test_pre_os_command_on_docker_job(factory):
    # pre-os-command is run unconditionally, including for docker jobs, so a
    # device with a hard_reset_command always gets a PreOs action in its boot.
    docker_job = factory.create_job(
        "hi6220-hikey-01", "sample_jobs/fastboot-docker.yaml"
    )
    boot = docker_job.pipeline.actions[1]
    assert isinstance(boot, BootFastbootAction)
    assert any(isinstance(a, PreOs) for a in boot.pipeline.actions)
