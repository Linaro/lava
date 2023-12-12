# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from django.db.models import Case, Field, TextField, Value, When

from lava_common.yaml import yaml_safe_load

if TYPE_CHECKING:
    from django.db.models import IntegerField


@cache
def annotate_int_field_verbose(field: IntegerField):
    return Case(
        *(
            When(**{field.attname: choice_int, "then": Value(choice_str)})
            for choice_int, choice_str in field.choices
        ),
        default=Value("Undefined"),
        output_field=TextField(),
    )


class YamlField(Field):
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return yaml_safe_load(value)
