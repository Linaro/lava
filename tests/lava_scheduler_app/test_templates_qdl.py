# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# Author: Christopher Obbard <chris.obbard@oss.qualcomm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from .test_templates import BaseTemplateTest


class TestQDLTemplates(BaseTemplateTest):
    """
    Test rendering of the QDL jinja2 templates
    """

    def render_enter_commands(self, *variables: str):
        data = "\n".join(("{% extends 'qcs6490-rb3gen2.jinja2' %}", *variables))
        template_dict = self.render_device_dictionary_from_text(data)
        return template_dict["actions"]["boot"]["methods"]["qdl"]["parameters"][
            "enter-commands"
        ]

    def test_qdl_enter_command_unset(self):
        self.assertEqual([], self.render_enter_commands())

    def test_qdl_enter_command_string(self):
        self.assertEqual(
            "/usr/local/bin/tac-api.py --serial DP05DD00 --command bootToEDL",
            self.render_enter_commands(
                "{% set qdl_enter_command = "
                "'/usr/local/bin/tac-api.py --serial DP05DD00 --command bootToEDL' %}"
            ),
        )

    def test_qdl_enter_command_list(self):
        self.assertEqual(
            ["tac-api.py --command bootToEDL", "tac-api.py --command powerOn"],
            self.render_enter_commands(
                "{% set qdl_enter_command = ["
                "'tac-api.py --command bootToEDL', "
                "'tac-api.py --command powerOn'] %}"
            ),
        )

    def test_qdl_enter_commands_deprecated(self):
        # the deprecated qdl_enter_commands is still honoured
        self.assertEqual(
            ["tac-api.py --command bootToEDL"],
            self.render_enter_commands(
                "{% set qdl_enter_commands = ['tac-api.py --command bootToEDL'] %}"
            ),
        )

    def test_qdl_enter_command_overrides_deprecated(self):
        self.assertEqual(
            "tac-api.py --command bootToEDL",
            self.render_enter_commands(
                "{% set qdl_enter_commands = ['tac-api.py --command powerOn'] %}",
                "{% set qdl_enter_command = 'tac-api.py --command bootToEDL' %}",
            ),
        )
