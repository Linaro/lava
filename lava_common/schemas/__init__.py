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

import importlib

from voluptuous import Any, Invalid, Optional, Range, Required, Schema

from lava_common.exceptions import JobError, LAVABug


def validate(name, data, live=False):
    # Import the module
    try:
        module = importlib.import_module("lava_common.schemas." + name)
    except ImportError:
        raise LAVABug("unable to find module 'lava_common.schemas.%s'" % name)

    try:
        Schema(module.schema(live))(data)
        return None
    except Invalid as exc:
        raise JobError(
            "%s (%s)" % (exc.msg, ", ".join([str(s) for s in exc.path]))
        ) from exc


def timeout():
    return Any(
        {Required("days"): Range(min=1), Optional("skip"): bool},
        {Required("hours"): Range(min=1), Optional("skip"): bool},
        {Required("minutes"): Range(min=1), Optional("skip"): bool},
        {Required("seconds"): Range(min=1), Optional("skip"): bool},
    )


def action(live=False):
    base = {
        Optional("namespace"): str,
        Optional("protocols"): object,
        Optional("role"): str,
        Optional("timeout"): timeout(),
    }

    if not live:
        return base
    return {
        **base,
        Optional("lava-lxc"): object,
        Optional("lava-multinode"): object,
        Optional("lava-vland"): object,
        Optional("repeat-count"): Range(min=0),
    }
