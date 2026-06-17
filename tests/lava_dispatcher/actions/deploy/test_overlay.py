# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from pathlib import Path
from tarfile import open as tarfile_open
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from lava_dispatcher.actions.deploy.apply_overlay import ParsePersistentNFS
from lava_dispatcher.actions.deploy.overlay import CompressOverlay, OverlayAction
from tests.lava_dispatcher.test_basic import Factory

from ...test_basic import LavaDispatcherTestCase


class Recorder:
    def __init__(self):
        self.data = ""

    def clean(self):
        self.data = ""

    def write(self, data):
        self.data += data


TEST_DATA: list[tuple[dict[str, Any], str, list[str]]] = [
    ({}, "", [""]),
    ({"hello": "world"}, "", ["export hello=world"]),
    (
        {"hello": "world", "something": "to say", "an_int": 1},
        "",
        ["export an_int=1", "export hello=world", "export something='to say'"],
    ),
    (
        [
            {"board_id": "49EBE14005DA77C"},
            {"parent": True, "usb_vendor_id": "12d1", "usb_product_id": "3609"},
        ],
        "DEVICE_INFO",
        [
            "export DEVICE_INFO_0_board_id=49EBE14005DA77C",
            "export DEVICE_INFO_1_parent=1",
            "export DEVICE_INFO_1_usb_product_id=3609",
            "export DEVICE_INFO_1_usb_vendor_id=12d1",
        ],
    ),
    (
        [{"board_id": "S_NO81730000"}, {"board_id": "S_NO81730001"}],
        "STATIC_INFO",
        [
            "export STATIC_INFO_0_board_id=S_NO81730000",
            "export STATIC_INFO_1_board_id=S_NO81730001",
        ],
    ),
    (
        [{"SATA": "/dev/disk/by-id/ata-SanDisk_SSD_PLUS_120GB_190504A00573"}],
        "STORAGE_INFO",
        [
            "export STORAGE_INFO_0_SATA=/dev/disk/by-id/"
            "ata-SanDisk_SSD_PLUS_120GB_190504A00573"
        ],
    ),
    (
        {"COMMAND": "sh -c 'date'"},
        "",
        ["export COMMAND='sh -c '\"'\"'date'\"'\"''"],
    ),
]


class TestExportData(LavaDispatcherTestCase):
    def test_export_data(self):
        for data, prefix, result in TEST_DATA:
            with self.subTest(data=data, prefix=prefix, result=result):
                action = OverlayAction(self.create_job_mock())
                fout = Recorder()
                action._export_data(fout, data, prefix)
                self.assertEqual(
                    sorted(fout.data.strip("\n").split("\n")),
                    result,
                )


def test_persist_nfs_place_holder():
    factory = Factory()
    factory.validate_job_strict = True
    job = factory.create_job("kvm03", "sample_jobs/qemu-download-postprocess.yaml")

    action = ParsePersistentNFS(job)
    action.parameters = {
        "persistent_nfs": {
            "address": "foo:/var/lib/lava/dispatcher/tmp/linux/imx8mm_rootfs"
        },
        "namespace": "common",
    }
    action.params = action.parameters["persistent_nfs"]
    with patch(
        "lava_dispatcher.actions.deploy.apply_overlay.rpcinfo_nfs",
        return_value=None,
    ):
        action.validate()
    assert action.job.device["dynamic_data"]["NFS_SERVER_IP"] == "foo"

    action.parameters = {
        "persistent_nfs": {
            "address": "{FILE_SERVER_IP}:/var/lib/lava/dispatcher/tmp/linux/imx8mm_rootfs"
        },
        "namespace": "common",
    }
    action.params = action.parameters["persistent_nfs"]
    with patch(
        "lava_dispatcher.actions.deploy.apply_overlay.rpcinfo_nfs",
        return_value=None,
    ):
        action.validate()
    assert action.job.device["dynamic_data"]["NFS_SERVER_IP"] == "foobar"


class TestCompressOverlay(LavaDispatcherTestCase):
    def _run_compress_overlay(self, sample_test_results_dir: str):
        """Run CompressOverlay with a populated overlay location.

        Creates ``<location>/<lava_test_results_dir>/foo`` and
        ``<location>/root/bar`` then runs the action. Returns a dict mapping
        every archive member name to its ``TarInfo`` (read before the temp
        directories holding the tarball are cleaned up).
        """
        job = self.create_simple_job()
        compress_overlay = CompressOverlay(job)
        compress_overlay.parameters = {"namespace": "common"}

        compress_overlay.set_namespace_data(
            action="test",
            label="results",
            key="lava_test_results_dir",
            value=sample_test_results_dir,
        )

        with (
            TemporaryDirectory("sample_location") as sample_location,
            TemporaryDirectory("mkdtemp") as mkdtemp_dir,
            patch.object(compress_overlay, "mkdtemp", return_value=mkdtemp_dir),
        ):
            compress_overlay.set_namespace_data(
                action="test", label="shared", key="location", value=sample_location
            )
            sample_location_path = Path(sample_location)

            # Results dir that should be added to tar. lava_test_results_dir is
            # an absolute path so strip the leading "/" before joining.
            results_dir_path = sample_location_path / sample_test_results_dir.lstrip(
                "/"
            )
            results_dir_path.mkdir(parents=True, exist_ok=False)
            (results_dir_path / "foo").write_text("foo")

            # "root" dir that should be added to tar
            root_dir_path = sample_location_path / "root"
            root_dir_path.mkdir(exist_ok=False)
            (root_dir_path / "bar").write_text("bar")

            compress_overlay.run(None, None)

            # Tar archive should be created in mkdtemp_dir
            mkdtemp_path = Path(mkdtemp_dir)
            compress_output_path = Path(
                compress_overlay.get_namespace_data(
                    action=compress_overlay.name, label="output", key="file"
                )
            )
            self.assertTrue(compress_output_path.is_relative_to(mkdtemp_path))

            with tarfile_open(compress_output_path, mode="r") as overlay_tar:
                return {m.name: m for m in overlay_tar.getmembers()}

    def test_compress_overlay(self) -> None:
        members = self._run_compress_overlay("/lava-12345")

        self.assertTrue(members["lava-12345"].isdir())
        self.assertTrue(members["lava-12345/foo"].isfile())
        self.assertTrue(members["./root"].isdir())
        self.assertTrue(members["./root/bar"].isfile())

    def test_compress_overlay_nested_results_dir(self) -> None:
        # When lava_test_results_dir is overridden to a nested path, the whole
        # path (minus the leading "/") must be preserved in the archive instead
        # of being collapsed to just the final "lava-XXXX" directory. This is
        # the behaviour fixed in commit 44e815f4a.
        members = self._run_compress_overlay("/var/lib/lava/lava-12345")

        self.assertTrue(members["var/lib/lava/lava-12345"].isdir())
        self.assertTrue(members["var/lib/lava/lava-12345/foo"].isfile())
        self.assertTrue(members["./root"].isdir())
        self.assertTrue(members["./root/bar"].isfile())

        # The basename-only entry that the old code produced must be absent.
        self.assertNotIn("lava-12345", members)

    def test_compress_overlay_member_names(self) -> None:
        # The exact set of archive members for a nested results dir: the results
        # dir is stored under its full path (minus the leading "/"). Intermediate
        # path components are not added as separate members, and nothing is added
        # at the collapsed basename location.
        members = self._run_compress_overlay("/results/lava-99999")

        self.assertEqual(
            set(members),
            {
                "results/lava-99999",
                "results/lava-99999/foo",
                "./root",
                "./root/bar",
            },
        )
