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
from lava_dispatcher.action import Action
from tests.lava_dispatcher.test_basic import StdoutTestCase, Factory


class TestFVPActions(StdoutTestCase):
    def setUp(self, job="sample_jobs/fvp_foundation.yaml"):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job("fvp-01.jinja2", job)


def test_shell_reference(monkeypatch):
    monkeypatch.setattr(Action, "run_cmd", lambda cmd: b"")
    factory = TestFVPActions()
    factory.setUp()
    factory.job.validate()
    assert [] == factory.job.pipeline.errors  # nosec
    description_ref = factory.pipeline_reference("fvp_foundation.yaml", job=factory.job)
    assert description_ref == factory.job.pipeline.describe(False)  # nosec


def test_use_telnet(monkeypatch):
    monkeypatch.setattr(Action, "run_cmd", lambda cmd: b"")
    factory = TestFVPActions()
    factory.setUp(job="sample_jobs/fvp_foundation_use_telnet.yaml")
    factory.job.validate()
    assert [] == factory.job.pipeline.errors  # nosec
    description_ref = factory.pipeline_reference(
        "fvp_foundation_use_telnet.yaml", job=factory.job
    )
    assert description_ref == factory.job.pipeline.describe(False)  # nosec


def test_transfer_overlay(monkeypatch):
    monkeypatch.setattr(Action, "run_cmd", lambda cmd: b"")
    factory = TestFVPActions()
    factory.setUp(job="sample_jobs/fvp_foundation_transfer_overlay.yaml")
    factory.job.validate()
    assert [] == factory.job.pipeline.errors  # nosec
    description_ref = factory.pipeline_reference(
        "fvp_foundation_transfer_overlay.yaml", job=factory.job
    )
    assert description_ref == factory.job.pipeline.describe(False)  # nosec
    boot_fvp = [
        action for action in factory.job.pipeline.actions if action.name == "boot-fvp"
    ][0]
    assert boot_fvp is not None
    boot_fvp_main = [
        action for action in boot_fvp.pipeline.actions if action.name == "boot-fvp-main"
    ][0]
    assert boot_fvp_main is not None
    transfer_overlay = [
        action
        for action in boot_fvp.pipeline.actions
        if action.name == "overlay-unpack"
    ][0]
    assert transfer_overlay is not None
