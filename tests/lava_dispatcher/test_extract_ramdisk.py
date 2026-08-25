# Copyright 2026 Qualcomm Inc.
#
# Author: Matt Hart <matthart@qti.qualcomm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import gzip
import os
from unittest.mock import MagicMock, patch

from lava_common.constants import RAMDISK_FNAME
from lava_dispatcher.actions.deploy.apply_overlay import ExtractRamdisk
from tests.lava_dispatcher.test_basic import LavaDispatcherTestCase


class TestExtractRamdisk(LavaDispatcherTestCase):
    def extract(self, compression="gz"):
        """
        Run ExtractRamdisk over a stand-in ramdisk, returning what it published
        for the other actions: (unpack directory, archive path).
        """
        workdir = self.create_temporary_directory()
        downloaded = workdir / "rootfs.cpio.gz"
        downloaded.write_bytes(b"not really a cpio")
        ramdisk_dir = self.create_temporary_directory()
        parts_dir = self.create_temporary_directory()

        job = self.create_simple_job()
        action = ExtractRamdisk(job)
        action.parameters = {"ramdisk": {"compression": compression}}

        published = {}

        def set_namespace_data(action=None, label=None, key=None, value=None, **kw):
            published[(label, key)] = value

        with (
            patch.object(action, "get_namespace_data", return_value=str(downloaded)),
            patch.object(action, "set_namespace_data", side_effect=set_namespace_data),
            patch.object(
                action, "mkdtemp", side_effect=[str(ramdisk_dir), str(parts_dir)]
            ),
            patch("lava_dispatcher.actions.deploy.apply_overlay.split_initramfs"),
            patch("lava_dispatcher.actions.deploy.apply_overlay.uncpio"),
            patch(
                "lava_dispatcher.actions.deploy.apply_overlay._decompress_if_needed",
                side_effect=lambda part, comp: part,
            ),
        ):
            action.run(MagicMock(), None)

        # cpio --create archives everything under the unpack directory, so
        # the original archive must be moved out of it, otherwise the
        # rebuilt ramdisk would contain the original archive as an entry.
        suffix = f".{compression}" if compression else ""
        self.assertFalse(os.path.exists(ramdisk_dir / (RAMDISK_FNAME + suffix)))

        return (
            published[("extracted_ramdisk", "directory")],
            published[("ramdisk_file", "file")],
        )

    def test_archive_path_is_not_the_unpack_directory(self):
        # CompressRamdisk writes the rebuilt archive to the "ramdisk_file"
        # path. Handing it the directory the contents were unpacked into makes
        # cpio fail with "Unable to create cpio archive", taking down every
        # tftp job that installs modules or an overlay into its ramdisk.
        directory, archive = self.extract()
        self.assertNotEqual(directory, archive)
        self.assertTrue(os.path.isdir(directory))
        self.assertFalse(os.path.isdir(archive))
        self.assertEqual(RAMDISK_FNAME, os.path.basename(archive))

    def test_archive_path_without_compression(self):
        directory, archive = self.extract(compression=None)
        self.assertNotEqual(directory, archive)
        self.assertEqual(RAMDISK_FNAME, os.path.basename(archive))

    def test_compressed_ramdisk_is_consumed_by_decompression(self):
        # decompress_file() replaces the compressed archive by its
        # decompressed counterpart, so nothing may assume the compressed
        # archive is still around once the parts have been extracted.
        workdir = self.create_temporary_directory()
        downloaded = workdir / "rootfs.cpio.gz"
        downloaded.write_bytes(gzip.compress(b"not really a cpio"))
        ramdisk_dir = self.create_temporary_directory()
        parts_dir = self.create_temporary_directory()

        job = self.create_simple_job()
        action = ExtractRamdisk(job)
        action.parameters = {"ramdisk": {"compression": "gz"}}

        published = {}

        def set_namespace_data(action=None, label=None, key=None, value=None, **kw):
            published[(label, key)] = value

        with (
            patch.object(action, "get_namespace_data", return_value=str(downloaded)),
            patch.object(action, "set_namespace_data", side_effect=set_namespace_data),
            patch.object(
                action, "mkdtemp", side_effect=[str(ramdisk_dir), str(parts_dir)]
            ),
            patch("lava_dispatcher.actions.deploy.apply_overlay.uncpio") as uncpio,
        ):
            action.run(MagicMock(), None)

        # The gzipped ramdisk is not a cpio archive, so split_initramfs() bails
        # out and the whole file is extracted as a single part.
        uncpio.assert_called_once_with(
            os.path.join(parts_dir, RAMDISK_FNAME),
            published[("extracted_ramdisk", "directory")],
        )
        # CompressRamdisk rebuilds the ramdisk next to the directory it was
        # unpacked into: neither the original archive nor its decompressed
        # counterpart may be left there.
        self.assertEqual(
            ["ramdisk"],
            os.listdir(os.path.dirname(published[("ramdisk_file", "file")])),
        )
