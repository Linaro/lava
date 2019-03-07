# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2019 Linaro Limited
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

from voluptuous import (
    All,
    Any,
    Exclusive,
    Invalid,
    Length,
    MultipleInvalid,
    NotIn,
    Optional,
    Range,
    Required,
    Schema,
)

from lava_common.timeout import Timeout


def validate_action(name, data, strict=True):
    # Import the module
    try:
        module = importlib.import_module("lava_common.schemas." + name)
        Schema(module.schema(), extra=not strict)(data)
    except ImportError:
        raise Invalid("unknown action type", path=["actions"] + name.split("."))
    except MultipleInvalid as exc:
        raise Invalid(exc.msg, path=["actions"] + name.split(".")) from exc


def validate(data, strict=True):
    schema = Schema(job(), extra=not strict)
    schema(data)
    for action in data["actions"]:
        # The job schema does already check the we have only one key
        action_type = next(iter(action.keys()))
        data = action[action_type]
        cls = None
        if action_type == "boot":
            cls = "boot." + data.get("method", "")
        elif action_type == "command":
            cls = "command"
        elif action_type == "deploy":
            cls = "deploy." + data.get("to", "")
        elif action_type == "test":
            if "definitions" in data:
                cls = "test.definition"
            elif "interactive" in data:
                cls = "test.interactive"
            elif "monitors" in data:
                cls = "test.monitor"
        if cls is None:
            raise Invalid("invalid action", path=["actions", action_type])
        cls = cls.replace("-", "_")
        validate_action(cls, data, strict=strict)


def timeout():
    return Any(
        {Required("days"): Range(min=1), Optional("skip"): bool},
        {Required("hours"): Range(min=1), Optional("skip"): bool},
        {Required("minutes"): Range(min=1), Optional("skip"): bool},
        {Required("seconds"): Range(min=1), Optional("skip"): bool},
    )


def action():
    return {
        Optional("namespace"): All(str, NotIn(["common"], msg="'common' is reserved")),
        Optional("connection-namespace"): str,
        Optional("protocols"): object,
        Optional("role"): [str],
        Optional("timeout"): timeout(),
        Optional("repeat"): Range(min=1),  # TODO: where to put it?
        Optional("failure_retry"): Range(min=1),  # TODO: where to put it?
    }


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


def extra_checks(data):
    check_job_timeouts(data)
    check_multinode_or_device_type(data)
    check_multinode_roles(data)
    check_namespace(data)
    check_secrets_visibility(data)


def check_job_timeouts(data):
    job_duration = Timeout.parse(data["timeouts"]["job"])

    def _check_timeout(prefix, path, local_data):
        if local_data is None:
            return
        duration = Timeout.parse(local_data)
        if duration > job_duration:
            raise Invalid("%s timeout is larger than job timeout" % prefix, path=path)

    # global timeouts
    _check_timeout("Global", ["timeouts", "action"], data["timeouts"].get("action"))
    for key in data["timeouts"].get("actions", []):
        _check_timeout(
            "Global", ["timeouts", "actions", key], data["timeouts"]["actions"][key]
        )
    _check_timeout(
        "Global", ["timeouts", "connection"], data["timeouts"].get("connection")
    )
    for key in data["timeouts"].get("connections", []):
        _check_timeout(
            "Global",
            ["timeouts", "connections", key],
            data["timeouts"]["connections"][key],
        )

    # action timeouts
    for (index, action) in enumerate(data["actions"]):
        action_type = next(iter(action.keys()))
        t = action[action_type].get("timeout")
        if t is None:
            continue
        _check_timeout("Action", ["actions", str(index)], t)


def check_multinode_or_device_type(data):
    device_type = data.get("device_type")
    multinode = data.get("protocols", {}).get("lava-multinode")

    if device_type and multinode:
        raise Invalid('"device_type" shoud not be used with multinode')
    if not device_type and not multinode:
        raise Invalid('"device_type" or multinode should be defined')


def check_multinode_roles(data):
    # When using multinode, each action should have a role
    if not data.get("protocols", {}).get("lava-multinode"):
        return

    for action in data.get("actions", []):
        action_type = next(iter(action.keys()))
        if "role" not in action[action_type]:
            raise Invalid("Every action of a multinode job should have roles")


def check_namespace(data):
    # If namespace is used in one action, every actions should use namespaces.
    actions_with_ns = 0
    for action in data["actions"]:
        action_type = next(iter(action.keys()))
        ns = action[action_type].get("namespace")
        if ns is not None:
            actions_with_ns += 1

    if actions_with_ns and (len(data["actions"]) != actions_with_ns):
        raise Invalid("When using namespaces, every action should have a namespace")


def check_secrets_visibility(data):
    if "secrets" in data and data["visibility"] == "public":
        raise Invalid('When using "secrets", visibility shouldn\'t be "public"')


def job():
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

    return All(
        {
            Required("job_name"): All(str, Length(min=1, max=200)),
            Optional("device_type"): All(str, Length(min=1, max=200)),
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
            Optional("secrets"): dict,
            Optional("visibility"): Any("public", "personal", {"group": [str]}),
            Optional("protocols"): {
                Optional("lava-lxc"): Any(lava_lxc, {str: lava_lxc}),
                Optional("lava-multinode"): {
                    Required("roles"): {
                        str: Any(
                            {
                                Required("device_type"): str,
                                Required("count"): Range(min=0),
                                Optional("context"): dict,
                                Optional("tags"): [str],
                                Optional("timeout"): timeout(),
                            },
                            {
                                Required("connection"): str,
                                Required("count"): Range(min=0),
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
        },
        extra_checks,
    )
