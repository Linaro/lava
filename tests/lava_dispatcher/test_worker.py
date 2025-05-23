# Copyright (C) 2025-present Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import time
from unittest.mock import MagicMock, patch

import pytest

from lava_dispatcher.worker import Job


@pytest.fixture
@patch("lava_dispatcher.worker.Job.__init__", return_value=None)
def job(init):
    job = Job(row=MagicMock())
    job.job_id = 123
    job.last_update = int(time.monotonic())
    job.description = MagicMock(return_value="")
    return job


def test_finalize_timed_out_no_desc(job):
    assert job.finalize_timed_out() is True


def test_finalize_timed_out_yaml_error(job):
    job.description = MagicMock(return_value="invalid: yaml: content:")
    assert job.finalize_timed_out() is True


def test_finalize_timed_out_attr_error(job):
    job.description = MagicMock(return_value="[]")
    assert job.finalize_timed_out() is True


def test_finalize_timed_out(job):
    desc = """pipeline:
- class: FinalizeAction
  name: finalize
  timeout: 1
    """
    job.description = MagicMock(return_value=desc)
    job.last_update = int(time.monotonic()) - 2
    assert job.finalize_timed_out() is True


def test_finalize_timed_out_false(job):
    desc = """pipeline:
- class: FinalizeAction
  name: finalize
  timeout: 300
    """
    job.description = MagicMock(return_value=desc)
    assert job.finalize_timed_out() is False
