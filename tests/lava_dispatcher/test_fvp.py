# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from lava_dispatcher.action import Action
from lava_dispatcher.actions.boot import OverlayUnpack
from lava_dispatcher.actions.boot.fvp import BootFVPAction, BootFVPMain
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestFVPActions(LavaDispatcherTestCase):
    def setUp(self, job="sample_jobs/fvp_foundation.yaml"):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job("fvp-01", job)


def test_shell_reference(monkeypatch):
    monkeypatch.setattr(Action, "run_cmd", lambda cmd: b"")
    factory = TestFVPActions()
    factory.setUp()
    factory.job.validate()
    assert [] == factory.job.pipeline.errors  # nosec
    description_ref = factory.pipeline_reference("fvp_foundation.yaml", job=factory.job)
    assert description_ref == factory.job.pipeline.describe()  # nosec


def test_use_telnet(monkeypatch):
    monkeypatch.setattr(Action, "run_cmd", lambda cmd: b"")
    factory = TestFVPActions()
    factory.setUp(job="sample_jobs/fvp_foundation_use_telnet.yaml")
    factory.job.validate()
    assert [] == factory.job.pipeline.errors  # nosec
    description_ref = factory.pipeline_reference(
        "fvp_foundation_use_telnet.yaml", job=factory.job
    )
    assert description_ref == factory.job.pipeline.describe()  # nosec


def test_transfer_overlay(monkeypatch):
    monkeypatch.setattr(Action, "run_cmd", lambda cmd: b"")
    factory = TestFVPActions()
    factory.setUp(job="sample_jobs/fvp_foundation_transfer_overlay.yaml")
    factory.job.validate()
    assert [] == factory.job.pipeline.errors  # nosec
    description_ref = factory.pipeline_reference(
        "fvp_foundation_transfer_overlay.yaml", job=factory.job
    )
    assert description_ref == factory.job.pipeline.describe()  # nosec

    boot_fvp = factory.job.pipeline.find_action(BootFVPAction)
    boot_fvp.pipeline.find_action(BootFVPMain)
    boot_fvp.pipeline.find_action(OverlayUnpack)
