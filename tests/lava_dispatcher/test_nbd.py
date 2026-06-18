# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import patch

from lava_dispatcher.actions.boot import BootloaderCommandOverlay
from lava_dispatcher.actions.deploy.download import DownloadHandler
from lava_dispatcher.actions.deploy.nbd import NbdAction, XnbdAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


@patch("lava_dispatcher.actions.deploy.nbd.which", return_value="/usr/bin/nbd-server")
@patch("lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd")
class TestNbdDeploy(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()

    def test_nbdroot_shared_via_namespace(self, tftp_which, nbd_which):
        """Regression: XnbdAction must read nbdroot from the same namespace
        data that DownloadHandler sets."""
        job = self.factory.create_job("x86-01", "sample_jobs/up2-initrd-nbd.yaml")
        job.validate()

        xnbd = job.pipeline.find_action(XnbdAction)
        nbdroot_dl = [
            a
            for a in job.pipeline.find_all_actions(DownloadHandler)
            if a.key == "nbdroot"
        ][0]

        # Simulate what DownloadHandler.run() does.
        nbdroot_dl.set_namespace_data(
            action="download-action",
            label="file",
            key="nbdroot",
            value="/tmp/rootfs/ext4/nbdroot.ext4",
        )
        self.assertEqual(
            xnbd.get_namespace_data(
                action="download-action", label="file", key="nbdroot"
            ),
            "/tmp/rootfs/ext4/nbdroot.ext4",
        )

    def test_nbd_pipeline_structure(self, tftp_which, nbd_which):
        """NbdAction appears before XnbdAction in the pipeline."""
        job = self.factory.create_job("x86-01", "sample_jobs/up2-initrd-nbd.yaml")
        job.validate()
        actions = list(job.pipeline._iter_actions())
        self.assertLess(
            next(i for i, a in enumerate(actions) if isinstance(a, NbdAction)),
            next(i for i, a in enumerate(actions) if isinstance(a, XnbdAction)),
        )

    def test_boot_action_detects_xnbd(self, tftp_which, nbd_which):
        """NBD boot action detects xnbd via protocols.lava-xnbd
        (merged by the job parser) to set {NBDSERVERIP}/{NBDSERVERPORT}."""
        job = self.factory.create_job("x86-01", "sample_jobs/up2-initrd-nbd.yaml")
        job.validate()
        self.assertIn(
            "lava-xnbd", job.pipeline.find_action(BootloaderCommandOverlay).parameters
        )
