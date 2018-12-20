# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
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

from voluptuous import Any, Exclusive, Optional, Required

from lava_common.schemas import deploy

# TODO: one of download or writer should be defined
# TODO: one of images or image should be defined


def schema(live=False):
    base = {
        Required("to"): Any("sata", "sd", "usb"),
        Exclusive("images", "image"): {
            Required("image"): deploy.url(),
            Optional(str): deploy.url(),
        },
        Exclusive("image", "image"): deploy.url(),
        Required("device"): str,
        Optional("download"): {
            Required("tool"): str,
            Required("options"): str,
            Required("prompt"): str,
        },
        Optional("writer"): {
            Required("tool"): str,
            Required("options"): str,
            Required("prompt"): str,
        },
        Optional("uniquify"): bool,
        **deploy.schema(live),
    }
    return {**deploy.schema(live), **base}
