# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest


@pytest.fixture(autouse=True)
def pyudev(mocker):
    return mocker.patch("lava_dispatcher_host.utils.pyudev")
