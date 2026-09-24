# Copyright (C) 2026 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import pytest
from voluptuous import Invalid

from lava_common.schemas import validate

MULTINODE_JOB = {
    "job_name": "multinode job",
    "visibility": "public",
    "timeouts": {"job": {"minutes": 10}},
    "protocols": {
        "lava-multinode": {
            "roles": {
                "server": {"device_type": "qemu", "count": 1},
                "client": {"device_type": "qemu", "count": 1},
            }
        }
    },
    "actions": [
        {"boot": {"method": "qemu", "media": "tmpfs", "role": ["server", "client"]}}
    ],
}


def multinode_job(pool_pattern=None):
    job = {
        **MULTINODE_JOB,
        "protocols": {
            "lava-multinode": {**MULTINODE_JOB["protocols"]["lava-multinode"]}
        },
    }
    if pool_pattern is not None:
        job["protocols"]["lava-multinode"]["pool_pattern"] = pool_pattern
    return job


class TestPoolPattern:
    def test_without_pool_pattern(self):
        validate(multinode_job(), strict=True)

    @pytest.mark.parametrize(
        "pool_pattern", ["pool-*", "lab-?", "rack-[0-9]", "rack", "*"]
    )
    def test_valid_pool_patterns(self, pool_pattern):
        validate(multinode_job(pool_pattern), strict=True)

    def test_pool_pattern_should_be_a_string(self):
        with pytest.raises(Invalid):
            validate(multinode_job(42), strict=True)

    def test_pool_pattern_should_not_be_empty(self):
        with pytest.raises(Invalid):
            validate(multinode_job(""), strict=True)

    def test_pool_pattern_is_rejected_at_the_top_level(self):
        job = multinode_job()
        job["pool_pattern"] = "pool-*"
        with pytest.raises(Invalid):
            validate(job, strict=True)
