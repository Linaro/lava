# Copyright (C) 2025 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from unittest.mock import patch

from lava_common.exceptions import JobError
from lava_dispatcher.actions.deploy.apply_overlay import ApplyOverlayAvh

from ...test_basic import LavaDispatcherTestCase


class TestApplyOverlay(LavaDispatcherTestCase):
    def test_append_overlays_validate(self):
        job = self.create_simple_job()
        action = ApplyOverlayAvh(job)

        # 1. Test working job definition.
        action.parameters = {
            "to": "avh",
            "namespace": "common",
            "timeout": {"minutes": 30},
            "options": {"model": "kronos"},
            "fw_package": {
                "url": "https://example.com/kronos/fw-package-1.0.zip",
                "storage_file": "virtio_0",
                "root_partition": 1,
            },
        }
        action.validate()

        # 2. Test missing 'strorage_file' key.
        action.parameters = {
            "to": "avh",
            "namespace": "common",
            "timeout": {"minutes": 30},
            "options": {"model": "kronos"},
            "fw_package": {
                "url": "https://example.com/kronos/fw-package-1.0.zip",
                "storage_file": "virtio_0",
            },
        }
        with self.assertRaisesRegex(
            JobError, "Unable to apply overlay without 'fw_package.root_partition'"
        ):
            action.validate()

        # 3. Test missing 'root_partition' key.
        action.parameters = {
            "to": "avh",
            "timeout": {"minutes": 30},
            "options": {"model": "kronos"},
            "fw_package": {"url": "https://example.com/kronos/fw-package-1.0.zip"},
        }
        with self.assertRaisesRegex(
            JobError, "Unable to apply overlay without 'fw_package.storage_file'"
        ):
            action.validate()

    @patch("lava_dispatcher.actions.deploy.apply_overlay.shutil.make_archive")
    @patch("lava_dispatcher.actions.deploy.apply_overlay.copy_in_overlay")
    @patch("lava_dispatcher.actions.deploy.apply_overlay.zipfile.ZipFile")
    @patch(
        "lava_dispatcher.actions.deploy.apply_overlay.ApplyOverlayAvh.mkdtemp",
        return_value="/mock/tempdir",
    )
    def test_append_overlays_run(
        self,
        mock_mkdtemp,
        mock_zipfile,
        mock_copy_in_overlay,
        mock_make_archive,
    ):
        job = self.create_simple_job()
        action = ApplyOverlayAvh(job)
        action.parameters = {
            "to": "avh",
            "namespace": "common",
            "timeout": {"minutes": 30},
            "options": {"model": "kronos"},
            "fw_package": {
                "url": "https://example.com/kronos/fw-package-1.0.zip",
                "storage_file": "virtio_0",
                "root_partition": 1,
            },
        }
        action.state.compresssed_overlay.file = "mock_overlay_file"
        action.state.downloads.create_downloaded_file(
            download_name="fw_package",
            download_file="mock_fw_package.zip",
        )

        action.validate()
        action.run(None, 0)

        mock_zipfile.assert_called_with("mock_fw_package.zip", "r")
        mock_copy_in_overlay.assert_called_once_with(
            f"/mock/tempdir/virtio_0", 1, "mock_overlay_file"
        )
        mock_make_archive.assert_called_once_with(
            "mock_fw_package", "zip", "/mock/tempdir"
        )
