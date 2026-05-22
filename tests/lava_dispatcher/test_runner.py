# Copyright (C) 2026 LAVA contributors
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from lava_common.log import (
    YAMLFileHandler,
    YAMLHTTPHandler,
    YAMLLogger,
    run_output_sender,
)
from lava_dispatcher.runner import parser, setup_logger


class TestLavaRun(TestCase):
    def test_lava_run_arg_parser_and_logger(self) -> None:
        arg_parser = parser()

        temp_dir_name = self.enterContext(TemporaryDirectory())
        temp_dir_path = Path(temp_dir_name)
        device_yaml_path = temp_dir_path / "device.yaml"
        job_definition_path = temp_dir_path / "job.yaml"

        options = arg_parser.parse_args(
            [
                "--job-id=12345",
                f"--output-dir={temp_dir_name}",
                "--url=example.com",
                "--token=qwerty",
                "--job-log-interval=10",
                f"--device={device_yaml_path}",
                str(job_definition_path),
            ]
        )

        self.enterContext(
            patch("lava_dispatcher.runner.DISPATCHER_DOWNLOAD_DIR", temp_dir_name)
        )
        multiprocess_mock = self.enterContext(patch("lava_common.log.multiprocessing"))

        logger = setup_logger(options)
        self.addCleanup(logger.close)

        self.assertIsInstance(logger, YAMLLogger)
        self.assertEqual(
            {type(h) for h in logger.handlers}, {YAMLFileHandler, YAMLHTTPHandler}
        )

        multiprocess_mock.Process.assert_called_once_with(
            target=run_output_sender,
            args=(
                multiprocess_mock.Queue(),
                "example.com/scheduler/internal/v1/jobs/12345/logs/",
                "qwerty",
                10,
                "12345",
            ),
        )

        self.assertTrue((temp_dir_path / "12345").is_dir())
