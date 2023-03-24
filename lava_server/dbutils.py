# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from django.db.models import Case, TextField, Value, When

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
