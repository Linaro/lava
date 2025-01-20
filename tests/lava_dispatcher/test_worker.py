# Copyright (C) 2025-present Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import time
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest

from lava_common.worker import get_parser
from lava_dispatcher.worker import (
    Job,
    LavaWorkerOptions,
    ServerUnavailable,
    VersionMismatch,
    get_job_data,
)


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


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def mock_options():
    options = MagicMock()
    options.exit_on_version_mismatch = True
    options.url = "http://example.com"
    options.token = "worker_token"
    options.name = "worker_name"
    return options


@pytest.mark.asyncio
async def test_get_job_data(mock_session, mock_options):
    expected_data = {
        "running": [{"id": 1, "token": "token1"}],
        "cancel": [{"id": 2, "token": "token2"}],
        "start": [{"id": 3, "token": "token3"}],
    }

    with patch("lava_dispatcher.worker.ping") as mock_ping:
        mock_ping.return_value = expected_data

        data = await get_job_data(mock_session, mock_options)

        mock_ping.assert_called_once_with(
            mock_session, "http://example.com", "worker_token", "worker_name"
        )

        assert data == expected_data


@pytest.mark.asyncio
async def test_get_job_data_server_unavailable(mock_session, mock_options):
    with patch("lava_dispatcher.worker.ping") as mock_ping:
        mock_ping.side_effect = ServerUnavailable("Server unavailable")

        data = await get_job_data(mock_session, mock_options)

        assert data == {}


@pytest.mark.asyncio
async def test_get_job_data_version_mismatch_exit(mock_session, mock_options):
    mock_options.exit_on_version_mismatch = True
    with patch("lava_dispatcher.worker.ping") as mock_ping:
        mock_ping.side_effect = VersionMismatch("Version mismatch")

        with pytest.raises(VersionMismatch):
            await get_job_data(mock_session, mock_options)


@pytest.mark.asyncio
async def test_get_job_data_version_mismatch_no_exit(mock_session, mock_options):
    mock_options.exit_on_version_mismatch = False
    with patch("lava_dispatcher.worker.ping") as mock_ping:
        mock_ping.side_effect = VersionMismatch("Version mismatch")

        data = await get_job_data(mock_session, mock_options)

        assert data == {}


class TestWorker(TestCase):
    def test_worker_argparse(self) -> None:
        # Test that options dataclass can be initialized from the parsed
        # arguments.
        LavaWorkerOptions(
            **vars(
                get_parser().parse_args(
                    ["--name", "unittest_worker", "--url", "https://example.com"]
                )
            )
        )
        # Check that --url is required
        with self.assertRaises(SystemExit):
            LavaWorkerOptions(
                **vars(get_parser().parse_args(["--name", "unittest_worker"]))
            )
