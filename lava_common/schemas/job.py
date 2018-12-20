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

from voluptuous import All, Any, Exclusive, Length, Optional, Range, Required

from lava_common.schemas import timeout


def notify():
    callback = {
        Required("url"): str,
        Optional("method"): Any("GET", "POST"),
        Optional("token"): str,
        Optional("dataset"): Any("minimal", "logs", "results", "all"),
        Optional("content-type"): Any("json", "urlencoded"),
    }

    return {
        Required("criteria"): Any(
            {
                Required("status"): Any(
                    "finished", "running", "complete", "canceled", "incomplete"
                )
            },
            {
                Required("status"): Any("complete", "incomplete"),
                Optional("type"): Any("regression", "progression"),
            },
        ),
        Optional("verbosity"): Any("verbose", "quiet", "status-only"),
        Optional("recipients"): [
            {
                Required("to"): {
                    Required("method"): Any("email", "irc"),
                    Optional("user"): str,
                    Optional("email"): str,
                    Optional("handle"): str,
                    Optional("server"): str,
                }
            }
        ],
        Exclusive("callback", "callback"): callback,
        Exclusive("callbacks", "callback"): [callback],
        Optional("compare"): {
            Optional("blacklist"): [str],
            Optional("query"): Any(
                {Required("username"): str, Required("name"): str},
                {Required("entity"): str, Optional("conditions"): {str: str}},
            ),
        },
    }


def schema():
    lava_lxc = {
        Required("name"): str,
        Required("distribution"): str,
        Required("release"): str,
        Optional("arch"): str,
        Optional("mirror"): str,
        Optional("persist"): bool,
        Optional("security_mirror"): str,
        Optional("template"): str,
        Optional("timeout"): timeout(),
        Optional("verbose"): bool,
    }

    return {
        Required("job_name"): All(str, Length(min=1, max=200)),
        Required("device_type"): All(str, Length(min=1, max=200)),
        Required("timeouts"): {
            Required("job"): timeout(),
            Optional("action"): timeout(),
            Optional("actions"): {str: timeout()},
            Optional("connection"): timeout(),
            Optional("connections"): {str: timeout()},
        },
        Optional("context"): dict,
        Optional("metadata"): {str: object},
        Optional("priority"): Any("high", "medium", "low", Range(min=0, max=100)),
        Optional("tags"): [str],
        Optional("secrets"): dict,  # FIXME: validate that job is not public
        Optional("visibility"): Any("public", "personal", {"group": [str]}),
        Optional("protocols"): {
            Optional("lava-lxc"): Any(lava_lxc, {str: lava_lxc}),
            Optional("lava-multinode"): {
                Required("roles"): {
                    str: Any(
                        {
                            Required("device_type"): str,
                            Required("count"): Range(min=1),
                            Optional("context"): dict,
                            Optional("tags"): [str],
                            Optional("timeout"): timeout(),
                        },
                        {
                            Required("connection"): str,
                            Required("count"): Range(min=1),
                            Required("expect_role"): str,
                            Required("host_role"): str,
                            Optional("request"): str,
                            Optional("tags"): [str],
                            Optional("timeout"): timeout(),
                        },
                    )
                },
                Optional("timeout"): timeout(),
            },
            Optional("lava-vland"): Any(
                {str: {str: {Required("tags"): [str]}}},
                {str: {Required("tags"): [str]}},
            ),
            Optional("lava-xnbd"): {
                Required("port"): Any("auto", int),
                Optional("timeout"): timeout(),
            },
        },
        Optional("notify"): notify(),
        Optional("reboot_to_fastboot"): bool,
        Required("actions"): [{Any("boot", "command", "deploy", "test"): dict}],
    }
