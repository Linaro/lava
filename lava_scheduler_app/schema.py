# -*- coding: utf-8 -*-
# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
import re
from voluptuous import (
    All,
    Any,
    Exclusive,
    In,
    Invalid,
    Length,
    Match,
    MultipleInvalid,
    Optional,
    Required,
    Schema,
)

from lava_common.schemas import CONTEXT_VARIABLES

from django.conf import settings

INVALID_CHARACTER_ERROR_MSG = "Invalid character"


CALLBACK_SCHEMA = {
    Required("url"): str,
    Optional("method"): Any("GET", "POST"),
    Optional("token"): str,
    Optional("dataset"): Any("minimal", "logs", "results", "all"),
    Optional("content-type"): Any("json", "urlencoded"),
}


class SubmissionException(UserWarning):
    """ Error raised if the submission is itself invalid. """


def _timeout_schema():
    return Schema(
        {
            Exclusive("days", "timeout_unit"): int,
            Exclusive("hours", "timeout_unit"): int,
            Exclusive("minutes", "timeout_unit"): int,
            Exclusive("seconds", "timeout_unit"): int,
            Optional("skip"): bool,
        }
    )


def _deploy_tftp_schema():
    return Schema(
        {
            Required("to"): "tftp",
            Optional("timeout"): _timeout_schema(),
            Optional("kernel"): {Required("url"): str},
            Optional("ramdisk"): {Required("url"): str},
            Optional("nbdroot"): {Required("url"): str},
            Optional("initrd"): {Required("url"): str},
            Optional("nfsrootfs"): {Required("url"): str},
            Optional("dtb"): {Required("url"): str},
            Optional("modules"): {Required("url"): str},
            Optional("tee"): {Required("url"): str},
        },
        extra=True,
    )


def _job_deploy_schema():
    return Schema(
        {Required("to"): str, Optional("timeout"): _timeout_schema()}, extra=True
    )


def _auto_login_schema():
    return Schema(
        {
            Required("login_prompt"): str,
            Required("username"): str,
            Optional("password_prompt"): str,
            Optional("password"): str,
            Optional("login_commands"): list,
        }
    )


def _simple_params():
    return Schema({Any(str): Any(str, bool)})


def _context_schema():
    context_variables = CONTEXT_VARIABLES + settings.EXTRA_CONTEXT_VARIABLES
    return Schema({In(context_variables): Any(int, str, [int, str])}, extra=False)


def _job_boot_schema():
    return Schema(
        {
            Required("method"): str,
            Optional("timeout"): _timeout_schema(),
            Optional("auto_login"): _auto_login_schema(),
            Optional("parameters"): _simple_params(),
            Optional("commands"): Any(str, list),
        },
        extra=True,
    )


def _inline_schema():
    return Schema({"metadata": dict, "install": dict, "run": dict, "parse": dict})


def _test_definition_schema():
    return Schema(
        [
            {
                Required("repository"): Any(_inline_schema(), str),
                Required("from"): str,
                Required("name"): str,
                Required("path"): str,
                Optional("parameters"): dict,
                Optional("timeout"): _timeout_schema(),
            }
        ],
        extra=True,
    )


def _job_test_schema():
    return Schema(
        {
            Required("definitions"): _test_definition_schema(),
            Optional("timeout"): _timeout_schema(),
        },
        extra=True,
    )


def _job_monitor_schema():
    return Schema(
        {
            Required("monitors"): _monitor_def_schema(),
            Optional("timeout"): _timeout_schema(),
        },
        extra=True,
    )


def _monitor_def_schema():
    return Schema(
        [
            {
                Required("name"): Match(
                    r"^[a-zA-Z0-9-_]+$", msg=INVALID_CHARACTER_ERROR_MSG
                ),
                Required("start"): str,
                Required("end"): str,
                Required("pattern"): str,
                Optional("fixupdict"): dict,
            }
        ]
    )


def _job_interactive_schema():
    return Schema(
        {
            Required("interactive"): _interactive_def_schema(),
            Optional("timeout"): _timeout_schema(),
        },
        extra=True,
    )


def _interactive_def_schema():
    return Schema(
        [
            {
                Required("name"): Match(
                    r"^[a-zA-Z0-9-_]+$", msg=INVALID_CHARACTER_ERROR_MSG
                ),
                Required("prompts"): list,
                Optional("echo"): "discard",
                Required("script"): _interactive_script_schema(),
            }
        ]
    )


def _interactive_script_schema():
    return Schema(
        [
            {
                Optional("name"): Match(
                    r"^[a-zA-Z0-9-_]+$", msg=INVALID_CHARACTER_ERROR_MSG
                ),
                Optional("command"): Any(None, str),
                Optional("delay"): int,
                Optional("lava-send"): str,
                Optional("lava-sync"): str,
                Optional("lava-wait"): str,
                Optional("lava-wait-all"): str,
                Optional("wait_for_prompt"): bool,
                Optional("failures"): [
                    {
                        Required("message"): str,
                        Optional("exception"): Any(
                            "InfrastructureError", "JobError", "TestError"
                        ),
                        Optional("error"): str,
                    }
                ],
                Optional("successes"): [{Required("message"): str}],
            }
        ]
    )


def _job_command_schema():
    return Schema(
        {
            Required("name"): str,
            Optional("timeout"): _timeout_schema(),
            Optional("namespace"): str,
        },
        extra=True,
    )


def _job_actions_schema():
    return Schema(
        [
            {
                "deploy": Any(_deploy_tftp_schema(), _job_deploy_schema()),
                "boot": _job_boot_schema(),
                "test": Any(
                    _job_monitor_schema(), _job_interactive_schema(), _job_test_schema()
                ),
                "command": _job_command_schema(),
            }
        ]
    )


def _job_notify_schema():
    return Schema(
        {
            Required("criteria"): _notify_criteria_schema(),
            "recipients": _recipient_schema(),
            Exclusive("callback", "legacy_callback"): _legacy_callback_schema(),
            Exclusive("callbacks", "legacy_callback"): _callback_schema(),
            "verbosity": Any("verbose", "quiet", "status-only"),
            "compare": _notify_compare_schema(),
        },
        extra=True,
    )


def _recipient_schema():
    EMAIL_STR = "email"
    IRC_STR = "irc"
    return Schema(
        [
            {
                Required("to"): {
                    Required("method"): Any(EMAIL_STR, IRC_STR),
                    "user": str,
                    "email": str,
                    "server": str,
                    "handle": str,
                }
            }
        ]
    )


def _notify_criteria_schema():
    return Schema(
        {
            Required("status"): Any(
                "running", "complete", "incomplete", "canceled", "finished"
            ),
            Optional("dependency_query"): str,
            "type": Any("progression", "regression"),
        },
        extra=True,
    )


def _notify_compare_schema():
    return Schema(
        {
            "query": Any(_query_name_schema(), _query_conditions_schema()),
            "blacklist": [str],
        },
        extra=True,
    )


def _query_name_schema():
    return Schema({Required("username"): str, Required("name"): str})


def _query_conditions_schema():
    return Schema({Required("entity"): str, "conditions": dict})


def _callback_schema():
    return Schema([CALLBACK_SCHEMA], extra=True)


def _legacy_callback_schema():
    return Schema(CALLBACK_SCHEMA, extra=True)


def vlan_name(value):
    if re.match("^[_a-zA-Z0-9]+$", str(value)):
        return str(value)
    else:
        raise Invalid(value)


def _validate_multinode(data_object):
    if data_object.get("protocols", {}).get("lava-multinode") is None:
        return
    multi = data_object["protocols"]["lava-multinode"]

    # List the roles
    roles = list(multi["roles"].keys())
    context_schema = _context_schema()
    # Check that "host_role" and "expect_role" does exist
    for role in roles:
        host_role = multi["roles"][role].get("host_role")
        expect_role = multi["roles"][role].get("expect_role")
        if host_role is not None:
            if host_role not in roles:
                raise SubmissionException("'host_role' '%s' does not exist" % host_role)
            if expect_role is None:
                raise SubmissionException(
                    "'expect_role' is required when 'host_role' is used"
                )
            if expect_role not in roles:
                raise SubmissionException(
                    "'expect_role' '%s' does not exist" % expect_role
                )
        elif expect_role is not None:
            raise SubmissionException("'expect_role' without 'host_role'")
        # Check context
        context = multi["roles"][role].get("context", {})
        context_schema(context)


def _job_protocols_schema():
    return Schema(
        {
            "lava-multinode": {"timeout": _timeout_schema(), "roles": dict},
            "lava-vland": {str: {vlan_name: {"tags": [str]}}},
            "lava-lxc": dict,
            "lava-xnbd": dict,
        }
    )


def action_name(value):
    if re.match(r"^[a-z-]+$", str(value)):
        return str(value)
    else:
        raise Invalid(value)


def _job_timeout_schema():
    return Schema(
        {
            Required("job"): _timeout_schema(),
            Optional("action"): _timeout_schema(),
            Optional("connection"): _timeout_schema(),
            Optional("actions"): {All(action_name): _timeout_schema()},
            Optional("connections"): {All(action_name): _timeout_schema()},
        }
    )


def visibility_schema():
    # possible values - 1 of 2 strings or a specified dict
    return Schema(Any("public", "personal", {"group": [str]}))


_job_schema = Schema(
    {
        "device_type": All(
            str, Length(min=1)
        ),  # not Required as some protocols encode it elsewhere
        Required("job_name"): All(str, Length(min=1, max=200)),
        Optional("priority"): Any("high", "medium", "low", int),
        Optional("protocols"): _job_protocols_schema(),
        Optional("context"): _context_schema(),
        Optional("metadata"): All({Any(str, int): Any(str, int)}),
        Optional("secrets"): dict,
        Optional("environment"): dict,
        Optional("tags"): [str],
        Required("visibility"): visibility_schema(),
        Required("timeouts"): _job_timeout_schema(),
        Required("actions"): _job_actions_schema(),
        Optional("notify"): _job_notify_schema(),
        Optional("reboot_to_fastboot"): bool,
    }
)


def _device_deploy_schema():
    return Schema(
        {
            "connections": dict,
            Required("methods"): dict,
            Optional("parameters"): _simple_params(),
        }
    )


def _device_boot_schema():
    return Schema({Required("connections"): dict, Required("methods"): dict})


def _device_actions_schema():
    return Schema({"deploy": _device_deploy_schema(), "boot": _device_boot_schema()})


def _device_timeouts_schema():
    return Schema(
        {
            Optional("actions"): {All(action_name): _timeout_schema()},
            Optional("connections"): {All(action_name): _timeout_schema()},
        }
    )


def _device_user_commands():
    return Schema({All(str): {Required("do"): str, Optional("undo"): str}})


def _device_connections_commands():
    return Schema({All(str): {"connect": str, Optional("tags"): list}})


def _device_commands_schema():
    return Schema(
        {
            All(str): Any(list, dict, str),
            Optional("connections"): _device_connections_commands(),
            Optional("users"): _device_user_commands(),
        }
    )


# Less strict than the job_schema as this is primarily admin / template
# controlled.
_device_schema = Schema(
    {
        "character_delays": dict,
        "commands": _device_commands_schema(),
        "constants": dict,
        "adb_serial_number": str,
        "fastboot_serial_number": str,
        "fastboot_options": [str],
        "fastboot_via_uboot": bool,
        "device_info": [dict],
        "static_info": [dict],
        "storage_info": [dict],
        "environment": dict,
        "flash_cmds_order": list,
        "parameters": dict,
        "board_id": str,
        "usb_vendor_id": All(str, Length(min=4, max=4)),  # monitor type like arduino
        "usb_product_id": All(str, Length(min=4, max=4)),  # monitor type like arduino
        "usb_sleep": int,
        "usb_filesystem_label": str,
        "usb_serial_driver": str,
        "actions": _device_actions_schema(),
        "timeouts": _device_timeouts_schema(),
        "available_architectures": list,
        "uuu_usb_otg_path": str,
        "uuu_corrupt_boot_media_command": [str],
    }
)


def _validate_vcs_parameters(data_objects):
    for action in data_objects["actions"]:
        if "test" in action and "definitions" in action["test"]:
            for definition in action["test"]["definitions"]:
                if (
                    "revision" in definition
                    and "shallow" in definition
                    and definition["shallow"] is True
                ):
                    raise SubmissionException(
                        "When 'revision' is used, 'shallow' shouldn't be 'True'"
                    )


def validate_submission(data_object):
    """
    Validates a python object as a TestJob submission
    :param data: Python object, e.g. from yaml.safe_load()
    :return: True if valid, else raises SubmissionException
    """
    try:
        _job_schema(data_object)
    except MultipleInvalid as exc:
        raise SubmissionException(exc)

    _validate_vcs_parameters(data_object)
    _validate_multinode(data_object)
    return True


def _validate_primary_connection_power_commands(data_object):
    power_control_commands = ["power_off", "power_on", "hard_reset"]

    # debug, tests don't pass. write docs.
    with contextlib.suppress(KeyError):
        ssh_host = data_object["actions"]["deploy"]["methods"]["ssh"]["host"]
        if ssh_host:
            if "commands" in data_object:
                for command in power_control_commands:
                    if command in data_object["commands"]:
                        raise SubmissionException(
                            "When primary connection is used, power control commands (%s) should not be specified."
                            % ", ".join(power_control_commands)
                        )


def validate_device(data_object):
    """
    Validates a python object as a pipeline device configuration
    e.g. yaml.safe_load(`lava-server manage device-dictionary --hostname host1 --export`)
    To validate a device_type template, a device dictionary needs to be created.
    :param data: Python object representing a pipeline Device.
    :return: True if valid, else raises SubmissionException
    """
    try:
        _device_schema(data_object)
    except MultipleInvalid as exc:
        raise SubmissionException(exc)

    _validate_primary_connection_power_commands(data_object)
    return True
