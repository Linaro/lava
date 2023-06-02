#
# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import importlib

from voluptuous import (
    All,
    Any,
    Exclusive,
    In,
    Invalid,
    Length,
    Match,
    MultipleInvalid,
    NotIn,
    Optional,
    Range,
    Required,
    Schema,
)

from lava_common.timeout import Timeout

CONTEXT_VARIABLES = [
    # qemu variables
    "arch",
    "boot_console",
    "boot_root",
    "cpu",
    "extra_options",
    "guestfs_driveid",
    "guestfs_interface",
    "guestfs_size",
    "machine",
    "memory",
    "model",
    "monitor",
    "netdevice",
    "no_kvm",
    "serial",
    "vga",
    # u-boot variables
    "booti_dtb_addr",
    "booti_kernel_addr",
    "booti_ramdisk_addr",
    "bootm_dtb_addr",
    "bootm_kernel_addr",
    "bootm_ramdisk_addr",
    "bootz_dtb_addr",
    "bootz_kernel_addr",
    "bootz_ramdisk_addr",
    # others
    "boot_character_delay",
    "boot_retry",
    "bootloader_prompt",
    "console_device",
    "custom_kernel_args",
    "extra_kernel_args",
    "extra_nfsroot_args",
    "failure_retry",
    "kernel_loglevel",
    "kernel_start_message",
    "lava_test_results_dir",
    "menu_interrupt_prompt",
    "mustang_menu_list",
    "test_character_delay",
    "tftp_mac_address",
    "uboot_extra_error_message",
    "uboot_needs_interrupt",
    "uboot_altbank",
]


def validate_action(name, index, data, strict=True):
    # Import the module
    try:
        module = importlib.import_module("lava_common.schemas." + name)
        Schema(module.schema(), extra=not strict)(data)
    except ImportError:
        raise Invalid("unknown action type", path=["actions"] + name.split("."))
    except MultipleInvalid as exc:
        path = ["actions[%d]" % index] + name.split(".") + exc.path
        raise Invalid(exc.msg, path=path) from exc


def validate(data, strict=True, extra_context_variables=[]):
    schema = Schema(job(extra_context_variables), extra=not strict)
    schema(data)
    for index, action in enumerate(data["actions"]):
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
                if "docker" in data:
                    cls = "test.docker"
                else:
                    cls = "test.definition"
            elif "interactive" in data:
                cls = "test.interactive"
            elif "monitors" in data:
                cls = "test.monitor"
        if cls is None:
            raise Invalid("invalid action", path=["actions[%s]" % index, action_type])
        cls = cls.replace("-", "_")
        validate_action(cls, index, data, strict=strict)


def timeout():
    return Any(
        {Required("days"): Range(min=1), Optional("skip"): bool},
        {Required("hours"): Range(min=1), Optional("skip"): bool},
        {Required("minutes"): Range(min=1), Optional("skip"): bool},
        {Required("seconds"): Range(min=1), Optional("skip"): bool},
    )


def action():
    return {
        Optional("namespace"): All(
            str,
            NotIn(
                ["common", "docker-test-shell"],
                msg="'common' and 'docker-test-shell' are reserved namespace names",
            ),
        ),
        Optional("connection-namespace"): str,
        Optional("protocols"): object,
        Optional("role"): [str],
        Optional("timeout"): timeout(),
        Optional("timeouts"): {str: timeout()},
        Optional("repeat"): Range(min=1),  # TODO: where to put it?
        Optional("failure_retry"): Range(min=1),  # TODO: where to put it?
        Optional("failure_retry_interval"): Range(min=1),
    }


def notify():
    callback = {
        Required("url"): str,
        Optional("method"): Any("GET", "POST"),
        Optional("token"): str,
        Optional("header"): str,
        Optional("dataset"): Any("minimal", "logs", "results", "all"),
        Optional("content-type"): Any("json", "urlencoded"),
    }

    return {
        Required("criteria"): Any(
            {
                Required("status"): "all",
            },
            {
                Required("status"): Any(
                    "finished",
                    "running",
                    "complete",
                    "canceled",
                    "incomplete",
                ),
                Optional("dependency_query"): str,
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
    check_multinode_roles(data)
    check_multinode_extras(data)
    check_namespace(data)


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
    for index, action in enumerate(data["actions"]):
        action_type = next(iter(action.keys()))
        t = action[action_type].get("timeout")
        if t is None:
            continue
        _check_timeout("Action", ["actions", str(index)], t)


def check_multinode_extras(data):
    multinode = data.get("protocols", {}).get("lava-multinode")

    extras = ("device_type", "environment", "context", "tags")
    for extra in extras:
        extra_value = data.get(extra)
        if extra_value and multinode:
            raise Invalid(f'"{extra}" should not be used with multinode')
        if extra == "device_type" and not extra_value and not multinode:
            raise Invalid(f'"{extra}" or multinode should be defined')


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


def job(extra_context_variables=[]):
    context_variables = CONTEXT_VARIABLES + extra_context_variables
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
                Optional("queue"): timeout(),
            },
            Required("visibility"): Any("public", "personal", {"group": [str]}),
            Optional("context"): Schema(
                {In(context_variables): Any(int, str, [int, str])}, extra=False
            ),
            Optional("metadata"): {str: object},
            Optional("priority"): Any("high", "medium", "low", Range(min=0, max=100)),
            Optional("tags"): [str],
            Optional("secrets"): dict,
            Optional("environment"): dict,
            Optional("protocols"): {
                Optional("lava-lxc"): Any(lava_lxc, {str: lava_lxc}),
                Optional("lava-multinode"): {
                    Required("roles"): {
                        str: Any(
                            {
                                Required("device_type"): str,
                                Required("count"): Range(min=0),
                                Optional("context"): Schema(
                                    {In(context_variables): Any(int, str, [int, str])},
                                    extra=False,
                                ),
                                Optional("tags"): [str],
                                Optional("environment"): dict,
                                Optional("essential"): bool,
                                Optional("timeout"): timeout(),
                            },
                            {
                                Required("connection"): str,
                                Required("count"): Range(min=0),
                                Required("expect_role"): str,
                                Required("host_role"): str,
                                Optional("essential"): bool,
                                Optional("request"): str,
                                Optional("tags"): [str],
                                Optional("timeout"): timeout(),
                                Optional("context"): Schema(
                                    {In(context_variables): Any(int, str, [int, str])},
                                    extra=False,
                                ),
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


docker_image_format_pattern = (
    "^[a-z0-9]+[a-z0-9._/:-]*[a-z0-9]+(:[a-zA-Z0-9_]+[a-zA-Z0-9._-]*)?$"
)
docker_image_format = Match(
    docker_image_format_pattern, msg="Invalid docker image name"
)


def docker(image_key="image"):
    return {
        Required(image_key): docker_image_format,
        Optional("local"): bool,
        Optional("container_name"): str,
        Optional("network_from"): str,
    }
