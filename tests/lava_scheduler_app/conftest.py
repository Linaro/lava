# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest


@pytest.fixture(autouse=True)
def update_settings(mocker, tmp_path):
    mocker.patch(
        "lava_scheduler_app.models.TestJob.output_dir", str(tmp_path / "job-output")
    )
