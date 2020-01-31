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
from lava_common.exceptions import JobError
from lava_dispatcher.action import Action
from tests.lava_dispatcher.test_basic import StdoutTestCase, Factory
from lava_dispatcher.actions.deploy import docker
import subprocess


class TestFVPActions(StdoutTestCase):
    def setUp(self, job="sample_jobs/fvp_foundation.yaml"):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job("fvp-01.jinja2", job)

    def test_ramdisk_overlay(self):
        factory = TestFVPActions()
        factory.setUp("sample_jobs/fvp_ramdisk_overlay.yaml")
        deploy = [
            action
            for action in factory.job.pipeline.actions
            if action.name == "fvp-deploy"
        ][0]
        self.assertIsNotNone(deploy)

        overlay = [
            action
            for action in deploy.pipeline.actions
            if action.name == "apply-overlay-tftp"
        ][0]
        self.assertIsNotNone(overlay)
        # As we don't require the parameters['ramdisk']['install_overlay'] option,
        # check we still apply the overlay to the ramdisk
        self.assertEquals(True, overlay.force_ramdisk)


def test_shell_reference(monkeypatch):
    monkeypatch.setattr(Action, "run_cmd", lambda cmd: b"")
    monkeypatch.setattr(docker, "which", lambda a: "/usr/bin/docker")
    factory = TestFVPActions()
    factory.setUp()
    factory.job.validate()
    assert [] == factory.job.pipeline.errors
    description_ref = factory.pipeline_reference("fvp_foundation.yaml", job=factory.job)
    assert description_ref == factory.job.pipeline.describe(False)


def test_ramdisk_inside_disk(monkeypatch):
    monkeypatch.setattr(Action, "run_cmd", lambda cmd: b"")
    monkeypatch.setattr(docker, "which", lambda a: "/usr/bin/docker")
    factory = TestFVPActions()
    factory.setUp("sample_jobs/fvp_ramdisk_overlay.yaml")
    factory.job.validate()
    assert [] == factory.job.pipeline.errors
    description_ref = factory.pipeline_reference(
        "fvp_ramdisk_overlay.yaml", job=factory.job
    )
    assert description_ref == factory.job.pipeline.describe(False)
