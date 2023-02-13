# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Optional, Required

from lava_common.schemas import docker
from lava_common.schemas.test.definition import schema as base


def schema():
    docker_test_shell_base = {
        Required("docker"): docker(),
        Optional("downloads-namespace"): str,
    }
    return {**base(), **docker_test_shell_base}
