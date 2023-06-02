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


def test_skip_pre_os_command_on_lxc_job(factory):
    lxc_job = factory.create_job("hi6220-hikey-01.jinja2", "sample_jobs/fastboot.yaml")
    boot = lxc_job.pipeline.actions[3]
    assert isinstance(boot, BootFastbootAction)
    assert all([not isinstance(a, PreOs) for a in boot.pipeline.actions])


def test_skip_pre_os_command_on_docker_job(factory):
    docker_job = factory.create_job(
        "hi6220-hikey-01.jinja2", "sample_jobs/fastboot-docker.yaml"
    )
    boot = docker_job.pipeline.actions[1]
    assert isinstance(boot, BootFastbootAction)
    assert all([not isinstance(a, PreOs) for a in boot.pipeline.actions])
