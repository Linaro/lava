# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lava_dispatcher.utils.filesystem import copy_in_overlay, prepare_guestfs


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


class TestPrepareGuestfs(unittest.TestCase):
    """Exercise the mountpoint -> sub_dir handling in prepare_guestfs.

    The real external steps (create_ext4, inject_tar, qemu-img convert) are
    mocked out; the inject_tar mock captures the guest tarball that
    prepare_guestfs builds so the archive layout can be asserted.
    """

    def _make_overlay(self, base_dir: str, results_dir: str, entries: dict) -> str:
        """Create an overlay tarball mimicking CompressOverlay output.

        ``results_dir`` is the absolute lava_test_results_dir; its contents are
        stored under the full path (minus leading "/"), alongside a top-level
        "root" directory. Returns the path to the gzipped tarball.
        """
        src = Path(base_dir) / "src"
        results_path = src / results_dir.lstrip("/")
        results_path.mkdir(parents=True)
        for name, content in entries.items():
            (results_path / name).write_text(content)
        root_path = src / "root"
        root_path.mkdir()
        (root_path / "authorized_keys").write_text("ssh-key")

        overlay = os.path.join(base_dir, "overlay.tar.gz")
        with tarfile.open(overlay, "w:gz") as tar:
            tar.add(results_path, results_dir.lstrip("/"))
            tar.add(root_path, "./root")
        return overlay

    def _run(self, mountpoint: str, results_dir: str, entries: dict):
        """Run the e2fsprogs branch of prepare_guestfs, returning the names of
        the members written into the guest tarball that gets injected."""
        captured = {}

        def fake_inject_tar(action, image, tar_path):
            with tarfile.open(tar_path, "r") as tar:
                captured["names"] = set(tar.getnames())

        with tempfile.TemporaryDirectory() as workdir:
            overlay = self._make_overlay(workdir, results_dir, entries)

            action = MagicMock()
            action.parameters = {"overlay_backend": "e2fsprogs"}
            # prepare_guestfs calls action.mkdtemp() for tar_output and guest_dir
            action.mkdtemp.side_effect = lambda: tempfile.mkdtemp(dir=workdir)

            output = os.path.join(workdir, "guest.qcow2")
            with (
                patch(
                    "lava_dispatcher.utils.ext4.create_ext4", return_value="UUID-1234"
                ),
                patch(
                    "lava_dispatcher.utils.ext4.inject_tar", side_effect=fake_inject_tar
                ) as mock_inject,
                patch("lava_dispatcher.utils.filesystem.subprocess.run") as mock_run,
            ):
                uuid = prepare_guestfs(action, output, overlay, mountpoint, 64)

        self.assertEqual(uuid, "UUID-1234")
        mock_inject.assert_called_once()
        mock_run.assert_called_once()
        return captured["names"]

    def test_nested_mountpoint_contents_placed_at_root(self):
        # mountpoint is a nested results dir: its *contents* must be placed at
        # the archive root (so the device mounts them back at the original
        # nested path). This is the behaviour fixed in commit 44e815f4a.
        names = self._run(
            "/var/lib/lava/lava-12345",
            "/var/lib/lava/lava-12345",
            {"foo": "foo", "bar": "bar"},
        )
        self.assertEqual(names, {"foo", "bar"})

    def test_mountpoint_with_trailing_slash(self):
        # os.path.normpath() strips the trailing slash before lstrip("/"), so a
        # trailing slash on the mountpoint must not change the resolved sub_dir.
        names = self._run(
            "/var/lib/lava/lava-12345/",
            "/var/lib/lava/lava-12345",
            {"foo": "foo"},
        )
        self.assertEqual(names, {"foo"})

    def test_single_level_mountpoint(self):
        # The single-level case that already worked before the fix must keep
        # working: contents of /lava-12345 land at the archive root.
        names = self._run(
            "/lava-12345",
            "/lava-12345",
            {"foo": "foo", "baz": "baz"},
        )
        self.assertEqual(names, {"foo", "baz"})
