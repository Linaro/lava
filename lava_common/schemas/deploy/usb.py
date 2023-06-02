#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Exclusive, Optional, Required

from lava_common.schemas import deploy

# TODO: one of download or writer should be defined
# TODO: one of images or image should be defined


def schema():
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
        Optional("tool"): {
            Required("prompts"): [str],
        },
        Optional("uniquify"): bool,
        **deploy.schema(),
    }
    return {**deploy.schema(), **base}
