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
    def test_compress_overlay(self) -> None:
        job = self.create_simple_job()
        compress_overlay = CompressOverlay(job)
        compress_overlay.parameters = {"namespace": "common"}

        sample_test_results_dir = "/lava-12345"
        compress_overlay.set_namespace_data(
            action="test",
            label="results",
            key="lava_test_results_dir",
            value=sample_test_results_dir,
        )

        with TemporaryDirectory(
            "sample_location"
        ) as sample_location, TemporaryDirectory(
            "mkdtemp"
        ) as mkdtemp_dir, patch.object(
            compress_overlay, "mkdtemp", return_value=mkdtemp_dir
        ):
            compress_overlay.set_namespace_data(
                action="test", label="shared", key="location", value=sample_location
            )
            sample_location_path = Path(sample_location)

            # Results dir that should be added to tar
            results_dir_path = Path(f"{sample_location_path}/{sample_test_results_dir}")
            results_dir_path.mkdir(exist_ok=False)
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
                self.assertTrue(overlay_tar.getmember("lava-12345").isdir())
                self.assertTrue(overlay_tar.getmember("lava-12345/foo").isfile())
                self.assertTrue(overlay_tar.getmember("./root").isdir())
                self.assertTrue(overlay_tar.getmember("./root/bar").isfile())
