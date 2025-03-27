# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from contextvars import Context
from unittest import SkipTest, TestCase
from unittest.mock import patch

from yaml import SafeDumper

from lava_common.yaml import yaml_quote, yaml_quote_dumper, yaml_safe_load


class TestYamlQuoting(TestCase):
    def test_quoting_double_quotes(self) -> None:
        # String that causes the job to fail when passed as extra_kernel_args
        string_with_quotes = (
            "console_msg_format=syslog earlycon deferred_probe_timeout=60 "
            'debug dyndbg="file dd.c +p" ignore_loglevel'
        )
        yaml_quoted_string = yaml_quote(string_with_quotes)
        self.assertEqual(string_with_quotes, yaml_safe_load(yaml_quoted_string))
        self.assertNotIn("\n", yaml_quoted_string, "Test quoted string is single line")
        # Check idempotency
        yaml_quoted_string2 = yaml_quote(string_with_quotes)
        self.assertEqual(yaml_quoted_string2, yaml_quoted_string)
        self.assertEqual(string_with_quotes, yaml_safe_load(yaml_quoted_string2))

    def test_extremely_long_string(self) -> None:
        extremely_large_list = list(range(10_000))
        extremely_large_list_quote = yaml_quote(extremely_large_list)

        self.assertNotIn(
            "\n", extremely_large_list_quote, "Test quoted string is single line"
        )
        self.assertEqual(
            extremely_large_list, yaml_safe_load(extremely_large_list_quote)
        )

    def test_container_quoting(self) -> None:
        test_container = {
            "test": [1, 2, 3, 4, "\0"],
            "uboot_args": (
                "console_msg_format=syslog earlycon deferred_probe_timeout=60 "
                'debug dyndbg="file dd.c +p" ignore_loglevel'
            ),
        }
        test_container_quote = yaml_quote(test_container)

        self.assertNotIn(
            "\n", test_container_quote, "Test quoted string is single line"
        )

        self.assertEqual(test_container, yaml_safe_load(test_container_quote))

    def test_template_embedding(self) -> None:
        # Not an actual Jinja template but something similar
        test_template = r"""---
test: {TEST_OBJECT}
"""
        test_object = {
            "test": [1, 2, 3, 4, "\0"],
            "uboot_args": (
                "console_msg_format=syslog earlycon deferred_probe_timeout=60 "
                'debug dyndbg="file dd.c +p" ignore_loglevel'
            ),
        }

        test_yaml = test_template.format(TEST_OBJECT=yaml_quote(test_object))

        self.assertEqual(test_object, yaml_safe_load(test_yaml)["test"])

    def test_python_implementation_yaml(self) -> None:
        import lava_common.yaml

        if isinstance(lava_common.yaml.SafeDumper, SafeDumper):
            raise SkipTest(
                "CSafeDumper is not supported. Already tested Python implementation."
            )

        with patch("lava_common.yaml.SafeDumper", SafeDumper):
            context = Context()
            context.run(self.test_quoting_double_quotes)
            context.run(self.test_extremely_long_string)
            context.run(self.test_container_quoting)
            context.run(self.test_template_embedding)

        self.assertIsInstance(context[yaml_quote_dumper][1], SafeDumper)
