# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later
import unittest
from unittest.mock import MagicMock, patch

from lava_dispatcher.utils.filesystem import copy_in_overlay


class TestOverlayBackendDeployParam(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4.inject_tar")
    @patch(
        "lava_dispatcher.utils.filesystem.decompress_file",
        return_value="/tmp/overlay.tar",
    )
    @patch("lava_dispatcher.utils.filesystem.os.path.exists", return_value=False)
    @patch(
        "lava_dispatcher.utils.filesystem._resolve_backend", return_value="e2fsprogs"
    )
    def test_copy_in_overlay_passes_deploy_parameters(
        self, mock_resolve, mock_exists, mock_decompress, mock_inject
    ):
        action = MagicMock()
        action.parameters = {"overlay_backend": "e2fsprogs"}
        copy_in_overlay(action, "/tmp/img.ext4", None, "/tmp/overlay.tar.gz")
        mock_resolve.assert_called_once_with(action.parameters)
        mock_inject.assert_called_once_with(action, "/tmp/img.ext4", "/tmp/overlay.tar")
