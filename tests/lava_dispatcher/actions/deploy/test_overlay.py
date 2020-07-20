# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import pytest
from lava_dispatcher.actions.deploy.overlay import OverlayAction


class Recorder:
    def __init__(self):
        self.data = ""

    def clean(self):
        self.data = ""

    def write(self, data):
        self.data += data


@pytest.mark.parametrize(
    "data,prefix,result",
    [
        ({}, "", [""]),
        ({"hello": "world"}, "", ["export hello='world'"]),
        (
            {"hello": "world", "something": "to say", "an_int": 1},
            "",
            ["export an_int=1", "export hello='world'", "export something='to say'"],
        ),
        (
            [
                {"board_id": "49EBE14005DA77C"},
                {"parent": True, "usb_vendor_id": "12d1", "usb_product_id": "3609"},
            ],
            "DEVICE_INFO",
            [
                "export DEVICE_INFO_0_board_id='49EBE14005DA77C'",
                "export DEVICE_INFO_1_parent=1",
                "export DEVICE_INFO_1_usb_product_id='3609'",
                "export DEVICE_INFO_1_usb_vendor_id='12d1'",
            ],
        ),
        (
            [{"board_id": "S_NO81730000"}, {"board_id": "S_NO81730001"}],
            "STATIC_INFO",
            [
                "export STATIC_INFO_0_board_id='S_NO81730000'",
                "export STATIC_INFO_1_board_id='S_NO81730001'",
            ],
        ),
        (
            [{"SATA": "/dev/disk/by-id/ata-SanDisk_SSD_PLUS_120GB_190504A00573"}],
            "STORAGE_INFO",
            [
                "export STORAGE_INFO_0_SATA='/dev/disk/by-id/ata-SanDisk_SSD_PLUS_120GB_190504A00573'"
            ],
        ),
    ],
)
def test_export_data(data, prefix, result):
    action = OverlayAction()
    fout = Recorder()
    action._export_data(fout, data, prefix)
    assert sorted(fout.data.strip("\n").split("\n")) == result
