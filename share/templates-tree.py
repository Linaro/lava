#!/usr/bin/env python3
# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
#
# This script prints the templates inheritance tree from a given directories
# Example print inheritance of the device types in the development tree:
#
# PYTHONPATH=. python3 ./share/templates-tree.py ./etc/dispatcher-config/device-types/
from __future__ import annotations

from argparse import ArgumentParser
from itertools import chain
from pathlib import Path
from pprint import pp

from jinja2.nodes import Extends as JinjaNodeExtends

from lava_common.jinja import create_device_templates_env


def pprint_templates_tree(templates_dirs: list[Path]) -> None:
    device_type_name_to_extends: dict[str, str | None] = {}

    jinja_env = create_device_templates_env()
    for template_file in chain.from_iterable(
        templates_dir.iterdir() for templates_dir in templates_dirs
    ):
        device_type_name = template_file.name
        ast = jinja_env.parse(template_file.read_text())
        extends = ast.find(JinjaNodeExtends)
        if extends is not None:
            device_type_name_to_extends[device_type_name] = extends.template.value
        else:
            device_type_name_to_extends[device_type_name] = None

    each_device_type_node: dict[str, dict] = {
        dt: {} for dt in device_type_name_to_extends
    }
    template_tree: dict[str, dict] = {}

    for device_type, extends in device_type_name_to_extends.items():
        if extends is None:
            # Top level template that does not inherit any other template
            template_tree[device_type] = each_device_type_node[device_type]
        else:
            parent_node = each_device_type_node[extends]
            parent_node[device_type] = each_device_type_node[device_type]

    pp(template_tree)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("templates_dirs", type=Path, nargs="+")
    pprint_templates_tree(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
