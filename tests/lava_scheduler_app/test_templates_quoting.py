# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from shlex import quote as shlex_quote
from shlex import split as shlex_split
from unittest import TestCase

from lava_common.yaml import yaml_safe_load
from lava_scheduler_app.environment import DEVICES_JINJA_ENV

# Based on base-uboot.jinja2
SAMPLE_FILTER_SECTIONS_TEMPLATE = """---
commands:
    - "tftp {KERNEL_ADDR} {KERNEL}"
    - {% filter yaml_quote %}setenv bootargs {% filter shlex_quote -%}
        {{ console_device }}{{ baud_rate }} root=/dev/nfs rw {{ base_nfsroot_args }} {{ base_kernel_args }} {{ base_ip_args }}
        {%- endfilter %}{% endfilter %}

"""

SAMPLE_CONTAINER_QUOTING_TEMPLATE = """---
commands: {{ uboot_commands|yaml_quote }}
"""


class TestTemplateQuoting(TestCase):
    def test_template_quoting_filters_sections(self) -> None:
        template = DEVICES_JINJA_ENV.from_string(SAMPLE_FILTER_SECTIONS_TEMPLATE)
        dyndbg_fragment = 'dyndbg="file dd.c +p"'
        base_kernel_args = (
            "'console_msg_format=syslog' earlycon"
            f"deferred_probe_timeout=60 debug {dyndbg_fragment}  ignore_loglevel"
        )
        rendered_template = template.render(
            console_device="console=ttySC0,115200n8",
            baud_rate="",
            base_nfsroot_args="nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard",
            base_kernel_args=base_kernel_args,
            base_ip_args="ip=dhcp",
        )
        parsed_yaml = yaml_safe_load(rendered_template)
        setenv_string = parsed_yaml["commands"][-1]
        self.assertTrue(setenv_string.startswith("setenv "))
        setenv_shell_list = shlex_split(setenv_string)
        self.assertEqual(
            len(setenv_shell_list),
            3,
            "Test that POSIX shell will interpret commands as 3 arguments.",
        )
        bootargs_string = setenv_shell_list[-1]
        self.assertIn(
            base_kernel_args,
            bootargs_string,
            "Test that kernel arguments survived quoting unchanged.",
        )

    def test_template_container_quoting(self) -> None:
        bootargs = (
            "'console=ttySC0,115200n8' root=/dev/nfs rw "
            "nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard console_msg_format=syslog "
            'earlycon deferred_probe_timeout=60 debug dyndbg="file dd.c +p" '
            "ignore_loglevel ip=dhcp"
        )
        uboot_commands = [
            "tfpt {KERNEL_ADDR} {KERNEL}",
            f"setenv bootargs {shlex_quote(bootargs)}",
        ]
        template = DEVICES_JINJA_ENV.from_string(SAMPLE_CONTAINER_QUOTING_TEMPLATE)
        rendered_template = template.render(uboot_commands=uboot_commands)
        self.assertEqual(uboot_commands, yaml_safe_load(rendered_template)["commands"])
