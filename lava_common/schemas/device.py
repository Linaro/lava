#
# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib

from voluptuous import All, Any, Invalid, Length, Optional, Required, Schema

from . import timeout


def device():
    timeout_schema = timeout()

    return {
        Optional("character_delays"): {Optional("boot"): int, Optional("test"): int},
        Optional("commands"): {
            Optional("connect"): str,
            Optional("connections"): {
                str: {Required("connect"): str, Optional("tags"): [str]}
            },
            Optional("hard_reset"): Any(str, [str]),
            Optional("soft_reboot"): Any(str, [str]),
            Optional("power_off"): Any(str, [str]),
            Optional("power_on"): Any(str, [str]),
            Optional("pre_power_command"): Any(str, [str]),
            Optional("pre_os_command"): Any(str, [str]),
            Optional("users"): {str: {Required("do"): str, Optional("undo"): str}},
        },
        Required("constants"): dict,
        Optional("adb_serial_number"): str,
        Optional("fastboot_serial_number"): str,
        Optional("fastboot_options"): [str],
        Optional("fastboot_via_uboot"): bool,
        Optional("device_info"): [dict],
        Optional("static_info"): [dict],
        Optional("storage_info"): [dict],
        Optional("environment"): dict,
        Optional("flash_cmds_order"): [str],
        Required("parameters"): {
            # TODO: having a more precise schema make this fail on debian 9,
            # maybe due to the dictionary key ordering in python3.5
            Optional("interfaces"): dict,
            Optional("media"): {
                Optional("sata"): {
                    Required("UUID-required"): bool,
                    Required(str): {
                        Required("uuid"): str,
                        Required("device_id"): int,
                        Required("uboot_interface"): str,
                        Required("grub_interface"): str,
                        Required("boot_part"): int,
                    },
                },
                Optional("sd"): {
                    Optional("UUID-required"): bool,
                    Required(str): {Required("uuid"): str, Required("device_id"): int},
                },
                Optional("usb"): {
                    Optional("UUID-required"): bool,
                    Required(str): {Required("uuid"): str, Required("device_id"): int},
                },
            },
            Optional(Any("image", "booti", "uimage", "bootm", "zimage", "bootz")): {
                Required("kernel"): str,
                Required("ramdisk"): str,
                Required("dtb"): str,
            },
            # FIXME: should be removed when the templates are fixed
            Optional("pass"): None,
        },
        Optional("board_id"): str,
        Optional("usb_vendor_id"): All(
            str, Length(min=4, max=4)
        ),  # monitor type like arduino
        Optional("usb_product_id"): All(
            str, Length(min=4, max=4)
        ),  # monitor type like arduino
        Optional("usb_sleep"): int,
        Optional("usb_filesystem_label"): str,
        Optional("usb_serial_driver"): str,
        Required("actions"): {
            Required("deploy"): {
                Required("methods"): dict,
                Optional("connections"): dict,
                Optional("parameters"): dict,
            },
            Required("boot"): {
                Required("connections"): dict,
                Required("methods"): dict,
            },
        },
        Required("timeouts"): {
            Required("actions"): {str: timeout_schema},
            Required("connections"): {str: timeout_schema},
        },
        Optional("available_architectures"): [str],
    }


def extra_checks(data):
    power_control_commands = ["power_off", "power_on", "hard_reset"]
    with contextlib.suppress(KeyError):
        ssh_host = data["actions"]["deploy"]["methods"]["ssh"]["host"]
        if ssh_host and "commands" in data:
            for command in power_control_commands:
                if command in data["commands"]:
                    raise Invalid(
                        "When primary connection is used, power control commands (%s) should not be specified."
                        % ", ".join(power_control_commands)
                    )


def validate(data):
    schema = Schema(All(device(), extra_checks), extra=True)
    schema(data)
