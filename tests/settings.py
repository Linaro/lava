# Copyright (C) 2023 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path

import lava_server.settings.dev

base_tests_path = Path(__file__).parent

tests_settings = {
    k: v for k, v in vars(lava_server.settings.dev).items() if k.isupper()
}

tests_settings["DEVICES_PATH"] = str(base_tests_path / "lava_scheduler_app/devices")
tests_settings["HEALTH_CHECKS_PATH"] = str(
    base_tests_path / "lava_scheduler_app/health-checks"
)

globals().update(**tests_settings)
