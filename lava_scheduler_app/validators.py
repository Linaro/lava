# Copyright (C) 2024 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from django.core.exceptions import ValidationError


def validate_non_slash(value):
    if "/" in value:
        raise ValidationError(
            f"{value} contains slash character", params={"value": value}
        )
