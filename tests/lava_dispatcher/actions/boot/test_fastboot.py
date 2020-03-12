# -*- coding: utf-8 -*-
# Copyright (C) 2020 Linaro Limited
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

from lava_dispatcher.actions.boot.fastboot import BootFastbootAction, PreOs
from tests.lava_dispatcher.test_basic import Factory
import pytest


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
