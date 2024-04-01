# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import Any

from lava_dispatcher.actions.deploy.overlay import OverlayAction, PersistentNFSOverlay
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
            "ata-SanDisk_SSD_PLUS_120GB_190504A00573",
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

    action = PersistentNFSOverlay(job)
    action.parameters = {
        "persistent_nfs": {
            "address": "foo:/var/lib/lava/dispatcher/tmp/linux/imx8mm_rootfs"
        },
        "namespace": "common",
    }
    action.params = action.parameters["persistent_nfs"]
    action.validate()
    assert action.job.device["dynamic_data"]["NFS_SERVER_IP"] == "foo"

    action.parameters = {
        "persistent_nfs": {
            "address": "{FILE_SERVER_IP}:/var/lib/lava/dispatcher/tmp/linux/imx8mm_rootfs"
        },
        "namespace": "common",
    }
    action.params = action.parameters["persistent_nfs"]
    action.validate()
    assert action.job.device["dynamic_data"]["NFS_SERVER_IP"] == "foobar"
