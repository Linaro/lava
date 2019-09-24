# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
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
import unittest

from lava_dispatcher.tests.test_basic import StdoutTestCase, Factory
from lava_dispatcher.actions.deploy import docker
import subprocess


class TestFVPActions(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job("docker-01.jinja2", "sample_jobs/fvp.yaml")


def test_shell_reference(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda cmd: b"")
    monkeypatch.setattr(docker, "which", lambda a: "/usr/bin/docker")
    factory = TestFVPActions()
    factory.setUp()
    factory.job.validate()
    assert [] == factory.job.pipeline.errors
    description_ref = factory.pipeline_reference("fvp.yaml", job=factory.job)
    assert description_ref == factory.job.pipeline.describe(False)
